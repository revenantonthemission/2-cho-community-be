"""token_models: JWT Refresh Token CRUD 모듈.

refresh_token 테이블의 CRUD 기능과 만료 토큰 정리 기능을 제공합니다.
"""

import logging
from datetime import datetime, timezone

from database.connection import get_connection, transactional
from utils.jwt_utils import hash_refresh_token


async def create_refresh_token(
    user_id: int, raw_token: str, expires_at: datetime
) -> None:
    """Refresh Token 해시를 DB에 저장합니다.

    Args:
        user_id: 사용자 ID.
        raw_token: 클라이언트에 전달된 원본 Refresh Token.
        expires_at: 만료 시간.
    """
    token_hash = hash_refresh_token(raw_token)
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO refresh_token (user_id, token_hash, expires_at)
                VALUES (%s, %s, %s)
                """,
                (user_id, token_hash, expires_at),
            )


async def get_refresh_token(raw_token: str) -> dict | None:
    """Raw Refresh Token으로 토큰 레코드를 조회합니다.

    만료된 토큰은 삭제 후 None 반환.
    SELECT + 조건부 DELETE를 트랜잭션으로 묶어 원자성을 보장합니다.

    Args:
        raw_token: 원본 Refresh Token.

    Returns:
        {"user_id": int, "expires_at": datetime} 또는 None.
    """
    token_hash = hash_refresh_token(raw_token)
    async with transactional() as cur:
        await cur.execute(
            """
            SELECT user_id, expires_at
            FROM refresh_token
            WHERE token_hash = %s
            """,
            (token_hash,),
        )
        row = await cur.fetchone()

        if not row:
            return None

        user_id, expires_at = row[0], row[1]

        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if expires_at < datetime.now(timezone.utc):
            await cur.execute(
                "DELETE FROM refresh_token WHERE token_hash = %s",
                (token_hash,),
            )
            return None

        return {"user_id": user_id, "expires_at": expires_at}


async def delete_refresh_token(raw_token: str) -> None:
    """특정 Refresh Token을 삭제합니다 (로그아웃).

    Args:
        raw_token: 원본 Refresh Token.
    """
    token_hash = hash_refresh_token(raw_token)
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM refresh_token WHERE token_hash = %s",
                (token_hash,),
            )


async def rotate_refresh_token(
    old_raw_token: str,
    new_raw_token: str,
    user_id: int,
    new_expires_at: datetime,
) -> None:
    """기존 Refresh Token을 삭제하고 새 토큰을 저장합니다 (원자적 토큰 회전).

    단일 트랜잭션으로 DELETE + INSERT를 묶어
    크래시/동시 요청 시 불일치를 방지합니다.

    Args:
        old_raw_token: 삭제할 기존 Refresh Token.
        new_raw_token: 저장할 새 Refresh Token.
        user_id: 사용자 ID.
        new_expires_at: 새 토큰의 만료 시간.
    """
    old_hash = hash_refresh_token(old_raw_token)
    new_hash = hash_refresh_token(new_raw_token)
    async with transactional() as cur:
        await cur.execute(
            "DELETE FROM refresh_token WHERE token_hash = %s",
            (old_hash,),
        )
        await cur.execute(
            """
            INSERT INTO refresh_token (user_id, token_hash, expires_at)
            VALUES (%s, %s, %s)
            """,
            (user_id, new_hash, new_expires_at),
        )


async def delete_user_refresh_tokens(user_id: int) -> None:
    """특정 사용자의 모든 Refresh Token을 삭제합니다 (회원 탈퇴/강제 로그아웃).

    Args:
        user_id: 사용자 ID.
    """
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM refresh_token WHERE user_id = %s",
                (user_id,),
            )


logger = logging.getLogger("api")


async def cleanup_expired_tokens() -> int:
    """만료된 Refresh Token을 일괄 삭제합니다.

    Returns:
        삭제된 토큰 수.
    """
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM refresh_token WHERE expires_at < %s",
                (datetime.now(timezone.utc),),
            )
            deleted = cur.rowcount
    logger.info("만료된 Refresh Token %d개 정리 완료", deleted)
    return deleted
