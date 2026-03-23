"""token_models: JWT Refresh Token CRUD 모듈.

refresh_token 테이블의 CRUD 기능과 만료 토큰 정리 기능을 제공합니다.
"""

import logging
from datetime import UTC, datetime

from database.connection import transactional
from utils.jwt_utils import hash_refresh_token

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
    """Refresh Token 해시를 DB에 저장합니다.

    Args:
        user_id: 사용자 ID.
        raw_token: 클라이언트에 전달된 원본 Refresh Token.
        expires_at: 만료 시간.
    """
    token_hash = hash_refresh_token(raw_token)
    async with transactional() as cur:
        await cur.execute(_INSERT_TOKEN_SQL, (user_id, token_hash, expires_at))


async def get_refresh_token(raw_token: str) -> dict | None:
    """Raw Refresh Token으로 토큰 레코드를 조회합니다.

    만료된 토큰은 삭제 후 None 반환.
    SELECT FOR UPDATE + 조건부 DELETE를 트랜잭션으로 묶어 원자성을 보장합니다.

    Args:
        raw_token: 원본 Refresh Token.

    Returns:
        {"user_id": int, "expires_at": datetime} 또는 None.
    """
    token_hash = hash_refresh_token(raw_token)
    async with transactional() as cur:
        # FOR UPDATE: 동일 토큰에 대한 동시 요청의 토큰 재사용(replay) 방지
        await cur.execute(_SELECT_TOKEN_SQL, (token_hash,))
        row = await cur.fetchone()

        if not row:
            return None

        user_id, expires_at = row[0], _normalize_expires_at(row[1])

        if expires_at < datetime.now(UTC):
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
    """기존 Refresh Token 검증·삭제·신규 토큰 삽입을 단일 트랜잭션으로 수행합니다.

    SELECT ... FOR UPDATE로 행 잠금 후 유효성을 검증하고,
    DELETE + INSERT를 같은 트랜잭션 내에서 완료합니다.
    이를 통해 동시 갱신 요청이 모두 성공하는 토큰 팬아웃(fan-out)을 방지합니다.

    Args:
        old_token_hash: 교체할 기존 토큰의 SHA-256 해시.
        user_id: 토큰 소유 사용자 ID (소유자 일치 확인에 사용).
        new_token_hash: 저장할 새 토큰의 SHA-256 해시.
        new_expires_at: 새 토큰의 만료 시간.

    Returns:
        성공 시 user_id, 토큰이 유효하지 않거나 만료된 경우 None.
    """
    async with transactional() as cur:
        # FOR UPDATE: 동일 토큰에 대한 동시 요청이 함께 진입하지 못하도록 행 잠금
        await cur.execute(_SELECT_TOKEN_SQL, (old_token_hash,))
        row = await cur.fetchone()

        if not row:
            return None

        db_user_id, expires_at = row[0], _normalize_expires_at(row[1])

        # 만료 여부 및 소유자 일치 확인
        if expires_at < datetime.now(UTC) or db_user_id != user_id:
            return None

        # 기존 토큰 삭제 후 새 토큰 삽입 — 같은 트랜잭션에서 수행
        await cur.execute(
            "DELETE FROM refresh_token WHERE token_hash = %s",
            (old_token_hash,),
        )
        await cur.execute(_INSERT_TOKEN_SQL, (user_id, new_token_hash, new_expires_at))

    return user_id


async def delete_user_refresh_tokens(user_id: int) -> None:
    """특정 사용자의 모든 Refresh Token을 삭제합니다 (회원 탈퇴/강제 로그아웃).

    Args:
        user_id: 사용자 ID.
    """
    async with transactional() as cur:
        await cur.execute(
            "DELETE FROM refresh_token WHERE user_id = %s",
            (user_id,),
        )


async def cleanup_expired_tokens() -> int:
    """만료된 Refresh Token을 일괄 삭제합니다.

    Returns:
        삭제된 토큰 수.
    """
    async with transactional() as cur:
        await cur.execute(
            "DELETE FROM refresh_token WHERE expires_at < %s",
            (datetime.now(UTC),),
        )
        deleted = cur.rowcount
    logger.info("만료된 Refresh Token %d개 정리 완료", deleted)
    return deleted
