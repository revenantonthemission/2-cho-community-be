"""notification_setting_models: 알림 설정 모델.

유형별 알림 on/off 설정을 관리합니다.
행이 없는 사용자는 모든 알림 활성화(기본값)로 처리합니다.
"""

from core.database.connection import get_cursor, transactional

# 모든 알림 유형의 기본값 (행이 없을 때)
DEFAULT_SETTINGS = {
    "comment": True,
    "like": True,
    "mention": True,
    "follow": True,
    "bookmark": True,
    "reply": True,
}

# digest_frequency 기본값 (ENUM: 'daily' | 'weekly' | 'off')
DEFAULT_DIGEST_FREQUENCY = "weekly"

_TYPE_TO_COLUMN = {
    "comment": "comment_enabled",
    "like": "like_enabled",
    "mention": "mention_enabled",
    "follow": "follow_enabled",
    "bookmark": "bookmark_enabled",
    "reply": "reply_enabled",
    "badge_earned": "badge_earned_enabled",
    "level_up": "level_up_enabled",
}


async def get_notification_settings(user_id: int) -> dict[str, bool | str]:
    """사용자의 알림 설정을 조회합니다. 행이 없으면 기본값 반환."""
    async with get_cursor() as cur:
        await cur.execute(
            """
                SELECT comment_enabled, like_enabled, mention_enabled,
                       follow_enabled, bookmark_enabled, reply_enabled,
                       digest_frequency
                FROM notification_setting
                WHERE user_id = %s
                """,
            (user_id,),
        )
        row = await cur.fetchone()

    if not row:
        return {**DEFAULT_SETTINGS, "digest_frequency": DEFAULT_DIGEST_FREQUENCY}

    return {
        "comment": bool(row["comment_enabled"]),
        "like": bool(row["like_enabled"]),
        "mention": bool(row["mention_enabled"]),
        "follow": bool(row["follow_enabled"]),
        "bookmark": bool(row["bookmark_enabled"]),
        "reply": bool(row["reply_enabled"]),
        "digest_frequency": row["digest_frequency"],
    }


async def update_notification_settings(
    user_id: int,
    settings: dict[str, bool],
    digest_frequency: str | None = None,
) -> dict[str, bool | str]:
    """알림 설정을 업데이트합니다 (UPSERT).

    digest_frequency가 None이면 기존 DB 값을 유지합니다.
    신규 행 삽입 시에는 DEFAULT_DIGEST_FREQUENCY를 사용합니다.
    """
    merged = dict(DEFAULT_SETTINGS)
    for key, value in settings.items():
        if key in merged:
            merged[key] = value

    async with transactional() as cur:
        await cur.execute(
            """
            INSERT INTO notification_setting
                (user_id, comment_enabled, like_enabled, mention_enabled,
                 follow_enabled, bookmark_enabled, reply_enabled, digest_frequency)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                comment_enabled = VALUES(comment_enabled),
                like_enabled = VALUES(like_enabled),
                mention_enabled = VALUES(mention_enabled),
                follow_enabled = VALUES(follow_enabled),
                bookmark_enabled = VALUES(bookmark_enabled),
                reply_enabled = VALUES(reply_enabled),
                digest_frequency = COALESCE(%s, digest_frequency)
            """,
            (
                user_id,
                merged["comment"],
                merged["like"],
                merged["mention"],
                merged["follow"],
                merged["bookmark"],
                merged["reply"],
                # 신규 행: digest_frequency 값 또는 기본값
                digest_frequency if digest_frequency is not None else DEFAULT_DIGEST_FREQUENCY,
                # ON DUPLICATE: 전달된 값이 있으면 업데이트, 없으면 COALESCE가 기존 값 유지
                digest_frequency,
            ),
        )

    # 업데이트 후 실제 저장된 값을 반환하기 위해 DB 재조회
    return await get_notification_settings(user_id)


async def is_notification_muted(user_id: int, notification_type: str) -> bool:
    """특정 알림 유형이 음소거 상태인지 확인합니다."""
    column = _TYPE_TO_COLUMN.get(notification_type)
    if not column:
        return False

    async with get_cursor() as cur:
        await cur.execute(
            f"SELECT {column} FROM notification_setting WHERE user_id = %s",
            (user_id,),
        )
        row = await cur.fetchone()

    if not row:
        return False

    return not bool(row[column])
