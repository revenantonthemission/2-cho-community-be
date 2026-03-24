"""suspension_models: 계정 정지 관련 데이터 모델."""

from datetime import UTC, datetime, timedelta

from core.database.connection import transactional


async def suspend_user(
    user_id: int,
    duration_days: int,
    reason: str,
) -> bool:
    """사용자를 기간 정지합니다.

    Args:
        user_id: 정지할 사용자 ID.
        duration_days: 정지 기간 (일).
        reason: 정지 사유.

    Returns:
        정지 성공 여부.
    """
    suspended_until = datetime.now(UTC) + timedelta(days=duration_days)

    async with transactional() as cur:
        await cur.execute(
            """
            UPDATE user
            SET suspended_until = %s, suspended_reason = %s
            WHERE id = %s AND deleted_at IS NULL
            """,
            (suspended_until, reason, user_id),
        )
        return cur.rowcount > 0


async def unsuspend_user(user_id: int) -> bool:
    """사용자 정지를 해제합니다.

    Args:
        user_id: 정지 해제할 사용자 ID.

    Returns:
        해제 성공 여부.
    """
    async with transactional() as cur:
        await cur.execute(
            """
            UPDATE user
            SET suspended_until = NULL, suspended_reason = NULL
            WHERE id = %s AND deleted_at IS NULL AND suspended_until IS NOT NULL
            """,
            (user_id,),
        )
        return cur.rowcount > 0
