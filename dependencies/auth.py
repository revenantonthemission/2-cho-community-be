"""auth: FastAPI 의존성 주입을 위한 인증 모듈.

JWT Bearer Token 기반 사용자 인증 및 권한 확인 기능을 제공합니다.
"""

import hmac
from datetime import UTC, datetime

from fastapi import Depends, HTTPException, Request, status

from core.config import settings
from dependencies.request_context import get_request_timestamp
from models import user_models
from models.user_models import User
from utils.jwt_utils import decode_access_token


def _extract_bearer_token(request: Request) -> str | None:
    """Authorization 헤더에서 Bearer 토큰을 추출합니다."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    token = auth_header[len("Bearer ") :]
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
                "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )

    # 정지된 사용자는 API 접근 차단
    if user.is_suspended:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "account_suspended",
                "message": "계정이 정지되었습니다.",
                "suspended_until": (
                    user.suspended_until.strftime("%Y-%m-%dT%H:%M:%SZ") if user.suspended_until else None
                ),
                "suspended_reason": user.suspended_reason,
                "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
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
                "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )

    return user


async def get_optional_user(request: Request) -> User | None:
    """선택적으로 현재 사용자를 추출합니다.

    인증되지 않은 요청에서도 에러를 발생시키지 않고 None을 반환합니다.
    정지된 사용자의 403 에러는 전파합니다.

    Args:
        request: FastAPI Request 객체.

    Returns:
        인증된 사용자 객체, 인증되지 않은 경우 None.
    """
    try:
        return await _validate_token(request)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_403_FORBIDDEN:
            raise  # 정지된 사용자 에러는 전파
        return None


async def require_admin(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> User:
    """관리자 권한을 요구합니다.

    Args:
        request: FastAPI Request 객체.
        current_user: 현재 인증된 사용자 (get_current_user 의존성).

    Returns:
        관리자 사용자 객체.

    Raises:
        HTTPException: 관리자가 아닌 경우 403.
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "admin_required",
                "message": "관리자 권한이 필요합니다.",
                "timestamp": get_request_timestamp(request),
            },
        )
    return current_user


async def require_verified_email(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> User:
    """이메일 인증이 완료된 사용자만 허용합니다.

    미인증 시 403 Forbidden을 발생시킵니다.

    Args:
        request: FastAPI Request 객체.
        current_user: 현재 인증된 사용자 (get_current_user 의존성).

    Returns:
        이메일 인증이 완료된 사용자 객체.

    Raises:
        HTTPException: 이메일 미인증 시 403.
    """
    if settings.REQUIRE_EMAIL_VERIFICATION and not current_user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "email_not_verified",
                "message": "이메일 인증 후 이용 가능합니다.",
                "timestamp": get_request_timestamp(request),
            },
        )
    return current_user


def _is_valid_internal_key(request: Request) -> bool:
    """X-Internal-Key 헤더가 유효한 내부 API 키인지 확인합니다."""
    if not settings.INTERNAL_API_KEY:
        return False
    key = request.headers.get("X-Internal-Key", "")
    # 타이밍 공격 방지: 상수 시간 비교
    return hmac.compare_digest(key, settings.INTERNAL_API_KEY)


async def require_internal(request: Request) -> None:
    """내부 API 호출 인증을 요구합니다.

    EventBridge 등 자동화된 호출에서 X-Internal-Key 헤더로 인증합니다.

    Args:
        request: FastAPI Request 객체.

    Raises:
        HTTPException: 키가 없거나 유효하지 않으면 403.
    """
    if not _is_valid_internal_key(request):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "forbidden",
                "message": "유효한 내부 API 키가 필요합니다.",
                "timestamp": get_request_timestamp(request),
            },
        )


async def require_admin_or_internal(request: Request) -> User | None:
    """관리자 JWT 또는 내부 API 키 인증을 요구합니다.

    관리자 UI에서는 JWT로, EventBridge 등 자동화에서는 X-Internal-Key로 인증합니다.
    내부 키 인증 시 사용자 객체 없이 None을 반환합니다.

    Args:
        request: FastAPI Request 객체.

    Returns:
        관리자 사용자 객체 또는 None (내부 키 인증 시).

    Raises:
        HTTPException: 두 인증 모두 실패 시 403.
    """
    # 내부 API 키 우선 확인
    if _is_valid_internal_key(request):
        return None

    # JWT 관리자 인증 시도
    try:
        user = await _validate_token(request)
    except HTTPException as e:
        import logging

        logging.getLogger(__name__).debug(
            "JWT 인증 실패 (status=%d), 내부 키도 없음",
            e.status_code,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "forbidden",
                "message": "관리자 권한 또는 내부 API 키가 필요합니다.",
                "timestamp": get_request_timestamp(request),
            },
        ) from e

    if not user or not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "forbidden",
                "message": "관리자 권한 또는 내부 API 키가 필요합니다.",
                "timestamp": get_request_timestamp(request),
            },
        )

    return user
