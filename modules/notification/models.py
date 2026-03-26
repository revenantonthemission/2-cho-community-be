"""notification_models: 알림 관련 모델."""

import logging
from typing import Literal

from core.database.connection import get_cursor, transactional
from core.utils.formatters import format_datetime
from schemas.common import build_author_dict

logger = logging.getLogger(__name__)

NotificationType = Literal["comment", "like", "mention", "follow", "bookmark", "reply", "badge_earned", "level_up"]


async def create_notification(
    user_id: int,
    notification_type: NotificationType,
    post_id: int | None,
    actor_id: int,
    comment_id: int | None = None,
    actor_nickname: str | None = None,
) -> None:
    """알림을 생성하고 WebSocket으로 실시간 전송합니다.

    자기 자신에 대한 알림은 생성하지 않습니다.
    WebSocket 전송은 best-effort — 실패해도 DB 저장에 영향 없습니다.

    Args:
        actor_nickname: 호출부에서 이미 알고 있는 경우 전달하면 DB 조회 생략.
    """
    if user_id == actor_id:
        return

    from modules.notification.setting_models import is_notification_muted

    if await is_notification_muted(user_id, notification_type):
        return

    notification_id = None
    async with transactional() as cur:
        await cur.execute(
            "INSERT INTO notification (user_id, type, post_id, comment_id, actor_id) VALUES (%s, %s, %s, %s, %s)",
            (user_id, notification_type, post_id, comment_id, actor_id),
        )
        notification_id = cur.lastrowid

    # WebSocket 실시간 푸시 (best-effort, transactional 밖에서 실행)
    if notification_id:
        try:
            from core.utils.websocket_pusher import push_to_user

            if actor_nickname is None:
                async with get_cursor() as cur:
                    await cur.execute(
                        "SELECT nickname FROM user WHERE id = %s AND deleted_at IS NULL",
                        (actor_id,),
                    )
                    row = await cur.fetchone()
                    if row:
                        actor_nickname = row["nickname"]

            await push_to_user(
                user_id,
                {
                    "type": "notification",
                    "data": {
                        "notification_id": notification_id,
                        "notification_type": notification_type,
                        "post_id": post_id,
                        "comment_id": comment_id,
                        "actor_id": actor_id,
                        "actor_nickname": actor_nickname or "알 수 없는 사용자",
                    },
                },
            )
        except Exception:
            logger.warning(
                "WebSocket 푸시 실패 (notification_id=%d)",
                notification_id,
                exc_info=True,
            )


async def create_notifications_bulk(
    rows: list[tuple[int, str, int | None, int | None, int]],
) -> None:
    """여러 알림을 단일 INSERT로 일괄 생성합니다."""
    if not rows:
        return

    placeholders = ", ".join(["(%s, %s, %s, %s, %s)"] * len(rows))
    params: list = []
    for row in rows:
        params.extend(row)

    async with transactional() as cur:
        await cur.execute(
            f"INSERT INTO notification (user_id, type, post_id, comment_id, actor_id) VALUES {placeholders}",
            params,
        )


async def get_notifications(user_id: int, offset: int = 0, limit: int = 20) -> tuple[list[dict], int]:
    """사용자의 알림 목록과 총 개수를 반환합니다."""
    async with get_cursor() as cur:
        await cur.execute(
            "SELECT COUNT(*) AS cnt FROM notification WHERE user_id = %s",
            (user_id,),
        )
        total_count = (await cur.fetchone())["cnt"]

        await cur.execute(
            """
                SELECT n.id AS notification_id, n.type, n.post_id, n.comment_id,
                       n.is_read, n.created_at,
                       u.id AS actor_id, u.nickname AS actor_nickname,
                       u.profile_img AS actor_profile_img, u.distro AS actor_distro,
                       p.title AS post_title
                FROM notification n
                LEFT JOIN user u ON n.actor_id = u.id
                LEFT JOIN post p ON n.post_id = p.id
                WHERE n.user_id = %s
                ORDER BY n.created_at DESC
                LIMIT %s OFFSET %s
                """,
            (user_id, limit, offset),
        )
        rows = await cur.fetchall()

    notifications = []
    for row in rows:
        notifications.append(
            {
                "notification_id": row["notification_id"],
                "type": row["type"],
                "post_id": row["post_id"],
                "comment_id": row["comment_id"],
                "is_read": bool(row["is_read"]),
                "created_at": format_datetime(row["created_at"]),
                "actor": build_author_dict(
                    row["actor_id"],
                    row["actor_nickname"],
                    row["actor_profile_img"],
                    distro=row["actor_distro"],
                ),
                "post_title": row["post_title"] or "삭제된 게시글",
            }
        )

    return notifications, total_count


async def get_unread_count_with_latest(user_id: int) -> dict:
    """읽지 않은 알림 수와 최신 알림 1건을 반환합니다."""
    async with get_cursor() as cur:
        await cur.execute(
            "SELECT COUNT(*) AS cnt FROM notification WHERE user_id = %s AND is_read = 0",
            (user_id,),
        )
        count = (await cur.fetchone())["cnt"]

        latest = None
        if count > 0:
            await cur.execute(
                """
                    SELECT n.id AS notification_id, n.type, n.post_id, n.comment_id,
                           n.created_at,
                           u.nickname AS actor_nickname,
                           p.title AS post_title
                    FROM notification n
                    LEFT JOIN user u ON n.actor_id = u.id
                    LEFT JOIN post p ON n.post_id = p.id
                    WHERE n.user_id = %s AND n.is_read = 0
                    ORDER BY n.created_at DESC
                    LIMIT 1
                    """,
                (user_id,),
            )
            row = await cur.fetchone()
            if row:
                latest = {
                    "notification_id": row["notification_id"],
                    "type": row["type"],
                    "post_id": row["post_id"],
                    "comment_id": row["comment_id"],
                    "created_at": format_datetime(row["created_at"]),
                    "actor_nickname": row["actor_nickname"] or "탈퇴한 사용자",
                    "post_title": row["post_title"] or "삭제된 게시글",
                }

    return {"unread_count": count, "latest": latest}


async def mark_as_read(notification_id: int, user_id: int) -> bool:
    """알림을 읽음 처리합니다."""
    async with transactional() as cur:
        await cur.execute(
            "UPDATE notification SET is_read = 1 WHERE id = %s AND user_id = %s",
            (notification_id, user_id),
        )
        return cur.rowcount > 0


async def mark_all_as_read(user_id: int) -> int:
    """모든 알림을 읽음 처리합니다."""
    async with transactional() as cur:
        await cur.execute(
            "UPDATE notification SET is_read = 1 WHERE user_id = %s AND is_read = 0",
            (user_id,),
        )
        return cur.rowcount


async def delete_notification(notification_id: int, user_id: int) -> bool:
    """알림을 삭제합니다."""
    async with transactional() as cur:
        await cur.execute(
            "DELETE FROM notification WHERE id = %s AND user_id = %s",
            (notification_id, user_id),
        )
        return cur.rowcount > 0
