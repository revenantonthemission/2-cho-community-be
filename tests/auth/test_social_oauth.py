"""소셜 OAuth 콜백 통합 테스트 (14개).

프로바이더 메서드 레벨 모킹(Approach B)을 사용하여
카카오/네이버 소셜 로그인 콜백 흐름을 검증합니다.
"""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from httpx import AsyncClient

from database.connection import get_connection
from models import social_account_models, user_models
from routers.social_auth_router import _make_state
from services.social_auth.base import SocialUserInfo
from tests.conftest import create_verified_user

# ---------------------------------------------------------------------------
# 테스트 데이터 상수
# ---------------------------------------------------------------------------

KAKAO_USER_INFO = SocialUserInfo(
    provider="kakao",
    provider_id="kakao_123456",
    email="kakao_user@test.com",
    email_verified=True,
    profile_image="https://img.kakao.com/profile.jpg",
)

NAVER_USER_INFO = SocialUserInfo(
    provider="naver",
    provider_id="naver_789012",
    email="naver_user@test.com",
    email_verified=True,
    profile_image="https://img.naver.com/profile.jpg",
)


# ---------------------------------------------------------------------------
# 헬퍼 함수
# ---------------------------------------------------------------------------


@contextmanager  # type: ignore[arg-type]
def mock_provider(provider_module: str, user_info: SocialUserInfo):
    """프로바이더의 exchange_code와 get_user_info를 모킹한다."""
    cls_name = "KakaoProvider" if provider_module == "kakao" else "NaverProvider"
    base_path = f"services.social_auth.{provider_module}.{cls_name}"
    with (
        patch(
            f"{base_path}.exchange_code",
            new_callable=AsyncMock,
            return_value="fake_token",
        ),
        patch(
            f"{base_path}.get_user_info",
            new_callable=AsyncMock,
            return_value=user_info,
        ),
    ):
        yield


async def social_callback(
    client: AsyncClient,
    provider: str,
    state_raw: str,
    full_state: str,
    code: str = "fake_code",
    *,
    include_state_cookie: bool = True,
    include_code: bool = True,
    include_state_param: bool = True,
) -> httpx.Response:
    """소셜 콜백 엔드포인트를 호출하는 헬퍼."""
    params: dict[str, str] = {}
    if include_code:
        params["code"] = code
    if include_state_param:
        params["state"] = full_state

    cookies: dict[str, str] = {}
    if include_state_cookie:
        cookies["social_state"] = state_raw

    return await client.get(
        f"/v1/auth/social/{provider}/callback",
        params=params,
        cookies=cookies,
        follow_redirects=False,
    )


# ---------------------------------------------------------------------------
# Happy Path (5)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_authorize_redirects_to_provider(client: AsyncClient):
    """GET /authorize가 302로 카카오 URL 리다이렉트 + social_state 쿠키를 설정한다."""
    resp = await client.get(
        "/v1/auth/social/kakao/authorize", follow_redirects=False
    )
    assert resp.status_code == 302

    # 카카오 인증 URL로 리다이렉트
    location = resp.headers["location"]
    assert "kauth.kakao.com" in location

    # social_state 쿠키 설정 확인
    cookie_header = resp.headers.get("set-cookie", "")
    assert "social_state" in cookie_header


@pytest.mark.asyncio
async def test_callback_creates_new_user_kakao(client: AsyncClient):
    """카카오 신규 사용자 — password=None, nickname_set=False, /social-signup 리다이렉트."""
    state_raw, full_state = _make_state()

    with mock_provider("kakao", KAKAO_USER_INFO):
        resp = await social_callback(client, "kakao", state_raw, full_state)

    assert resp.status_code == 302
    location = resp.headers["location"]
    assert "/social-signup" in location
    assert "access_token=" in location

    # DB 검증: 사용자 생성 확인
    user = await user_models.get_user_by_email(KAKAO_USER_INFO.email)  # type: ignore[arg-type]
    assert user is not None
    assert user.password is None
    assert user.nickname_set is False

    # 소셜 계정 연동 확인
    sa = await social_account_models.get_by_provider("kakao", "kakao_123456")
    assert sa is not None
    assert sa["user_id"] == user.id


@pytest.mark.asyncio
async def test_callback_creates_new_user_naver(client: AsyncClient):
    """네이버 신규 사용자 — password=None, nickname_set=False, /social-signup 리다이렉트."""
    state_raw, full_state = _make_state()

    with mock_provider("naver", NAVER_USER_INFO):
        resp = await social_callback(client, "naver", state_raw, full_state)

    assert resp.status_code == 302
    location = resp.headers["location"]
    assert "/social-signup" in location
    assert "access_token=" in location

    # DB 검증
    user = await user_models.get_user_by_email(NAVER_USER_INFO.email)  # type: ignore[arg-type]
    assert user is not None
    assert user.password is None
    assert user.nickname_set is False

    sa = await social_account_models.get_by_provider("naver", "naver_789012")
    assert sa is not None
    assert sa["user_id"] == user.id


