"""verification_models: 이메일 인증 토큰 CRUD 모듈.

email_verification 테이블의 토큰 생성, 검증, 만료 토큰 정리 기능을 제공합니다.
SHA-256 해시 패턴은 refresh_token과 동일합니다.
"""

import logging
import secrets
from datetime import UTC, datetime, timedelta

from core.database.connection import get_cursor, transactional
from core.utils.jwt_utils import hash_refresh_token

logger = logging.getLogger("api")

_VERIFICATION_EXPIRE_HOURS = 24


async def create_verification_token(user_id: int) -> str:
    """이메일 인증 토큰을 생성하고 SHA-256 해시를 DB에 저장합니다."""
    raw_token = secrets.token_urlsafe(64)
    token_hash = hash_refresh_token(raw_token)
    expires_at = datetime.now(UTC) + timedelta(hours=_VERIFICATION_EXPIRE_HOURS)

    async with transactional() as cur:
        await cur.execute(
            "REPLACE INTO email_verification (user_id, token_hash, expires_at) VALUES (%s, %s, %s)",
            (user_id, token_hash, expires_at),
        )

    return raw_token


async def verify_token(raw_token: str) -> int | None:
    """인증 토큰을 검증하고 성공 시 email_verified를 갱신합니다."""
    token_hash = hash_refresh_token(raw_token)

    async with transactional() as cur:
        await cur.execute(
            "SELECT user_id, expires_at FROM email_verification WHERE token_hash = %s FOR UPDATE",
            (token_hash,),
        )
        row = await cur.fetchone()

        if not row:
            return None

        user_id, expires_at = row["user_id"], row["expires_at"]

        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)

        if expires_at < datetime.now(UTC):
            await cur.execute(
                "DELETE FROM email_verification WHERE token_hash = %s",
                (token_hash,),
            )
            return None

        await cur.execute(
            "DELETE FROM email_verification WHERE token_hash = %s",
            (token_hash,),
        )
        await cur.execute(
            "UPDATE user SET email_verified = 1 WHERE id = %s",
            (user_id,),
        )

    return user_id


async def cleanup_expired_verification_tokens() -> int:
    """만료된 이메일 인증 토큰을 일괄 삭제합니다."""
    async with get_cursor() as cur:
        await cur.execute(
            "DELETE FROM email_verification WHERE expires_at < %s",
            (datetime.now(UTC),),
        )
        deleted = cur.rowcount
    logger.info("만료된 이메일 인증 토큰 %d개 정리 완료", deleted)
    return deleted
