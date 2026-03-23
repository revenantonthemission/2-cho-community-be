"""Auth 도메인 — 토큰 갱신/인증 테스트."""

import pytest
from httpx import ASGITransport, AsyncClient

from main import app
from tests.conftest import create_verified_user

# ---------------------------------------------------------------------------
# Refresh Token
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refresh_token_returns_new_access_token(client: AsyncClient, fake):
    """유효한 refresh token 쿠키로 새 access_token을 발급받는다."""
    user = await create_verified_user(client, fake)

    # 로그인해서 refresh_token 쿠키 획득
    login_res = await client.post(
        "/v1/auth/session",
        json={"email": user["email"], "password": user["payload"]["password"]},
    )
    assert login_res.status_code == 200

    # refresh_token 쿠키를 가진 클라이언트로 갱신 요청
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        cookies=login_res.cookies,
    ) as refresh_client:
        res = await refresh_client.post("/v1/auth/token/refresh")

    assert res.status_code == 200
    data = res.json()["data"]
    assert "access_token" in data
    assert "user" in data


@pytest.mark.asyncio
async def test_refresh_with_invalid_token_returns_401(client: AsyncClient, fake):
    """유효하지 않은 refresh token으로 갱신 시 401을 반환한다."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        cookies={"refresh_token": "invalid-token-value"},
    ) as bad_client:
        res = await bad_client.post("/v1/auth/token/refresh")

    assert res.status_code == 401


@pytest.mark.asyncio
async def test_refresh_rotates_token(client: AsyncClient, fake):
    """토큰 갱신 후 이전 refresh token은 사용 불가하다 (토큰 회전)."""
    user = await create_verified_user(client, fake)

    # 로그인
    login_res = await client.post(
        "/v1/auth/session",
        json={"email": user["email"], "password": user["payload"]["password"]},
    )
    old_cookies = dict(login_res.cookies)

    # 첫 번째 갱신 — 성공
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        cookies=old_cookies,
    ) as c1:
        first_refresh = await c1.post("/v1/auth/token/refresh")
    assert first_refresh.status_code == 200

    # 이전(old) 쿠키로 다시 갱신 시도 — 토큰 회전으로 실패해야 함
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        cookies=old_cookies,
    ) as c2:
        second_refresh = await c2.post("/v1/auth/token/refresh")
    assert second_refresh.status_code == 401


# ---------------------------------------------------------------------------
# 만료/무효 Access Token
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_expired_access_token_returns_401(client: AsyncClient, fake):
    """명백히 무효한 JWT로 인증 시 401을 반환한다."""
    res = await client.get(
        "/v1/auth/me",
        headers={"Authorization": "Bearer clearly.invalid.token"},
    )

    assert res.status_code == 401


# ---------------------------------------------------------------------------
# GET /v1/auth/me
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_me_with_valid_token_returns_user_info(client: AsyncClient, fake):
    """유효한 토큰으로 /me 조회 시 사용자 정보를 반환한다."""
    user = await create_verified_user(client, fake)

    res = await user["client"].get("/v1/auth/me")

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["user"]["email"] == user["email"]
    assert data["user"]["nickname"] == user["nickname"]