@pytest.mark.asyncio
async def test_callback_sets_refresh_cookie(client: AsyncClient):
    """콜백 성공 시 refresh_token 쿠키가 설정된다."""
    state_raw, full_state = _make_state()

    with mock_provider("kakao", KAKAO_USER_INFO):
        resp = await social_callback(client, "kakao", state_raw, full_state)

    assert resp.status_code == 302

    # set-cookie 헤더에서 refresh_token 확인
    set_cookie_headers = resp.headers.get_list("set-cookie")
    refresh_cookies = [h for h in set_cookie_headers if "refresh_token" in h]
    assert len(refresh_cookies) > 0
    assert "httponly" in refresh_cookies[0].lower()


@pytest.mark.asyncio
async def test_callback_deletes_state_cookie(client: AsyncClient):
    """콜백 성공 후 social_state 쿠키가 삭제된다."""
    state_raw, full_state = _make_state()

    with mock_provider("kakao", KAKAO_USER_INFO):
        resp = await social_callback(client, "kakao", state_raw, full_state)

    assert resp.status_code == 302

    # social_state 쿠키 삭제 확인 (max-age=0 또는 과거 expires)
    set_cookie_headers = resp.headers.get_list("set-cookie")
    state_cookies = [
        h for h in set_cookie_headers if h.startswith("social_state")
    ]
    assert len(state_cookies) > 0

    state_cookie = state_cookies[0].lower()
    # 쿠키 삭제는 max-age=0 또는 과거 expires로 처리
    deleted = "max-age=0" in state_cookie or '=""' in state_cookie
    assert deleted, f"social_state 쿠키가 삭제되지 않음: {state_cookies[0]}"


# ---------------------------------------------------------------------------
# Returning User (2)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_callback_existing_social_user_redirects_to_main(
    client: AsyncClient,
):
    """기존 사용자(nickname_set=True)는 /main으로 리다이렉트된다."""
    # 사용자 + 소셜 계정 사전 생성
    nickname = user_models.generate_temp_nickname()
    user = await user_models.add_social_user(
        email="existing_kakao@test.com", nickname=nickname
    )
    # nickname_set=True로 변경
    await user_models.update_nickname_set(user.id, "완성닉네임")
    await social_account_models.create(
        user_id=user.id,
        provider="kakao",
        provider_id="returning_kakao_001",
        provider_email="existing_kakao@test.com",
    )

    # 동일한 provider_id를 가진 SocialUserInfo
    returning_info = SocialUserInfo(
        provider="kakao",
        provider_id="returning_kakao_001",
        email="existing_kakao@test.com",
        email_verified=True,
        profile_image=None,
    )

    state_raw, full_state = _make_state()
    with mock_provider("kakao", returning_info):
        resp = await social_callback(client, "kakao", state_raw, full_state)

    assert resp.status_code == 302
    assert "/main" in resp.headers["location"]


@pytest.mark.asyncio
async def test_callback_existing_social_user_without_nickname_redirects_to_signup(
    client: AsyncClient,
):
    """기존 사용자(nickname_set=False)는 /social-signup으로 리다이렉트된다."""
    nickname = user_models.generate_temp_nickname()
    user = await user_models.add_social_user(
        email="no_nick@test.com", nickname=nickname
    )
    await social_account_models.create(
        user_id=user.id,
        provider="naver",
        provider_id="returning_naver_001",
        provider_email="no_nick@test.com",
    )

    returning_info = SocialUserInfo(
        provider="naver",
        provider_id="returning_naver_001",
        email="no_nick@test.com",
        email_verified=True,
        profile_image=None,
    )

    state_raw, full_state = _make_state()
    with mock_provider("naver", returning_info):
        resp = await social_callback(client, "naver", state_raw, full_state)

    assert resp.status_code == 302
    assert "/social-signup" in resp.headers["location"]


