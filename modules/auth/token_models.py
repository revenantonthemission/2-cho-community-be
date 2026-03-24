"""token_models: JWT Refresh Token CRUD 모듈.

refresh_token 테이블의 CRUD 기능과 만료 토큰 정리 기능을 제공합니다.
"""

import logging
from datetime import UTC, datetime

from core.database.connection import transactional
from core.utils.jwt_utils import hash_refresh_token

logger = logging.getLogger("api")

# 공통 SELECT 필드 — 여러 함수에서 동일한 컬럼을 조회하므로 중복 방지
_SELECT_TOKEN_SQL = """
    SELECT user_id, expires_at
    FROM refresh_token
    WHERE token_hash = %s
    FOR UPDATE
"""

# 공통 INSERT SQL — create/rotate에서 동일한 형태로 토큰을 삽입
_INSERT_TOKEN_SQL = """
    INSERT INTO refresh_token (user_id, token_hash, expires_at)
    VALUES (%s, %s, %s)
"""


def _normalize_expires_at(expires_at: datetime) -> datetime:
    """MySQL TIMESTAMP가 timezone-naive로 반환될 경우 UTC로 보정합니다."""
    if expires_at.tzinfo is None:
        return expires_at.replace(tzinfo=UTC)
    return expires_at


async def create_refresh_token(user_id: int, raw_token: str, expires_at: datetime) -> None:
    """Refresh Token 해시를 DB에 저장합니다."""
    token_hash = hash_refresh_token(raw_token)
    async with transactional() as cur:
        await cur.execute(_INSERT_TOKEN_SQL, (user_id, token_hash, expires_at))


async def get_refresh_token(raw_token: str) -> dict | None:
    """Raw Refresh Token으로 토큰 레코드를 조회합니다. 만료된 토큰은 삭제 후 None 반환."""
    token_hash = hash_refresh_token(raw_token)
    async with transactional() as cur:
        await cur.execute(_SELECT_TOKEN_SQL, (token_hash,))
        row = await cur.fetchone()

        if not row:
            return None

        user_id, expires_at = row["user_id"], _normalize_expires_at(row["expires_at"])

        if expires_at < datetime.now(UTC):
            await cur.execute(
                "DELETE FROM refresh_token WHERE token_hash = %s",
                (token_hash,),
            )
            return None

        return {"user_id": user_id, "expires_at": expires_at}


async def delete_refresh_token(raw_token: str) -> None:
    """특정 Refresh Token을 삭제합니다 (로그아웃)."""
    token_hash = hash_refresh_token(raw_token)
    async with transactional() as cur:
        await cur.execute(
            "DELETE FROM refresh_token WHERE token_hash = %s",
            (token_hash,),
        )


async def atomic_rotate_refresh_token(
    old_token_hash: str,
    user_id: int,
    new_token_hash: str,
    new_expires_at: datetime,
) -> int | None:
    """기존 Refresh Token 검증·삭제·신규 토큰 삽입을 단일 트랜잭션으로 수행합니다."""
    async with transactional() as cur:
        await cur.execute(_SELECT_TOKEN_SQL, (old_token_hash,))
        row = await cur.fetchone()

        if not row:
            return None

        db_user_id, expires_at = row["user_id"], _normalize_expires_at(row["expires_at"])

        if expires_at < datetime.now(UTC) or db_user_id != user_id:
            return None

        await cur.execute(
            "DELETE FROM refresh_token WHERE token_hash = %s",
            (old_token_hash,),
        )
        await cur.execute(_INSERT_TOKEN_SQL, (user_id, new_token_hash, new_expires_at))

    return user_id


async def cleanup_expired_tokens() -> int:
    """만료된 Refresh Token을 일괄 삭제합니다."""
    async with transactional() as cur:
        await cur.execute(
            "DELETE FROM refresh_token WHERE expires_at < %s",
            (datetime.now(UTC),),
        )
        deleted = cur.rowcount
    logger.info("만료된 Refresh Token %d개 정리 완료", deleted)
    return deleted
