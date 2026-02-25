"""auth: FastAPI 의존성 주입을 위한 인증 모듈.

JWT Bearer Token 기반 사용자 인증 및 권한 확인 기능을 제공합니다.
"""

from datetime import datetime, timezone

from fastapi import HTTPException, Request, status

from models import user_models
from models.user_models import User
from utils.jwt_utils import decode_access_token


def _extract_bearer_token(request: Request) -> str | None:
    """Authorization 헤더에서 Bearer 토큰을 추출합니다."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    token = auth_header[len("Bearer "):]
    return token if token else None


async def _validate_token(request: Request) -> User | None:
    """Access Token을 검증하고 사용자를 반환합니다.

    Args:
        request: FastAPI Request 객체.

    Returns:
        유효한 사용자 객체, 토큰이 없으면 None.

    Raises:
        HTTPException 401: 토큰이 있으나 유효하지 않은 경우.
    """
    raw_token = _extract_bearer_token(request)
    if not raw_token:
        return None

    # decode_access_token은 만료/위조 시 HTTPException 401을 raise함
    payload = decode_access_token(raw_token)

    user_id = int(payload["sub"])
    user = await user_models.get_user_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "unauthorized",
                "timestamp": datetime.now(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
            },
        )

    return user


async def get_current_user(request: Request) -> User:
    """Bearer 토큰에서 현재 사용자를 추출하고 검증합니다.

    Args:
        request: FastAPI Request 객체.

    Returns:
        인증된 사용자 객체.

    Raises:
        HTTPException: 토큰이 없거나 유효하지 않으면 401.
    """
    user = await _validate_token(request)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "unauthorized",
                "timestamp": datetime.now(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
            },
        )

    return user


async def get_optional_user(request: Request) -> User | None:
    """선택적으로 현재 사용자를 추출합니다.

    인증되지 않은 요청에서도 에러를 발생시키지 않고 None을 반환합니다.

    Args:
        request: FastAPI Request 객체.

    Returns:
        인증된 사용자 객체, 인증되지 않은 경우 None.
    """
    try:
        return await _validate_token(request)
    except HTTPException:
        return None
