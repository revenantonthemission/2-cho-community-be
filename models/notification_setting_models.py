"""notification_setting_models: 알림 설정 모델.

유형별 알림 on/off 설정을 관리합니다.
행이 없는 사용자는 모든 알림 활성화(기본값)로 처리합니다.
"""

from database.connection import get_connection, transactional

# 모든 알림 유형의 기본값 (행이 없을 때)
DEFAULT_SETTINGS = {
    "comment": True,
    "like": True,
    "mention": True,
    "follow": True,
    "bookmark": True,
}

_TYPE_TO_COLUMN = {
    "comment": "comment_enabled",
    "like": "like_enabled",
    "mention": "mention_enabled",
    "follow": "follow_enabled",
    "bookmark": "bookmark_enabled",
}


async def get_notification_settings(user_id: int) -> dict[str, bool]:
    """사용자의 알림 설정을 조회합니다. 행이 없으면 기본값 반환."""
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
                SELECT comment_enabled, like_enabled, mention_enabled,
                       follow_enabled, bookmark_enabled
                FROM notification_setting
                WHERE user_id = %s
                """,
            (user_id,),
        )
        row = await cur.fetchone()

    if not row:
        return dict(DEFAULT_SETTINGS)

    return {
        "comment": bool(row[0]),
        "like": bool(row[1]),
        "mention": bool(row[2]),
        "follow": bool(row[3]),
        "bookmark": bool(row[4]),
    }


async def update_notification_settings(user_id: int, settings: dict[str, bool]) -> dict[str, bool]:
    """알림 설정을 업데이트합니다 (UPSERT)."""
    merged = dict(DEFAULT_SETTINGS)
    for key, value in settings.items():
        if key in merged:
            merged[key] = value

    async with transactional() as cur:
        await cur.execute(
            """
            INSERT INTO notification_setting
                (user_id, comment_enabled, like_enabled, mention_enabled,
                 follow_enabled, bookmark_enabled)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                comment_enabled = VALUES(comment_enabled),
                like_enabled = VALUES(like_enabled),
                mention_enabled = VALUES(mention_enabled),
                follow_enabled = VALUES(follow_enabled),
                bookmark_enabled = VALUES(bookmark_enabled)
            """,
            (
                user_id,
                merged["comment"],
                merged["like"],
                merged["mention"],
                merged["follow"],
                merged["bookmark"],
            ),
        )

    return merged


async def is_notification_muted(user_id: int, notification_type: str) -> bool:
    """특정 알림 유형이 음소거 상태인지 확인합니다."""
    column = _TYPE_TO_COLUMN.get(notification_type)
    if not column:
        return False

    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"SELECT {column} FROM notification_setting WHERE user_id = %s",
            (user_id,),
        )
        row = await cur.fetchone()

    # 행이 없으면 기본 활성화
    if not row:
        return False

    return not bool(row[0])
