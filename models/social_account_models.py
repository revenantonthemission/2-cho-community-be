"""social_account_models: 소셜 계정 연동 모델."""

from database.connection import get_connection, transactional


async def get_by_provider(provider: str, provider_id: str) -> dict | None:
    """소셜 제공자 + ID로 연동 계정을 조회합니다."""
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id, user_id, provider, provider_id, provider_email "
                "FROM social_account WHERE provider = %s AND provider_id = %s",
                (provider, provider_id),
            )
            row = await cur.fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "user_id": row[1],
        "provider": row[2],
        "provider_id": row[3],
        "provider_email": row[4],
    }


async def create(
    user_id: int,
    provider: str,
    provider_id: str,
    provider_email: str | None = None,
) -> int:
    """소셜 계정 연동을 생성합니다."""
    async with transactional() as cur:
        await cur.execute(
            "INSERT INTO social_account (user_id, provider, provider_id, provider_email) "
            "VALUES (%s, %s, %s, %s)",
            (user_id, provider, provider_id, provider_email),
        )
        return cur.lastrowid


async def get_by_user_id(user_id: int) -> list[dict]:
    """사용자의 소셜 계정 목록을 조회합니다."""
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id, provider, provider_id, provider_email, created_at "
                "FROM social_account WHERE user_id = %s",
                (user_id,),
            )
            rows = await cur.fetchall()
    return [
        {
            "id": r[0],
            "provider": r[1],
            "provider_id": r[2],
            "provider_email": r[3],
            "created_at": r[4],
        }
        for r in rows
    ]
