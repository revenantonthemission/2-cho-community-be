"""소셜 OAuth 콜백 통합 테스트 (13개).

GitHub OAuth 프로바이더 메서드 레벨 모킹(Approach B)을 사용하여
소셜 로그인 콜백 흐름을 검증합니다.
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

GITHUB_USER_INFO = SocialUserInfo(
    provider="github",
    provider_id="github_123456",
    email="github_user@test.com",
    email_verified=True,
    profile_image="https://avatars.githubusercontent.com/u/123456",
)


# ---------------------------------------------------------------------------
# 헬퍼 함수
# ---------------------------------------------------------------------------


@contextmanager  # type: ignore[arg-type]
def mock_provider(user_info: SocialUserInfo):
    """GitHubProvider의 exchange_code와 get_user_info를 모킹한다."""
    base_path = "services.social_auth.github.GitHubProvider"
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
# Happy Path (4)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_authorize_redirects_to_provider(client: AsyncClient):
    """GET /authorize가 302로 GitHub URL 리다이렉트 + social_state 쿠키를 설정한다."""
    resp = await client.get(
        "/v1/auth/social/github/authorize", follow_redirects=False
    )
    assert resp.status_code == 302

    location = resp.headers["location"]
    assert "github.com" in location

    cookie_header = resp.headers.get("set-cookie", "")
    assert "social_state" in cookie_header


@pytest.mark.asyncio
async def test_callback_creates_new_user(client: AsyncClient):
    """GitHub 신규 사용자 — password=None, nickname_set=False, /social-signup 리다이렉트."""
    state_raw, full_state = _make_state()

    with mock_provider(GITHUB_USER_INFO):
        resp = await social_callback(client, "github", state_raw, full_state)

    assert resp.status_code == 302
    location = resp.headers["location"]
    assert "/social-signup" in location
    assert "access_token=" in location

    user = await user_models.get_user_by_email(GITHUB_USER_INFO.email)  # type: ignore[arg-type]
    assert user is not None
    assert user.password is None
    assert user.nickname_set is False

    sa = await social_account_models.get_by_provider("github", "github_123456")
    assert sa is not None
    assert sa["user_id"] == user.id


@pytest.mark.asyncio
async def test_callback_sets_refresh_cookie(client: AsyncClient):
    """콜백 성공 시 refresh_token 쿠키가 설정된다."""
    state_raw, full_state = _make_state()

    with mock_provider(GITHUB_USER_INFO):
        resp = await social_callback(client, "github", state_raw, full_state)

    assert resp.status_code == 302

    set_cookie_headers = resp.headers.get_list("set-cookie")
    refresh_cookies = [h for h in set_cookie_headers if "refresh_token" in h]
    assert len(refresh_cookies) > 0
    assert "httponly" in refresh_cookies[0].lower()


@pytest.mark.asyncio
async def test_callback_deletes_state_cookie(client: AsyncClient):
    """콜백 성공 후 social_state 쿠키가 삭제된다."""
    state_raw, full_state = _make_state()

    with mock_provider(GITHUB_USER_INFO):
        resp = await social_callback(client, "github", state_raw, full_state)

    assert resp.status_code == 302

    set_cookie_headers = resp.headers.get_list("set-cookie")
    state_cookies = [
        h for h in set_cookie_headers if h.startswith("social_state")
    ]
    assert len(state_cookies) > 0

    state_cookie = state_cookies[0].lower()
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
    nickname = user_models.generate_temp_nickname()
    user = await user_models.add_social_user(
        email="existing_github@test.com", nickname=nickname
    )
    await user_models.update_nickname_set(user.id, "완성닉네임")
    await social_account_models.create(
        user_id=user.id,
        provider="github",
        provider_id="returning_github_001",
        provider_email="existing_github@test.com",
    )

    returning_info = SocialUserInfo(
        provider="github",
        provider_id="returning_github_001",
        email="existing_github@test.com",
        email_verified=True,
        profile_image=None,
    )

    state_raw, full_state = _make_state()
    with mock_provider(returning_info):
        resp = await social_callback(client, "github", state_raw, full_state)

    assert resp.status_code == 302
    assert "/main" in resp.headers["location"]


@pytest.mark.asyncio
async def test_callback_existing_social_user_without_nickname_redirects_to_signup(
    client: AsyncClient,
):
    """기존 사용자(nickname_set=False)는 /social-signup으로 리다이렉트된다."""
    nickname = user_models.generate_temp_nickname()
    user = await user_models.add_social_user(
        email="no_nick_gh@test.com", nickname=nickname
    )
    await social_account_models.create(
        user_id=user.id,
        provider="github",
        provider_id="returning_github_002",
        provider_email="no_nick_gh@test.com",
    )

    returning_info = SocialUserInfo(
        provider="github",
        provider_id="returning_github_002",
        email="no_nick_gh@test.com",
        email_verified=True,
        profile_image=None,
    )

    state_raw, full_state = _make_state()
    with mock_provider(returning_info):
        resp = await social_callback(client, "github", state_raw, full_state)

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
    local_user = await create_verified_user(client, fake)
    local_email = local_user["email"]

    collision_info = SocialUserInfo(
        provider="github",
        provider_id="collision_github_001",
        email=local_email,
        email_verified=True,
        profile_image=None,
    )

    state_raw, full_state = _make_state()
    with mock_provider(collision_info):
        resp = await social_callback(client, "github", state_raw, full_state)

    assert resp.status_code == 302
    assert "/main" in resp.headers["location"]

    sa = await social_account_models.get_by_provider("github", "collision_github_001")
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

    resp = await social_callback(client, "github", state_raw, tampered_state)

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
        "github",
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
        "github",
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

    mock_request = httpx.Request("POST", "https://github.com/login/oauth/access_token")
    mock_response = httpx.Response(400, request=mock_request)
    provider_exc = httpx.HTTPStatusError(
        "Bad Request", request=mock_request, response=mock_response
    )

    with patch(
        "services.social_auth.github.GitHubProvider.exchange_code",
        new_callable=AsyncMock,
        side_effect=provider_exc,
    ):
        resp = await social_callback(client, "github", state_raw, full_state)

    assert resp.status_code == 302
    assert "error=provider_error" in resp.headers["location"]


@pytest.mark.asyncio
async def test_callback_suspended_user_redirects_with_error(
    client: AsyncClient,
):
    """정지된 사용자 → /login?error=suspended."""
    nickname = user_models.generate_temp_nickname()
    user = await user_models.add_social_user(
        email="suspended_gh@test.com", nickname=nickname
    )
    await social_account_models.create(
        user_id=user.id,
        provider="github",
        provider_id="suspended_github_001",
        provider_email="suspended_gh@test.com",
    )

    suspended_until = datetime.now(timezone.utc) + timedelta(days=30)
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE user SET suspended_until = %s WHERE id = %s",
                (suspended_until, user.id),
            )

    suspended_info = SocialUserInfo(
        provider="github",
        provider_id="suspended_github_001",
        email="suspended_gh@test.com",
        email_verified=True,
        profile_image=None,
    )

    state_raw, full_state = _make_state()
    with mock_provider(suspended_info):
        resp = await social_callback(client, "github", state_raw, full_state)

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
