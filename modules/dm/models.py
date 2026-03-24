"""dm_models: DM(쪽지) 대화 및 메시지 관련 데이터 모델."""

from dataclasses import dataclass
from datetime import datetime

from core.database.connection import get_cursor, transactional
from core.utils.formatters import format_datetime
from schemas.common import DEFAULT_PROFILE_IMAGE

# DM 목록에서 미리보기로 보여줄 최대 글자 수
DM_PREVIEW_LENGTH = 100


@dataclass
class Conversation:
    """DM 대화 데이터 클래스."""

    id: int
    participant1_id: int
    participant2_id: int
    last_message_at: datetime | None
    created_at: datetime
    deleted_at: datetime | None


_CONV_COLUMNS = "id, participant1_id, participant2_id, last_message_at, created_at, deleted_at"


def _normalize_participants(a: int, b: int) -> tuple[int, int]:
    """참여자 ID를 정규화하여 (작은 값, 큰 값) 튜플로 반환합니다."""
    return (min(a, b), max(a, b))


async def get_or_create_conversation(user_id: int, recipient_id: int) -> tuple[Conversation, bool]:
    """대화를 조회하거나 새로 생성합니다. 삭제된 대화가 있으면 재활성화합니다."""
    p1, p2 = _normalize_participants(user_id, recipient_id)

    async with transactional() as cur:
        await cur.execute(
            f"SELECT {_CONV_COLUMNS} FROM dm_conversation WHERE participant1_id = %s AND participant2_id = %s",
            (p1, p2),
        )
        row = await cur.fetchone()

        if row:
            conv = Conversation(**row)
            if conv.deleted_at is not None:
                await cur.execute(
                    "UPDATE dm_conversation SET deleted_at = NULL, last_message_at = NULL WHERE id = %s",
                    (conv.id,),
                )
                conv.deleted_at = None
                conv.last_message_at = None
            return conv, False

        await cur.execute(
            "INSERT INTO dm_conversation (participant1_id, participant2_id) VALUES (%s, %s)",
            (p1, p2),
        )
        conv_id = cur.lastrowid

        await cur.execute(f"SELECT {_CONV_COLUMNS} FROM dm_conversation WHERE id = %s", (conv_id,))
        new_row = await cur.fetchone()
        if not new_row:
            raise RuntimeError(f"대화 삽입 직후 조회 실패: conv_id={conv_id}")

        return Conversation(**new_row), True


async def get_conversation_by_id(conversation_id: int) -> Conversation | None:
    """대화를 ID로 조회합니다. 삭제된 대화는 제외합니다."""
    async with get_cursor() as cur:
        await cur.execute(
            f"SELECT {_CONV_COLUMNS} FROM dm_conversation WHERE id = %s AND deleted_at IS NULL",
            (conversation_id,),
        )
        row = await cur.fetchone()
        return Conversation(**row) if row else None


async def get_conversations(user_id: int, offset: int = 0, limit: int = 20) -> tuple[list[dict], int]:
    """사용자의 대화 목록을 페이지네이션하여 반환합니다."""
    async with get_cursor() as cur:
        await cur.execute(
            """
                SELECT COUNT(*) AS cnt
                FROM dm_conversation
                WHERE (participant1_id = %s OR participant2_id = %s)
                  AND deleted_at IS NULL
                """,
            (user_id, user_id),
        )
        total_count = (await cur.fetchone())["cnt"]

        await cur.execute(
            """
                SELECT
                    c.id,
                    c.last_message_at,
                    c.created_at,
                    u.id AS other_user_id,
                    u.nickname,
                    u.profile_img,
                    u.deleted_at AS user_deleted_at,
                    (
                        SELECT IF(m.deleted_at IS NULL, m.content, NULL)
                        FROM dm_message m
                        WHERE m.conversation_id = c.id
                        ORDER BY m.created_at DESC
                        LIMIT 1
                    ) AS last_content,
                    (
                        SELECT m.sender_id
                        FROM dm_message m
                        WHERE m.conversation_id = c.id
                        ORDER BY m.created_at DESC
                        LIMIT 1
                    ) AS last_sender_id,
                    (
                        SELECT COUNT(*)
                        FROM dm_message m
                        WHERE m.conversation_id = c.id
                          AND m.sender_id != %s
                          AND m.is_read = 0
                          AND m.deleted_at IS NULL
                    ) AS unread_count
                FROM dm_conversation c
                JOIN user u ON u.id = IF(
                    c.participant1_id = %s,
                    c.participant2_id,
                    c.participant1_id
                )
                WHERE (c.participant1_id = %s OR c.participant2_id = %s)
                  AND c.deleted_at IS NULL
                ORDER BY COALESCE(c.last_message_at, c.created_at) DESC
                LIMIT %s OFFSET %s
                """,
            (user_id, user_id, user_id, user_id, limit, offset),
        )
        rows = await cur.fetchall()

    conversations = []
    for row in rows:
        other_nickname = row["nickname"] if row["nickname"] and row["user_deleted_at"] is None else "탈퇴한 사용자"
        other_profile = row["profile_img"] or DEFAULT_PROFILE_IMAGE

        last_content = row["last_content"]
        last_sender_id = row["last_sender_id"]

        last_msg_deleted = last_sender_id is not None and last_content is None

        last_message = None
        if last_sender_id is not None:
            if last_msg_deleted:
                last_message = {
                    "content": None,
                    "is_mine": last_sender_id == user_id,
                    "is_deleted": True,
                }
            elif last_content is not None:
                truncated = last_content[:DM_PREVIEW_LENGTH] + ("..." if len(last_content) > DM_PREVIEW_LENGTH else "")
                last_message = {
                    "content": truncated,
                    "is_mine": last_sender_id == user_id,
                    "is_deleted": False,
                }

        conversations.append(
            {
                "id": row["id"],
                "last_message_at": format_datetime(row["last_message_at"]),
                "created_at": format_datetime(row["created_at"]),
                "other_user": {
                    "user_id": row["other_user_id"],
                    "nickname": other_nickname,
                    "profile_image_url": other_profile,
                },
                "last_message": last_message,
                "unread_count": row["unread_count"],
            }
        )

    return conversations, total_count


