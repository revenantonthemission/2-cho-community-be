"""verification_models: 이메일 인증 토큰 CRUD 모듈.

email_verification 테이블의 토큰 생성, 검증, 만료 토큰 정리 기능을 제공합니다.
SHA-256 해시 패턴은 refresh_token과 동일합니다.
"""

import logging
import secrets
from datetime import datetime, timedelta, timezone

from database.connection import get_connection, transactional
from utils.jwt_utils import hash_refresh_token

logger = logging.getLogger("api")

_VERIFICATION_EXPIRE_HOURS = 24


async def create_verification_token(user_id: int) -> str:
    """이메일 인증 토큰을 생성하고 SHA-256 해시를 DB에 저장합니다.

    user_id에 UNIQUE 제약이 있으므로 REPLACE INTO로 기존 토큰을 덮어씁니다.

    Args:
        user_id: 사용자 ID.

    Returns:
        클라이언트에 전달할 원본(raw) 토큰 문자열.
    """
    raw_token = secrets.token_urlsafe(64)
    token_hash = hash_refresh_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=_VERIFICATION_EXPIRE_HOURS)

    async with transactional() as cur:
        await cur.execute(
            """
            REPLACE INTO email_verification (user_id, token_hash, expires_at)
            VALUES (%s, %s, %s)
            """,
            (user_id, token_hash, expires_at),
        )

    return raw_token


async def verify_token(raw_token: str) -> int | None:
    """인증 토큰을 검증하고 성공 시 email_verified를 갱신합니다.

    해시 매칭 + 만료 시간 확인 후, 단일 트랜잭션 내에서
    토큰 삭제 + user.email_verified=1 업데이트를 수행합니다.

    Args:
        raw_token: 클라이언트로부터 받은 원본 토큰.

    Returns:
        인증 성공 시 user_id, 실패 시 None.
    """
    token_hash = hash_refresh_token(raw_token)

    async with transactional() as cur:
        await cur.execute(
            """
            SELECT user_id, expires_at
            FROM email_verification
            WHERE token_hash = %s
            """,
            (token_hash,),
        )
        row = await cur.fetchone()

        if not row:
            return None

        user_id, expires_at = row[0], row[1]

        # MySQL TIMESTAMP는 timezone-naive로 반환될 수 있음
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if expires_at < datetime.now(timezone.utc):
            # 만료된 토큰 삭제
            await cur.execute(
                "DELETE FROM email_verification WHERE token_hash = %s",
                (token_hash,),
            )
            return None

        # 토큰 삭제 + 이메일 인증 완료를 같은 트랜잭션에서 수행
        await cur.execute(
            "DELETE FROM email_verification WHERE token_hash = %s",
            (token_hash,),
        )
        await cur.execute(
            "UPDATE user SET email_verified = 1 WHERE id = %s",
            (user_id,),
        )

    return user_id


async def is_user_verified(user_id: int) -> bool:
    """사용자의 이메일 인증 여부를 확인합니다.

    Args:
        user_id: 사용자 ID.

    Returns:
        인증 완료 시 True, 미인증 또는 사용자 미존재 시 False.
    """
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT email_verified FROM user WHERE id = %s AND deleted_at IS NULL",
                (user_id,),
            )
            row = await cur.fetchone()
            return bool(row[0]) if row else False


async def cleanup_expired_verification_tokens() -> int:
    """만료된 이메일 인증 토큰을 일괄 삭제합니다.

    Returns:
        삭제된 토큰 수.
    """
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM email_verification WHERE expires_at < %s",
                (datetime.now(timezone.utc),),
            )
            deleted = cur.rowcount
    logger.info("만료된 이메일 인증 토큰 %d개 정리 완료", deleted)
    return deleted
