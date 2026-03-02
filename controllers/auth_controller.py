"""auth_controller: 인증 관련 컨트롤러 모듈.

JWT 기반 로그인, 로그아웃, 토큰 갱신, 사용자 인증 상태 확인,
이메일 인증 등의 기능을 제공합니다.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request, Response, status

from core.config import settings
from dependencies.request_context import get_request_timestamp
from models import token_models, user_models, verification_models
from models.user_models import User
from schemas.auth_schemas import LoginRequest
from schemas.common import create_response, serialize_user
from utils.email import send_email
from utils.exceptions import bad_request_error
from utils.jwt_utils import create_access_token, create_refresh_token
from utils.password import verify_password

logger = logging.getLogger(__name__)

_REFRESH_COOKIE = "refresh_token"

# 타이밍 공격 방지: 존재하지 않는 사용자에 대해서도 bcrypt 비교를 수행하여 응답 시간 차이로
# 사용자 존재 여부가 노출되지 않도록 함
_TIMING_ATTACK_DUMMY_HASH = (
    "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxwKc.60VF.wdz.xGto8.H82o.f2y"
)


def _set_refresh_cookie(response: Response, token: str) -> None:
    """응답에 HttpOnly Refresh Token 쿠키를 설정합니다."""
    response.set_cookie(
        key=_REFRESH_COOKIE,
        value=token,
        httponly=True,
        secure=settings.HTTPS_ONLY,
        samesite="lax",
        max_age=settings.JWT_REFRESH_EXPIRE_DAYS * 24 * 60 * 60,
        path="/v1/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    """응답에서 Refresh Token 쿠키를 삭제합니다."""
    response.delete_cookie(
        key=_REFRESH_COOKIE,
        path="/v1/auth",
        httponly=True,
        secure=settings.HTTPS_ONLY,
        samesite="lax",
    )


async def login(
    credentials: LoginRequest, request: Request, response: Response
) -> dict:
    """이메일과 비밀번호를 사용하여 로그인합니다.

    성공 시 응답 body에 access_token과 사용자 정보를 반환하고,
    HttpOnly 쿠키로 refresh_token을 설정합니다.

    Args:
        credentials: 로그인 자격 증명 (이메일, 비밀번호).
        request: FastAPI Request 객체.
        response: FastAPI Response 객체.

    Returns:
        로그인 성공 시 access_token과 사용자 정보가 포함된 응답 딕셔너리.

    Raises:
        HTTPException: 인증 실패 시 401 Unauthorized.
    """
    timestamp = get_request_timestamp(request)

    user = await user_models.get_user_by_email(credentials.email)

    password_valid = await asyncio.to_thread(
        verify_password,
        credentials.password,
        user.password if user else _TIMING_ATTACK_DUMMY_HASH,
    )

    if not user or not password_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "unauthorized",
                "timestamp": timestamp,
            },
        )

    access_token = create_access_token(user_id=user.id)

    raw_refresh = create_refresh_token()
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.JWT_REFRESH_EXPIRE_DAYS
    )
    await token_models.create_refresh_token(user.id, raw_refresh, expires_at)

    _set_refresh_cookie(response, raw_refresh)

    return create_response(
        "LOGIN_SUCCESS",
        "로그인에 성공했습니다.",
        data={"access_token": access_token, "user": serialize_user(user)},
        timestamp=timestamp,
    )


async def logout(
    current_user: User, request: Request, response: Response
) -> dict:
    """Refresh Token을 무효화하여 로그아웃합니다.

    Args:
        current_user: 현재 인증된 사용자 객체.
        request: FastAPI Request 객체.
        response: FastAPI Response 객체.

    Returns:
        로그아웃 성공 응답 딕셔너리.
    """
    timestamp = get_request_timestamp(request)

    raw_refresh = request.cookies.get(_REFRESH_COOKIE)
    if raw_refresh:
        await token_models.delete_refresh_token(raw_refresh)

    _clear_refresh_cookie(response)

    return create_response(
        "LOGOUT_SUCCESS", "로그아웃에 성공했습니다.", timestamp=timestamp
    )


async def refresh_token(request: Request, response: Response) -> dict:
    """Refresh Token으로 새 Access Token을 발급합니다 (토큰 회전).

    기존 Refresh Token을 삭제하고 새 토큰 쌍을 발급하여 보안을 강화합니다.

    Args:
        request: FastAPI Request 객체.
        response: FastAPI Response 객체.

    Returns:
        새 access_token과 사용자 정보가 포함된 응답 딕셔너리.

    Raises:
        HTTPException 401: Refresh Token이 없거나 만료/무효인 경우.
    """
    timestamp = get_request_timestamp(request)

    raw_refresh = request.cookies.get(_REFRESH_COOKIE)
    if not raw_refresh:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "refresh_token_missing", "timestamp": timestamp},
        )

    # 만료된 토큰이면 내부에서 삭제 후 None 반환
    token_record = await token_models.get_refresh_token(raw_refresh)
    if not token_record:
        _clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "refresh_token_invalid", "timestamp": timestamp},
        )

    user = await user_models.get_user_by_id(token_record["user_id"])
    if not user:
        _clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "timestamp": timestamp},
        )

    # 토큰 회전: DELETE + INSERT를 단일 트랜잭션으로 묶어 원자성 보장
    new_access_token = create_access_token(user_id=user.id)
    new_raw_refresh = create_refresh_token()
    new_expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.JWT_REFRESH_EXPIRE_DAYS
    )
    await token_models.rotate_refresh_token(
        old_raw_token=raw_refresh,
        new_raw_token=new_raw_refresh,
        user_id=user.id,
        new_expires_at=new_expires_at,
    )

    _set_refresh_cookie(response, new_raw_refresh)

    return create_response(
        "TOKEN_REFRESHED",
        "토큰이 갱신되었습니다.",
        data={"access_token": new_access_token, "user": serialize_user(user)},
        timestamp=timestamp,
    )


async def get_my_info(current_user: User, request: Request) -> dict:
    """현재 로그인 중인 사용자의 정보를 반환합니다.

    Args:
        current_user: 현재 인증된 사용자 객체.
        request: FastAPI Request 객체.

    Returns:
        사용자 정보가 포함된 응답 딕셔너리.
    """
    timestamp = get_request_timestamp(request)

    return create_response(
        "AUTH_SUCCESS",
        "현재 로그인 중인 상태입니다.",
        data={"user": serialize_user(current_user)},
        timestamp=timestamp,
    )


async def verify_email(token: str, request: Request) -> dict:
    """이메일 인증 토큰을 검증하고 이메일 인증을 완료합니다.

    Args:
        token: 이메일 인증 토큰.
        request: FastAPI Request 객체.

    Returns:
        인증 성공 응답 딕셔너리.

    Raises:
        HTTPException 400: 토큰이 유효하지 않거나 만료된 경우.
    """
    timestamp = get_request_timestamp(request)

    user_id = await verification_models.verify_token(token)
    if not user_id:
        raise bad_request_error("invalid_or_expired_token", timestamp)

    return create_response(
        "EMAIL_VERIFIED",
        "이메일 인증이 완료되었습니다.",
        timestamp=timestamp,
    )


async def resend_verification(current_user: User, request: Request) -> dict:
    """이메일 인증 메일을 재발송합니다.

    이미 인증이 완료된 사용자는 400 에러를 반환합니다.
    이메일 발송 실패는 무시합니다.

    Args:
        current_user: 현재 인증된 사용자 객체.
        request: FastAPI Request 객체.

    Returns:
        재발송 성공 응답 딕셔너리.

    Raises:
        HTTPException 400: 이미 이메일 인증이 완료된 경우.
    """
    timestamp = get_request_timestamp(request)

    if current_user.email_verified:
        raise bad_request_error("already_verified", timestamp)

    raw_token = await verification_models.create_verification_token(current_user.id)

    frontend_url = settings.FRONTEND_URL
    verify_link = f"{frontend_url}/verify-email?token={raw_token}"

    email_body = (
        f"안녕하세요, {current_user.nickname}님.\n\n"
        "아래 링크를 클릭하여 이메일 인증을 완료해주세요.\n\n"
        f"{verify_link}\n\n"
        "이 링크는 24시간 동안 유효합니다.\n"
        "본인이 요청하지 않은 경우 이 이메일을 무시하세요."
    )

    try:
        await send_email(
            to=current_user.email,
            subject="[아무 말 대잔치] 이메일 인증",
            body=email_body,
        )
    except Exception:
        logger.warning("이메일 인증 메일 재발송 실패: %s", current_user.email)

    return create_response(
        "VERIFICATION_EMAIL_SENT",
        "인증 이메일이 발송되었습니다.",
        timestamp=timestamp,
    )