# ---------------------------------------------------------------------------
# Email Collision (1)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_callback_links_existing_local_account(
    client: AsyncClient, fake: Any
):
    """소셜 이메일이 기존 로컬 계정과 일치하면 연동하고 /main으로 리다이렉트된다."""
    # 로컬 계정 생성 (이메일 인증 완료)
    local_user = await create_verified_user(client, fake)
    local_email = local_user["email"]

    # 동일 이메일의 소셜 정보
    collision_info = SocialUserInfo(
        provider="kakao",
        provider_id="collision_kakao_001",
        email=local_email,
        email_verified=True,
        profile_image=None,
    )

    state_raw, full_state = _make_state()
    with mock_provider("kakao", collision_info):
        resp = await social_callback(client, "kakao", state_raw, full_state)

    assert resp.status_code == 302
    # 로컬 사용자는 nickname_set=True → /main
    assert "/main" in resp.headers["location"]

    # 새 사용자가 생성되지 않고 소셜 계정만 연동되었는지 확인
    sa = await social_account_models.get_by_provider("kakao", "collision_kakao_001")
    assert sa is not None
    assert sa["user_id"] == local_user["user_id"]


# ---------------------------------------------------------------------------
# Error Cases (6)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_callback_invalid_state_redirects_with_error(
    client: AsyncClient,
):
    """변조된 state → /login?error=invalid_state 리다이렉트."""
    state_raw, _ = _make_state()
    tampered_state = f"{state_raw}:tampered_signature"

    resp = await social_callback(client, "kakao", state_raw, tampered_state)

    assert resp.status_code == 302
    assert "error=invalid_state" in resp.headers["location"]


@pytest.mark.asyncio
async def test_callback_missing_state_cookie_redirects_with_error(
    client: AsyncClient,
):
    """social_state 쿠키 없이 요청 → /login?error=invalid_state."""
    _, full_state = _make_state()

    resp = await social_callback(
        client,
        "kakao",
        state_raw="",
        full_state=full_state,
        include_state_cookie=False,
    )

    assert resp.status_code == 302
    assert "error=invalid_state" in resp.headers["location"]


@pytest.mark.asyncio
async def test_callback_missing_code_redirects_with_error(
    client: AsyncClient,
):
    """code 파라미터 없이 요청 → /login?error=missing_code."""
    state_raw, full_state = _make_state()

    resp = await social_callback(
        client,
        "kakao",
        state_raw,
        full_state,
        include_code=False,
    )

    assert resp.status_code == 302
    assert "error=missing_code" in resp.headers["location"]


@pytest.mark.asyncio
async def test_callback_provider_error_redirects_with_error(
    client: AsyncClient,
):
    """exchange_code 예외 발생 → /login?error=provider_error."""
    state_raw, full_state = _make_state()

    # httpx.HTTPStatusError를 실제 예외로 생성
    mock_request = httpx.Request("POST", "https://kauth.kakao.com/oauth/token")
    mock_response = httpx.Response(400, request=mock_request)
    provider_exc = httpx.HTTPStatusError(
        "Bad Request", request=mock_request, response=mock_response
    )

    base_path = "services.social_auth.kakao.KakaoProvider"
    with patch(
        f"{base_path}.exchange_code",
        new_callable=AsyncMock,
        side_effect=provider_exc,
    ):
        resp = await social_callback(client, "kakao", state_raw, full_state)

    assert resp.status_code == 302
    assert "error=provider_error" in resp.headers["location"]


@pytest.mark.asyncio
async def test_callback_suspended_user_redirects_with_error(
    client: AsyncClient,
):
    """정지된 사용자 → /login?error=suspended."""
    # 사용자 + 소셜 계정 생성
    nickname = user_models.generate_temp_nickname()
    user = await user_models.add_social_user(
        email="suspended@test.com", nickname=nickname
    )
    await social_account_models.create(
        user_id=user.id,
        provider="kakao",
        provider_id="suspended_kakao_001",
        provider_email="suspended@test.com",
    )

    # 정지 처리 (직접 SQL)
    suspended_until = datetime.now(timezone.utc) + timedelta(days=30)
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE user SET suspended_until = %s WHERE id = %s",
                (suspended_until, user.id),
            )

    suspended_info = SocialUserInfo(
        provider="kakao",
        provider_id="suspended_kakao_001",
        email="suspended@test.com",
        email_verified=True,
        profile_image=None,
    )

    state_raw, full_state = _make_state()
    with mock_provider("kakao", suspended_info):
        resp = await social_callback(client, "kakao", state_raw, full_state)

    assert resp.status_code == 302
    assert "error=suspended" in resp.headers["location"]


@pytest.mark.asyncio
async def test_callback_unsupported_provider_returns_400(
    client: AsyncClient,
):
    """/v1/auth/social/google/callback → 400 (미지원 프로바이더)."""
    state_raw, full_state = _make_state()

    resp = await social_callback(client, "google", state_raw, full_state)

    assert resp.status_code == 400
