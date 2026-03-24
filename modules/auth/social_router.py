"""social_auth_router: 소셜 로그인 라우터.

카카오/네이버 소셜 로그인의 인증 시작, 콜백 처리, 닉네임 설정 엔드포인트를 제공합니다.
"""

import hashlib
import hmac
import logging
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import APIRouter, Cookie, Depends, Query, status
from fastapi.responses import RedirectResponse

from core.config import settings
from core.dependencies.auth import get_current_user
from core.utils.jwt_utils import create_access_token, create_refresh_token
from modules.auth import social_account_models, token_models
from modules.auth.social.factory import get_provider
from modules.auth.social_auth_schemas import CompleteSignupRequest
from modules.user import models as user_models
from modules.user.models import User, generate_temp_nickname
from schemas.common import create_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/auth/social", tags=["social-auth"])

_STATE_COOKIE = "social_state"
_REFRESH_COOKIE = "refresh_token"

# 액세스 토큰을 URL 노출 없이 전달하는 단기 쿠키.
# HttpOnly=False: JS가 읽어서 메모리/localStorage에 저장 후 즉시 삭제해야 함.
# max_age=60: 60초 내 JS가 읽지 않으면 자동 만료되어 노출 위험 최소화.
_ACCESS_TOKEN_COOKIE = "access_token_temp"
_ACCESS_TOKEN_COOKIE_MAX_AGE = 60


def _hmac_sign(message: str) -> str:
    """SECRET_KEY로 메시지의 HMAC-SHA256 서명을 생성합니다."""
    return hmac.new(settings.SECRET_KEY.encode(), message.encode(), hashlib.sha256).hexdigest()


def _make_state() -> tuple[str, str]:
    """HMAC 서명된 state 값을 생성합니다.

    Returns:
        (state_raw, full_state) 튜플. full_state = "raw:sig".
    """
    state_raw = uuid4().hex
    return state_raw, f"{state_raw}:{_hmac_sign(state_raw)}"


def _verify_state(state_param: str, cookie_raw: str) -> bool:
    """state 파라미터의 HMAC 서명과 쿠키 값을 검증합니다."""
    parts = state_param.split(":", 1)
    if len(parts) != 2:
        return False
    raw, sig = parts

    # 쿠키의 raw 값과 state의 raw 부분 비교
    if not hmac.compare_digest(cookie_raw, raw):
        return False

    # HMAC 서명 검증
    return hmac.compare_digest(sig, _hmac_sign(raw))


def _error_redirect(frontend_url: str, error: str) -> RedirectResponse:
    """에러 코드와 함께 로그인 페이지로 리다이렉트하는 응답을 생성합니다."""
    return RedirectResponse(
        url=f"{frontend_url}/login?error={error}",
        status_code=status.HTTP_302_FOUND,
    )


def _set_refresh_cookie(response: RedirectResponse, token: str) -> None:
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


def _set_access_token_cookie(response: RedirectResponse, token: str) -> None:
    """응답에 단기 Access Token 쿠키를 설정합니다.

    URL 쿼리 파라미터 노출을 피하기 위해 쿠키로 전달합니다.
    JS가 읽어야 하므로 HttpOnly=False이며, max_age를 짧게 설정해 노출 시간을 최소화합니다.
    """
    response.set_cookie(
        key=_ACCESS_TOKEN_COOKIE,
        value=token,
        httponly=False,
        secure=settings.HTTPS_ONLY,
        samesite="lax",
        max_age=_ACCESS_TOKEN_COOKIE_MAX_AGE,
        path="/",
    )


async def _issue_tokens_and_redirect(user: User, redirect_path: str) -> RedirectResponse:
    """JWT를 발급하고 프론트엔드로 리다이렉트합니다. 액세스 토큰은 단기 쿠키로 전달하여 URL 노출을 방지합니다."""
    access_token = create_access_token(user_id=user.id)
    raw_refresh = create_refresh_token()
    expires_at = datetime.now(UTC) + timedelta(days=settings.JWT_REFRESH_EXPIRE_DAYS)
    await token_models.create_refresh_token(user.id, raw_refresh, expires_at)

    redirect_url = f"{settings.FRONTEND_URL}{redirect_path}"
    response = RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)
    _set_refresh_cookie(response, raw_refresh)
    _set_access_token_cookie(response, access_token)
    return response


@router.get("/{provider}/authorize")
async def authorize(provider: str) -> RedirectResponse:
    """소셜 로그인 인증 페이지로 리다이렉트합니다."""
    social_provider = get_provider(provider)
    state_raw, full_state = _make_state()

    response = RedirectResponse(
        url=social_provider.get_authorize_url(full_state),
        status_code=status.HTTP_302_FOUND,
    )
    response.set_cookie(
        key=_STATE_COOKIE,
        value=state_raw,
        httponly=True,
        secure=settings.HTTPS_ONLY,
        samesite="lax",
        max_age=300,
        path="/",
    )
    return response


