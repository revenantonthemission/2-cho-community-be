"""jwt_utils: JWT 생성 및 검증 유틸리티 모듈.

Access Token (HS256 JWT) / Refresh Token (opaque random) 발급 및 검증.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import HTTPException, status

from core.config import settings

_JWT_ALGORITHM = "HS256"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(user_id: int) -> str:
    """Access Token을 생성합니다 (설정된 만료 시간 적용).

    PII(이메일, 닉네임 등)는 포함하지 않습니다.
    JWT는 암호화되지 않으므로, 식별에 필요한 최소 정보(sub)만 담습니다.
    """
    now = _now_utc()
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int(
            (now + timedelta(minutes=settings.JWT_ACCESS_EXPIRE_MINUTES)).timestamp()
        ),
        "type": "access",
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=_JWT_ALGORITHM)


def create_refresh_token() -> str:
    """Refresh Token을 생성합니다 (opaque random string).

    JWT가 아닌 고강도 무작위 바이트로 생성합니다.
    DB에서 revocation을 관리하므로 self-contained일 필요 없습니다.
    """
    return secrets.token_urlsafe(64)


def hash_refresh_token(raw_token: str) -> str:
    """Refresh Token의 SHA-256 해시를 반환합니다 (DB 저장용)."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


def decode_access_token(token: str) -> dict:
    """Access Token을 디코딩하고 클레임을 반환합니다.

    Raises:
        HTTPException 401: 토큰이 만료되었거나 유효하지 않은 경우.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[_JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "token_expired",
                "timestamp": _now_utc().strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "token_invalid",
                "timestamp": _now_utc().strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "token_invalid",
                "timestamp": _now_utc().strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )

    # sub 클레임 존재 및 정수 변환 가능 여부 검증
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "token_invalid",
                "timestamp": _now_utc().strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )
    try:
        int(sub)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "token_invalid",
                "timestamp": _now_utc().strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )

    return payload
