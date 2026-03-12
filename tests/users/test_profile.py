"""Users 도메인 — 프로필 조회/수정 테스트."""

import pytest
from httpx import AsyncClient

from tests.conftest import create_verified_user


# ---------------------------------------------------------------------------
# 내 프로필 조회
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_my_profile_returns_full_info(client: AsyncClient, fake):
    """GET /v1/users/me — 이메일 등 전체 정보를 반환한다."""
    # Arrange
    user = await create_verified_user(client, fake)

    # Act
    res = await user["client"].get("/v1/users/me")

    # Assert
    assert res.status_code == 200
    data = res.json()["data"]["user"]
    assert data["email"] == user["email"]
    assert data["nickname"] == user["nickname"]
    assert "profileImageUrl" in data
    assert "role" in data


@pytest.mark.asyncio
async def test_get_profile_without_auth_returns_401(client: AsyncClient):
    """인증 없이 GET /v1/users/me 요청 시 401을 반환한다."""
    res = await client.get("/v1/users/me")

    assert res.status_code == 401


# ---------------------------------------------------------------------------
# 타 사용자 프로필 조회
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_other_user_profile_returns_public_info(client: AsyncClient, fake):
    """GET /v1/users/{user_id} — 이메일 없이 공개 정보만 반환한다."""
    # Arrange
    user = await create_verified_user(client, fake)

    # Act — 인증 없이 타 사용자 프로필 조회
    res = await client.get(f"/v1/users/{user['user_id']}")

    # Assert
    assert res.status_code == 200
    data = res.json()["data"]["user"]
    assert data["user_id"] == user["user_id"]
    assert data["nickname"] == user["nickname"]
    assert "email" not in data  # 타 사용자에게 이메일 비공개


# ---------------------------------------------------------------------------
# 프로필 수정
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_nickname_succeeds(client: AsyncClient, fake):
    """PATCH /v1/users/me — 닉네임 변경이 성공한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    new_nickname = fake.lexify(text="?????") + "00"

    # Act
    res = await user["client"].patch(
        "/v1/users/me",
        json={"nickname": new_nickname},
    )

    # Assert
    assert res.status_code == 200
    data = res.json()["data"]["user"]
    assert data["nickname"] == new_nickname


@pytest.mark.asyncio
async def test_update_profile_image_url_succeeds(client: AsyncClient, fake):
    """PATCH /v1/users/me — 프로필 이미지 URL 변경이 성공한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    new_url = "/uploads/profiles/test_image.jpg"

    # Act
    res = await user["client"].patch(
        "/v1/users/me",
        json={"profileImageUrl": new_url},
    )

    # Assert
    assert res.status_code == 200
    data = res.json()["data"]["user"]
    assert data["profileImageUrl"] == new_url


@pytest.mark.asyncio
async def test_update_to_duplicate_nickname_returns_409(client: AsyncClient, fake):
    """이미 사용 중인 닉네임으로 변경 시도 시 409를 반환한다."""
    # Arrange — 두 사용자 생성
    user1 = await create_verified_user(client, fake)
    user2 = await create_verified_user(client, fake)

    # Act — user2가 user1의 닉네임으로 변경 시도
    res = await user2["client"].patch(
        "/v1/users/me",
        json={"nickname": user1["nickname"]},
    )

    # Assert
    assert res.status_code == 409
