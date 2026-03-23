"""Auth 도메인 — 비밀번호 재설정 / 이메일 찾기 테스트."""

import pytest
from httpx import AsyncClient

from tests.conftest import create_verified_user

# ---------------------------------------------------------------------------
# 비밀번호 재설정
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reset_password_request_returns_200(client: AsyncClient, fake):
    """존재하는 이메일로 비밀번호 재설정 요청 시 200을 반환한다."""
    user = await create_verified_user(client, fake)

    res = await client.post(
        "/v1/users/reset-password",
        json={"email": user["email"]},
    )

    assert res.status_code == 200
    assert res.json()["code"] == "RESET_PASSWORD_SUCCESS"


@pytest.mark.asyncio
async def test_reset_password_nonexistent_email_returns_200(client: AsyncClient, fake):
    """존재하지 않는 이메일로 비밀번호 재설정 요청 시에도 200을 반환한다 (anti-enumeration)."""
    res = await client.post(
        "/v1/users/reset-password",
        json={"email": "nonexistent@example.com"},
    )

    # 보안: 이메일 존재 여부와 무관하게 동일 응답
    assert res.status_code == 200
    assert res.json()["code"] == "RESET_PASSWORD_SUCCESS"


# ---------------------------------------------------------------------------
# 이메일 찾기
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_find_email_by_nickname_returns_masked_email(client: AsyncClient, fake):
    """닉네임으로 이메일 찾기 시 마스킹된 이메일을 반환한다."""
    user = await create_verified_user(client, fake)

    res = await client.post(
        "/v1/users/find-email",
        json={"nickname": user["nickname"]},
    )

    assert res.status_code == 200
    data = res.json()["data"]
    assert "masked_email" in data
    # 마스킹된 이메일은 원본과 달라야 함 (일부가 *로 치환)
    assert "*" in data["masked_email"]
