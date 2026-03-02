"""notification_models: 알림 관련 모델."""

from typing import Literal

from database.connection import get_connection, transactional
from schemas.common import build_author_dict
from utils.formatters import format_datetime

NotificationType = Literal["comment", "like"]


async def create_notification(
    user_id: int,
    notification_type: NotificationType,
    post_id: int,
    actor_id: int,
    comment_id: int | None = None,
) -> None:
    """알림을 생성합니다. 자기 자신에 대한 알림은 생성하지 않습니다."""
    if user_id == actor_id:
        return

    async with transactional() as cur:
        await cur.execute(
            """
            INSERT INTO notification (user_id, type, post_id, comment_id, actor_id)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (user_id, notification_type, post_id, comment_id, actor_id),
        )


async def get_notifications(
    user_id: int, offset: int = 0, limit: int = 20
) -> tuple[list[dict], int]:
    """사용자의 알림 목록과 총 개수를 반환합니다."""
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            # 총 개수
            await cur.execute(
                "SELECT COUNT(*) FROM notification WHERE user_id = %s",
                (user_id,),
            )
            total_count = (await cur.fetchone())[0]

            # 알림 목록 (actor + post 정보 JOIN)
            await cur.execute(
                """
                SELECT n.id, n.type, n.post_id, n.comment_id, n.is_read, n.created_at,
                       u.id AS actor_id, u.nickname AS actor_nickname,
                       u.profile_img AS actor_profile_img,
                       p.title AS post_title
                FROM notification n
                -- 삭제된 사용자/게시글도 포함 (알림에서 "탈퇴한 사용자", "삭제된 게시글"로 표시)
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
        notifications.append({
            "notification_id": row[0],
            "type": row[1],
            "post_id": row[2],
            "comment_id": row[3],
            "is_read": bool(row[4]),
            "created_at": format_datetime(row[5]),
            "actor": build_author_dict(row[6], row[7], row[8]),
            "post_title": row[9] or "삭제된 게시글",
        })

    return notifications, total_count


async def get_unread_count(user_id: int) -> int:
    """읽지 않은 알림 수를 반환합니다."""
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT COUNT(*) FROM notification WHERE user_id = %s AND is_read = 0",
                (user_id,),
            )
            return (await cur.fetchone())[0]


async def mark_as_read(notification_id: int, user_id: int) -> bool:
    """알림을 읽음 처리합니다. 성공 시 True."""
    async with transactional() as cur:
        await cur.execute(
            "UPDATE notification SET is_read = 1 WHERE id = %s AND user_id = %s",
            (notification_id, user_id),
        )
        return cur.rowcount > 0


async def mark_all_as_read(user_id: int) -> int:
    """모든 알림을 읽음 처리합니다. 변경된 행 수를 반환합니다."""
    async with transactional() as cur:
        await cur.execute(
            "UPDATE notification SET is_read = 1 WHERE user_id = %s AND is_read = 0",
            (user_id,),
        )
        return cur.rowcount


async def delete_notification(notification_id: int, user_id: int) -> bool:
    """알림을 삭제합니다. 성공 시 True."""
    async with transactional() as cur:
        await cur.execute(
            "DELETE FROM notification WHERE id = %s AND user_id = %s",
            (notification_id, user_id),
        )
        return cur.rowcount > 0