@router.get("/{provider}/callback")
async def callback(
    provider: str,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    social_state: str | None = Cookie(default=None),
) -> RedirectResponse:
    """소셜 로그인 콜백을 처리합니다."""
    frontend_url = settings.FRONTEND_URL

    # 사용자가 소셜 로그인을 취소한 경우
    if error:
        response = _error_redirect(frontend_url, "cancelled")
        response.delete_cookie(key=_STATE_COOKIE, path="/")
        return response

    # state 검증
    if not state or not social_state:
        return _error_redirect(frontend_url, "invalid_state")

    if not _verify_state(state, social_state):
        response = _error_redirect(frontend_url, "invalid_state")
        response.delete_cookie(key=_STATE_COOKIE, path="/")
        return response

    # code 누락 검증
    if not code:
        return _error_redirect(frontend_url, "missing_code")

    # 소셜 프로바이더에서 사용자 정보 조회
    social_provider = get_provider(provider)
    try:
        provider_token = await social_provider.exchange_code(code)
        user_info = await social_provider.get_user_info(provider_token)
    except Exception:
        logger.exception("소셜 로그인 코드 교환/사용자 정보 조회 실패: provider=%s", provider)
        response = _error_redirect(frontend_url, "provider_error")
        response.delete_cookie(key=_STATE_COOKIE, path="/")
        return response

    # state 쿠키 삭제는 성공적으로 검증 완료 후
    # (아래에서 모든 응답에 삭제 적용)

    # Branch 1: 이미 연동된 소셜 계정이 있는 경우
    social_account = await social_account_models.get_by_provider(user_info.provider, user_info.provider_id)
    if social_account:
        user = await user_models.get_user_by_id(social_account["user_id"])
        if not user:
            response = _error_redirect(frontend_url, "user_not_found")
            response.delete_cookie(key=_STATE_COOKIE, path="/")
            return response

        if user.is_suspended:
            response = _error_redirect(frontend_url, "suspended")
            response.delete_cookie(key=_STATE_COOKIE, path="/")
            return response

        redirect_path = "/social-signup" if not user.nickname_set else "/main"
        response = await _issue_tokens_and_redirect(user, redirect_path)
        response.delete_cookie(key=_STATE_COOKIE, path="/")
        return response

    # Branch 2: 이메일 매칭으로 기존 사용자에 소셜 계정 연동
    if user_info.email and user_info.email_verified:
        existing_user = await user_models.get_user_by_email(user_info.email)
        if existing_user:
            if existing_user.is_suspended:
                response = _error_redirect(frontend_url, "suspended")
                response.delete_cookie(key=_STATE_COOKIE, path="/")
                return response

            await social_account_models.create(
                user_id=existing_user.id,
                provider=user_info.provider,
                provider_id=user_info.provider_id,
                provider_email=user_info.email,
            )

            redirect_path = "/social-signup" if not existing_user.nickname_set else "/main"
            response = await _issue_tokens_and_redirect(existing_user, redirect_path)
            response.delete_cookie(key=_STATE_COOKIE, path="/")
            return response

    # Branch 3: 신규 사용자 생성
    temp_nickname = generate_temp_nickname()
    new_user = await user_models.add_social_user(
        email=user_info.email,
        nickname=temp_nickname,
        profile_image_url=user_info.profile_image,
    )
    await social_account_models.create(
        user_id=new_user.id,
        provider=user_info.provider,
        provider_id=user_info.provider_id,
        provider_email=user_info.email,
    )

    response = await _issue_tokens_and_redirect(new_user, "/social-signup")
    response.delete_cookie(key=_STATE_COOKIE, path="/")
    return response


@router.post("/complete-signup")
async def complete_signup(
    body: CompleteSignupRequest,
    current_user: User = Depends(get_current_user),
) -> dict:
    """소셜 가입 후 닉네임을 설정합니다."""
    # 닉네임 중복 검사
    existing = await user_models.get_user_by_nickname(body.nickname)
    if existing:
        return create_response(
            "NICKNAME_DUPLICATED",
            "이미 사용 중인 닉네임입니다.",
            data={},
        )
    updated_user = await user_models.update_nickname_set(current_user.id, body.nickname)
    if not updated_user:
        return create_response(
            "USER_NOT_FOUND",
            "사용자를 찾을 수 없습니다.",
            data={},
        )

    return create_response(
        "SIGNUP_COMPLETED",
        "닉네임이 설정되었습니다.",
        data={"nickname": updated_user.nickname},
    )
