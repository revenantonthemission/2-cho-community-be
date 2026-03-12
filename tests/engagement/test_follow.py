"""Engagement 도메인 -- 팔로우 테스트."""

import pytest
from httpx import AsyncClient

from tests.conftest import create_verified_user


# ---------------------------------------------------------------------------
# 팔로우 / 언팔로우
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_follow_user_returns_201(client: AsyncClient, fake):
    """사용자 팔로우 시 201을 반환한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    target = await create_verified_user(client, fake)

    # Act
    res = await client.post(
        f"/v1/users/{target['user_id']}/follow",
        headers=user["headers"],
    )

    # Assert
    assert res.status_code == 201
    assert res.json()["code"] == "USER_FOLLOWED"


@pytest.mark.asyncio
async def test_unfollow_user_returns_200(client: AsyncClient, fake):
    """팔로우 해제 시 200을 반환한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    target = await create_verified_user(client, fake)

    # 팔로우 먼저
    follow_res = await client.post(
        f"/v1/users/{target['user_id']}/follow",
        headers=user["headers"],
    )
    assert follow_res.status_code == 201

    # Act
    res = await client.delete(
        f"/v1/users/{target['user_id']}/follow",
        headers=user["headers"],
    )

    # Assert
    assert res.status_code == 200
    assert res.json()["code"] == "USER_UNFOLLOWED"


@pytest.mark.asyncio
async def test_follow_self_returns_400(client: AsyncClient, fake):
    """자기 자신을 팔로우하면 400을 반환한다."""
    # Arrange
    user = await create_verified_user(client, fake)

    # Act
    res = await client.post(
        f"/v1/users/{user['user_id']}/follow",
        headers=user["headers"],
    )

    # Assert
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_duplicate_follow_returns_409(client: AsyncClient, fake):
    """동일 사용자를 중복 팔로우하면 409를 반환한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    target = await create_verified_user(client, fake)

    # 첫 번째 팔로우
    first = await client.post(
        f"/v1/users/{target['user_id']}/follow",
        headers=user["headers"],
    )
    assert first.status_code == 201

    # Act -- 중복 팔로우
    res = await client.post(
        f"/v1/users/{target['user_id']}/follow",
        headers=user["headers"],
    )

    # Assert
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_follow_count_updates(client: AsyncClient, fake):
    """팔로우 후 프로필에서 팔로워/팔로잉 수가 갱신된다."""
    # Arrange
    user = await create_verified_user(client, fake)
    target = await create_verified_user(client, fake)

    # 팔로우
    follow_res = await client.post(
        f"/v1/users/{target['user_id']}/follow",
        headers=user["headers"],
    )
    assert follow_res.status_code == 201

    # Act -- 타겟 프로필 조회 (팔로워 수)
    profile_res = await client.get(
        f"/v1/users/{target['user_id']}",
        headers=user["headers"],
    )

    # Assert
    assert profile_res.status_code == 200
    profile = profile_res.json()["data"]["user"]
    assert profile["followers_count"] >= 1

    # Act -- 팔로잉 사용자 본인 정보 조회
    my_res = await client.get(
        "/v1/users/me",
        headers=user["headers"],
    )
    assert my_res.status_code == 200
    my_data = my_res.json()["data"]["user"]
    assert my_data["following_count"] >= 1


@pytest.mark.asyncio
async def test_my_following_list(client: AsyncClient, fake):
    """팔로우한 사용자가 팔로잉 목록에 나타난다."""
    # Arrange
    user = await create_verified_user(client, fake)
    target = await create_verified_user(client, fake)

    # 팔로우
    follow_res = await client.post(
        f"/v1/users/{target['user_id']}/follow",
        headers=user["headers"],
    )
    assert follow_res.status_code == 201

    # Act
    res = await client.get(
        "/v1/users/me/following",
        headers=user["headers"],
    )

    # Assert
    assert res.status_code == 200
    items = res.json()["data"]["following"]
    user_ids = [item["user_id"] for item in items]
    assert target["user_id"] in user_ids


@pytest.mark.asyncio
async def test_my_followers_list(client: AsyncClient, fake):
    """팔로우한 사용자가 상대방의 팔로워 목록에 나타난다."""
    # Arrange
    user = await create_verified_user(client, fake)
    target = await create_verified_user(client, fake)

    # 팔로우
    follow_res = await client.post(
        f"/v1/users/{target['user_id']}/follow",
        headers=user["headers"],
    )
    assert follow_res.status_code == 201

    # Act -- 타겟 사용자가 자신의 팔로워 목록 조회
    res = await client.get(
        "/v1/users/me/followers",
        headers=target["headers"],
    )

    # Assert
    assert res.status_code == 200
    items = res.json()["data"]["followers"]
    user_ids = [item["user_id"] for item in items]
    assert user["user_id"] in user_ids


@pytest.mark.asyncio
async def test_follow_creates_notification(client: AsyncClient, fake):
    """팔로우 시 대상 사용자에게 알림이 생성된다."""
    # Arrange
    user = await create_verified_user(client, fake)
    target = await create_verified_user(client, fake)

    # Act -- 팔로우
    follow_res = await client.post(
        f"/v1/users/{target['user_id']}/follow",
        headers=user["headers"],
    )
    assert follow_res.status_code == 201

    # Assert -- 대상 사용자의 알림 확인
    notif_res = await client.get(
        "/v1/notifications/",
        headers=target["headers"],
    )
    assert notif_res.status_code == 200
    notifications = notif_res.json()["data"]["notifications"]
    follow_notifs = [n for n in notifications if n["type"] == "follow"]
    assert len(follow_notifs) >= 1


@pytest.mark.asyncio
async def test_mutual_follow_status(client: AsyncClient, fake):
    """양쪽이 서로 팔로우하면 상호 팔로우 상태가 된다."""
    # Arrange
    user_a = await create_verified_user(client, fake)
    user_b = await create_verified_user(client, fake)

    # Act -- A가 B를 팔로우
    res_ab = await client.post(
        f"/v1/users/{user_b['user_id']}/follow",
        headers=user_a["headers"],
    )
    assert res_ab.status_code == 201

    # Act -- B가 A를 팔로우
    res_ba = await client.post(
        f"/v1/users/{user_a['user_id']}/follow",
        headers=user_b["headers"],
    )
    assert res_ba.status_code == 201

    # Assert -- A의 프로필을 B가 조회하면 is_following=True
    profile_a = await client.get(
        f"/v1/users/{user_a['user_id']}",
        headers=user_b["headers"],
    )
    assert profile_a.status_code == 200
    assert profile_a.json()["data"]["user"]["is_following"] is True

    # Assert -- B의 프로필을 A가 조회하면 is_following=True
    profile_b = await client.get(
        f"/v1/users/{user_b['user_id']}",
        headers=user_a["headers"],
    )
    assert profile_b.status_code == 200
    assert profile_b.json()["data"]["user"]["is_following"] is True
