"""Users 도메인 — 회원 탈퇴 테스트."""

import pytest
from httpx import AsyncClient

from tests.conftest import create_verified_user

# ---------------------------------------------------------------------------
# 탈퇴 성공
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_withdraw_account_succeeds(client: AsyncClient, fake):
    """DELETE /v1/users/me — 올바른 비밀번호와 동의로 탈퇴가 성공한다."""
    # Arrange
    user = await create_verified_user(client, fake)

    # Act
    res = await user["client"].request(
        "DELETE",
        "/v1/users/me",
        json={
            "password": user["payload"]["password"],
            "agree": True,
        },
    )

    # Assert
    assert res.status_code == 200
    assert res.json()["code"] == "WITHDRAWAL_ACCEPTED"


# ---------------------------------------------------------------------------
# 탈퇴 후 접근 불가 확인
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_after_withdrawal_returns_401(client: AsyncClient, fake):
    """탈퇴(soft delete) 후 로그인 시도 시 401을 반환한다."""
    # Arrange
    user = await create_verified_user(client, fake)

    # 탈퇴 실행
    del_res = await user["client"].request(
        "DELETE",
        "/v1/users/me",
        json={
            "password": user["payload"]["password"],
            "agree": True,
        },
    )
    assert del_res.status_code == 200

    # Act — 탈퇴 후 로그인 시도
    login_res = await client.post(
        "/v1/auth/session",
        json={
            "email": user["email"],
            "password": user["payload"]["password"],
        },
    )

    # Assert
    assert login_res.status_code == 401


@pytest.mark.asyncio
async def test_get_profile_after_withdrawal_returns_404(client: AsyncClient, fake):
    """탈퇴한 사용자의 프로필 조회 시 404를 반환한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    user_id = user["user_id"]

    # 탈퇴 실행
    del_res = await user["client"].request(
        "DELETE",
        "/v1/users/me",
        json={
            "password": user["payload"]["password"],
            "agree": True,
        },
    )
    assert del_res.status_code == 200

    # Act — 인증 없이 공개 프로필 조회
    res = await client.get(f"/v1/users/{user_id}")

    # Assert — soft delete된 사용자는 조회 불가
    assert res.status_code == 404
