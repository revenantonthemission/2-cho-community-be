"""Users 도메인 — 비밀번호 변경 테스트."""

import pytest
from httpx import AsyncClient

from tests.conftest import create_verified_user

# ---------------------------------------------------------------------------
# 비밀번호 변경 성공
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_change_password_succeeds(client: AsyncClient, fake):
    """PUT /v1/users/me/password — 올바른 현재 비밀번호로 변경이 성공한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    new_password = "NewPassword1!"

    # Act
    res = await user["client"].put(
        "/v1/users/me/password",
        json={
            "current_password": user["payload"]["password"],
            "new_password": new_password,
            "new_password_confirm": new_password,
        },
    )

    # Assert
    assert res.status_code == 200

    # 변경된 비밀번호로 로그인 가능 확인
    login_res = await client.post(
        "/v1/auth/session",
        json={"email": user["email"], "password": new_password},
    )
    assert login_res.status_code == 200


# ---------------------------------------------------------------------------
# 비밀번호 변경 실패
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_change_password_wrong_current_returns_400(client: AsyncClient, fake):
    """현재 비밀번호가 틀리면 400을 반환한다."""
    # Arrange
    user = await create_verified_user(client, fake)

    # Act
    res = await user["client"].put(
        "/v1/users/me/password",
        json={
            "current_password": "WrongPassword1!",
            "new_password": "NewPassword1!",
            "new_password_confirm": "NewPassword1!",
        },
    )

    # Assert
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_change_password_invalid_new_returns_422(client: AsyncClient, fake):
    """새 비밀번호가 유효성 규칙을 충족하지 않으면 422를 반환한다."""
    # Arrange
    user = await create_verified_user(client, fake)

    # Act — 특수문자/대문자 없는 짧은 비밀번호
    res = await user["client"].put(
        "/v1/users/me/password",
        json={
            "current_password": user["payload"]["password"],
            "new_password": "short",
            "new_password_confirm": "short",
        },
    )

    # Assert — Pydantic 유효성 검증 실패
    assert res.status_code == 422
