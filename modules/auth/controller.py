"""auth_controller: 인증 관련 컨트롤러 모듈.

JWT 기반 로그인, 로그아웃, 토큰 갱신, 사용자 인증 상태 확인,
이메일 인증 등의 기능을 제공합니다.
HTTP 관련 처리(쿠키, Request/Response)를 담당하고,
비즈니스 로직은 AuthService에 위임합니다.
"""

import logging

from fastapi import HTTPException, Request, Response, status

from core.config import settings
from core.dependencies.request_context import get_request_timestamp
from core.utils.email import send_email
from core.utils.error_codes import ErrorCode
from core.utils.exceptions import bad_request_error
from modules.auth import verification_models
from modules.auth.auth_schemas import LoginRequest
from modules.auth.service import AuthService
from modules.user.models import User
from schemas.common import create_response, serialize_user

logger = logging.getLogger(__name__)

_REFRESH_COOKIE = "refresh_token"


def _set_refresh_cookie(response: Response, token: str) -> None:
    """응답에 HttpOnly Refresh Token 쿠키를 설정합니다."""
    # httponly=True: JS에서 접근 불가 — XSS로 Refresh Token 탈취 방지
    # secure=HTTPS_ONLY: 프로덕션에서 HTTPS 전용 전송 강제
    # samesite=lax: CSRF 방지 + 외부 링크로의 GET 요청은 허용
    # path=/v1/auth: 토큰 갱신/로그아웃 엔드포인트에서만 쿠키 전송 — 불필요한 노출 최소화
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
    # 쿠키 삭제 시에도 설정 시와 동일한 path/domain 속성을 명시해야 브라우저가 올바르게 삭제함
    response.delete_cookie(
        key=_REFRESH_COOKIE,
        path="/v1/auth",
        httponly=True,
        secure=settings.HTTPS_ONLY,
        samesite="lax",
    )


async def login(credentials: LoginRequest, request: Request, response: Response) -> dict:
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

    result = await AuthService.authenticate(
        email=credentials.email,
        password=credentials.password,
        timestamp=timestamp,
    )

    # Refresh Token은 HttpOnly 쿠키로 전달 — 클라이언트 JS가 직접 접근할 수 없어 XSS 방어
    _set_refresh_cookie(response, result.raw_refresh_token)

    return create_response(
        "LOGIN_SUCCESS",
        "로그인에 성공했습니다.",
        data={
            "access_token": result.access_token,
            "user": serialize_user(result.user),
        },
        timestamp=timestamp,
    )


async def logout(current_user: User, request: Request, response: Response) -> dict:
    """Refresh Token을 무효화하여 로그아웃합니다.

    Args:
        current_user: 현재 인증된 사용자 객체.
        request: FastAPI Request 객체.
        response: FastAPI Response 객체.

    Returns:
        로그아웃 성공 응답 딕셔너리.
    """
    timestamp = get_request_timestamp(request)

    # 쿠키에서 Refresh Token을 읽어 DB에서 무효화 — None이어도 Service에서 gracefully 처리
    raw_refresh = request.cookies.get(_REFRESH_COOKIE)
    await AuthService.logout(raw_refresh)

    _clear_refresh_cookie(response)

    return create_response("LOGOUT_SUCCESS", "로그아웃에 성공했습니다.", timestamp=timestamp)


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

    # 쿠키가 없으면 즉시 401 — Service 호출 없이 빠른 거절로 불필요한 DB 조회 방지
    raw_refresh = request.cookies.get(_REFRESH_COOKIE)
    if not raw_refresh:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "refresh_token_missing", "timestamp": timestamp},
        )

    try:
        result = await AuthService.refresh_access_token(
            refresh_token_value=raw_refresh,
            timestamp=timestamp,
        )
    except HTTPException:
        # 유효하지 않은 토큰으로 접근 시 쿠키를 즉시 삭제 — 클라이언트가 만료된 쿠키를 계속 전송하지 않도록
        _clear_refresh_cookie(response)
        raise

    # 토큰 회전(rotation): 매 갱신마다 새 Refresh Token 발급 — 탈취된 토큰의 재사용 감지 가능
    _set_refresh_cookie(response, result.raw_refresh_token)

    return create_response(
        "TOKEN_REFRESHED",
        "토큰이 갱신되었습니다.",
        data={
            "access_token": result.access_token,
            "user": serialize_user(result.user),
        },
        timestamp=timestamp,
    )


async def get_auth_status(current_user: User, request: Request) -> dict:
    """현재 로그인 중인 사용자의 인증 상태와 기본 정보를 반환합니다.

    user_controller의 get_my_info(팔로우 수 포함 전체 프로필)와 달리
    인증 상태 확인 용도로 최소한의 사용자 정보만 반환합니다.

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

    # verify_token은 토큰 검증 + 사용자 email_verified 업데이트를 원자적으로 수행
    # None 반환 시 토큰이 없거나 만료됨 — 재사용 방지를 위해 검증 즉시 DB에서 삭제됨
    user_id = await verification_models.verify_token(token)
    if not user_id:
        raise bad_request_error(ErrorCode.INVALID_OR_EXPIRED_TOKEN, timestamp)

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

    # 이미 인증된 사용자는 불필요한 토큰 생성을 막기 위해 즉시 거절
    if current_user.email_verified:
        raise bad_request_error(ErrorCode.ALREADY_VERIFIED, timestamp)

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
            subject="[Camp Linux] 이메일 인증",
            body=email_body,
        )
    except Exception:
        # 이메일 발송 실패는 사용자 경험보다 중요하지 않으므로 경고 로그만 남기고 성공 응답 반환
        # 토큰은 이미 생성되었으므로 사용자가 나중에 재시도할 수 있음
        logger.warning("이메일 인증 메일 재발송 실패: %s", current_user.email)

    return create_response(
        "VERIFICATION_EMAIL_SENT",
        "인증 이메일이 발송되었습니다.",
        timestamp=timestamp,
    )
