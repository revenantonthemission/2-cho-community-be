"""Auth 도메인 — 로그인/로그아웃 테스트."""

import pytest
from httpx import AsyncClient

from database.connection import get_connection
from tests.conftest import create_verified_user


# ---------------------------------------------------------------------------
# 로그인 성공
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_with_valid_credentials_returns_200(client: AsyncClient, fake):
    """올바른 자격증명으로 로그인 시 access_token과 refresh_token 쿠키를 반환한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    email = user["email"]
    password = user["payload"]["password"]

    # Act — 새 세션으로 로그인
    res = await client.post(
        "/v1/auth/session",
        json={"email": email, "password": password},
    )

    # Assert
    assert res.status_code == 200
    data = res.json()["data"]
    assert "access_token" in data
    assert "user" in data
    assert data["user"]["email"] == email

    # HttpOnly 쿠키에 refresh_token이 포함되어야 함
    assert "refresh_token" in res.cookies


# ---------------------------------------------------------------------------
# 로그인 실패
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_with_wrong_password_returns_401(client: AsyncClient, fake):
    """잘못된 비밀번호로 로그인 시 401을 반환한다."""
    user = await create_verified_user(client, fake)

    res = await client.post(
        "/v1/auth/session",
        json={"email": user["email"], "password": "WrongPassword1!"},
    )

    assert res.status_code == 401


@pytest.mark.asyncio
async def test_login_with_nonexistent_email_returns_401(client: AsyncClient, fake):
    """존재하지 않는 이메일로 로그인 시 401을 반환한다."""
    res = await client.post(
        "/v1/auth/session",
        json={"email": "nobody@example.com", "password": "Password123!"},
    )

    assert res.status_code == 401


@pytest.mark.asyncio
async def test_login_with_suspended_account_returns_403(client: AsyncClient, fake):
    """정지된 계정으로 로그인 시 403과 정지 정보를 반환한다."""
    user = await create_verified_user(client, fake)

    # DB에서 직접 계정 정지 처리
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE user SET suspended_until = DATE_ADD(NOW(), INTERVAL 7 DAY), "
                "suspended_reason = '테스트 정지' WHERE id = %s",
                (user["user_id"],),
            )

    res = await client.post(
        "/v1/auth/session",
        json={"email": user["email"], "password": user["payload"]["password"]},
    )

    assert res.status_code == 403
    detail = res.json()["detail"]
    assert detail["error"] == "account_suspended"
    assert "suspended_until" in detail
    assert detail["suspended_reason"] == "테스트 정지"


@pytest.mark.asyncio
async def test_login_with_deleted_account_returns_401(client: AsyncClient, fake):
    """탈퇴(soft delete)한 계정으로 로그인 시 401을 반환한다."""
    user = await create_verified_user(client, fake)

    # 회원 탈퇴 API 호출
    res = await user["client"].request(
        "DELETE",
        "/v1/users/me",
        json={"password": user["payload"]["password"], "agree": True},
    )
    assert res.status_code == 200

    # 탈퇴 후 로그인 시도
    res = await client.post(
        "/v1/auth/session",
        json={"email": user["email"], "password": user["payload"]["password"]},
    )

    assert res.status_code == 401


# ---------------------------------------------------------------------------
# 로그아웃
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_logout_invalidates_refresh_token(client: AsyncClient, fake):
    """로그아웃 후 refresh token으로 갱신 시도 시 실패한다."""
    user = await create_verified_user(client, fake)

    # 로그아웃
    logout_res = await user["client"].delete("/v1/auth/session")
    assert logout_res.status_code == 200

    # 로그아웃 후 토큰 갱신 시도 — 쿠키가 삭제되었으므로 401
    refresh_res = await user["client"].post("/v1/auth/token/refresh")
    assert refresh_res.status_code == 401


@pytest.mark.asyncio
async def test_logout_then_relogin_succeeds(client: AsyncClient, fake):
    """로그아웃 후 동일 계정으로 재로그인이 성공한다."""
    user = await create_verified_user(client, fake)

    # 로그아웃
    await user["client"].delete("/v1/auth/session")

    # 재로그인
    res = await client.post(
        "/v1/auth/session",
        json={"email": user["email"], "password": user["payload"]["password"]},
    )

    assert res.status_code == 200
    assert "access_token" in res.json()["data"]