async def send_message(conversation_id: int, sender_id: int, content: str) -> dict:
    """메시지를 전송합니다."""
    async with transactional() as cur:
        await cur.execute(
            "INSERT INTO dm_message (conversation_id, sender_id, content) VALUES (%s, %s, %s)",
            (conversation_id, sender_id, content),
        )
        message_id = cur.lastrowid

        await cur.execute(
            "UPDATE dm_conversation SET last_message_at = CURRENT_TIMESTAMP WHERE id = %s",
            (conversation_id,),
        )

        await cur.execute(
            "SELECT id, conversation_id, sender_id, content, is_read, created_at FROM dm_message WHERE id = %s",
            (message_id,),
        )
        row = await cur.fetchone()

        if not row:
            raise RuntimeError(f"메시지 삽입 직후 조회 실패: message_id={message_id}")

        return {
            "id": row["id"],
            "conversation_id": row["conversation_id"],
            "sender_id": row["sender_id"],
            "content": row["content"],
            "is_read": bool(row["is_read"]),
            "created_at": format_datetime(row["created_at"]),
        }


async def get_messages(conversation_id: int, offset: int = 0, limit: int = 50) -> tuple[list[dict], int]:
    """대화의 메시지 목록을 페이지네이션하여 반환합니다."""
    async with get_cursor() as cur:
        await cur.execute(
            "SELECT COUNT(*) AS cnt FROM dm_message WHERE conversation_id = %s",
            (conversation_id,),
        )
        total_count = (await cur.fetchone())["cnt"]

        await cur.execute(
            """
                SELECT m.id, m.sender_id, u.nickname AS sender_nickname,
                       u.profile_img AS sender_profile_image,
                       m.content, m.is_read, m.created_at, m.deleted_at
                FROM dm_message m
                JOIN user u ON m.sender_id = u.id
                WHERE m.conversation_id = %s
                ORDER BY m.created_at ASC
                LIMIT %s OFFSET %s
                """,
            (conversation_id, limit, offset),
        )
        rows = await cur.fetchall()

    messages = []
    for row in rows:
        is_deleted = row["deleted_at"] is not None
        messages.append(
            {
                "id": row["id"],
                "sender_id": row["sender_id"],
                "sender_nickname": row["sender_nickname"] or "탈퇴한 사용자",
                "sender_profile_image": row["sender_profile_image"] or DEFAULT_PROFILE_IMAGE,
                "content": None if is_deleted else row["content"],
                "is_read": bool(row["is_read"]),
                "created_at": format_datetime(row["created_at"]),
                "is_deleted": is_deleted,
            }
        )

    return messages, total_count


async def mark_as_read(conversation_id: int, reader_id: int) -> int:
    """대화의 상대방 메시지를 읽음 처리합니다."""
    async with transactional() as cur:
        await cur.execute(
            """
            UPDATE dm_message
            SET is_read = 1
            WHERE conversation_id = %s AND sender_id != %s AND is_read = 0 AND deleted_at IS NULL
            """,
            (conversation_id, reader_id),
        )
        return cur.rowcount


async def get_unread_conversation_count(user_id: int) -> int:
    """읽지 않은 메시지가 있는 대화 수를 반환합니다."""
    async with get_cursor() as cur:
        await cur.execute(
            """
                SELECT COUNT(DISTINCT c.id) AS cnt
                FROM dm_conversation c
                JOIN dm_message m ON m.conversation_id = c.id
                WHERE (c.participant1_id = %s OR c.participant2_id = %s)
                  AND c.deleted_at IS NULL
                  AND m.sender_id != %s
                  AND m.is_read = 0
                  AND m.deleted_at IS NULL
                """,
            (user_id, user_id, user_id),
        )
        return (await cur.fetchone())["cnt"]


async def delete_message(conversation_id: int, message_id: int, sender_id: int) -> dict | None:
    """메시지를 soft delete합니다. 본인 메시지만 삭제 가능."""
    async with transactional() as cur:
        await cur.execute(
            "SELECT id, conversation_id, sender_id, deleted_at FROM dm_message WHERE id = %s AND conversation_id = %s",
            (message_id, conversation_id),
        )
        row = await cur.fetchone()
        if not row:
            return None

        msg = {
            "id": row["id"],
            "conversation_id": row["conversation_id"],
            "sender_id": row["sender_id"],
            "already_deleted": row["deleted_at"] is not None,
        }
        if msg["sender_id"] != sender_id:
            msg["forbidden"] = True
            return msg
        if msg["already_deleted"]:
            return msg

        await cur.execute(
            "UPDATE dm_message SET deleted_at = CURRENT_TIMESTAMP WHERE id = %s",
            (message_id,),
        )
        return msg


async def delete_conversation(conversation_id: int) -> bool:
    """대화를 소프트 삭제합니다."""
    async with transactional() as cur:
        await cur.execute(
            "UPDATE dm_conversation SET deleted_at = CURRENT_TIMESTAMP WHERE id = %s AND deleted_at IS NULL",
            (conversation_id,),
        )
        return cur.rowcount > 0
