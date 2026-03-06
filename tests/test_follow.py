"""test_follow: 팔로우 시스템 테스트."""

import pytest
from httpx import ASGITransport, AsyncClient

from main import app
from database.connection import get_connection


# -- 헬퍼: 두 번째 인증 사용자 생성 --
async def _create_second_user(client):
    """두 번째 인증 사용자를 생성하고 로그인된 클라이언트를 반환합니다."""
    payload = {
        "email": "follow_target@test.com",
        "password": "Password123!",
        "nickname": "FTarget",
    }
    await client.post("/v1/users/", data=payload)

    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE user SET email_verified = 1 WHERE email = %s",
                ("follow_target@test.com",),
            )
            await conn.commit()
            await cur.execute(
                "SELECT id FROM user WHERE email = %s",
                ("follow_target@test.com",),
            )
            row = await cur.fetchone()
            user_id = row[0]

    login_res = await client.post(
        "/v1/auth/session",
        json={"email": "follow_target@test.com", "password": "Password123!"},
    )
    token = login_res.json()["data"]["access_token"]

    transport = ASGITransport(app=app)
    auth_client = AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
        cookies=login_res.cookies,
    )
    return auth_client, user_id


@pytest.mark.asyncio
async def test_follow_01_follow_user(client, authorized_user):
    """팔로우 성공 (201)."""
    cli, _, _ = authorized_user
    target_cli, target_id = await _create_second_user(client)
    async with target_cli:
        res = await cli.post(f"/v1/users/{target_id}/follow")
        assert res.status_code == 201
        assert res.json()["code"] == "USER_FOLLOWED"


@pytest.mark.asyncio
async def test_follow_02_duplicate_follow(client, authorized_user):
    """중복 팔로우 (409)."""
    cli, _, _ = authorized_user
    target_cli, target_id = await _create_second_user(client)
    async with target_cli:
        await cli.post(f"/v1/users/{target_id}/follow")
        res = await cli.post(f"/v1/users/{target_id}/follow")
        assert res.status_code == 409
        assert res.json()["detail"]["error"] == "already_following"


@pytest.mark.asyncio
async def test_follow_03_follow_self(client, authorized_user):
    """자기 자신 팔로우 (400)."""
    cli, user_info, _ = authorized_user
    res = await cli.post(f"/v1/users/{user_info['user_id']}/follow")
    assert res.status_code == 400
    assert res.json()["detail"]["error"] == "cannot_follow_self"


@pytest.mark.asyncio
async def test_follow_04_follow_nonexistent(client, authorized_user):
    """존재하지 않는 사용자 팔로우 (404)."""
    cli, _, _ = authorized_user
    res = await cli.post("/v1/users/999999/follow")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_follow_05_unfollow(client, authorized_user):
    """언팔로우 성공 (200)."""
    cli, _, _ = authorized_user
    target_cli, target_id = await _create_second_user(client)
    async with target_cli:
        await cli.post(f"/v1/users/{target_id}/follow")
        res = await cli.delete(f"/v1/users/{target_id}/follow")
        assert res.status_code == 200
        assert res.json()["code"] == "USER_UNFOLLOWED"


@pytest.mark.asyncio
async def test_follow_06_unfollow_not_following(client, authorized_user):
    """팔로우하지 않은 사용자 언팔로우 (404)."""
    cli, _, _ = authorized_user
    target_cli, target_id = await _create_second_user(client)
    async with target_cli:
        res = await cli.delete(f"/v1/users/{target_id}/follow")
        assert res.status_code == 404


@pytest.mark.asyncio
async def test_follow_07_my_following_list(client, authorized_user):
    """팔로잉 목록 조회."""
    cli, _, _ = authorized_user
    target_cli, target_id = await _create_second_user(client)
    async with target_cli:
        await cli.post(f"/v1/users/{target_id}/follow")
        res = await cli.get("/v1/users/me/following")
        assert res.status_code == 200
        data = res.json()["data"]
        assert len(data["following"]) == 1
        assert data["following"][0]["user_id"] == target_id


@pytest.mark.asyncio
async def test_follow_08_my_followers_list(client, authorized_user):
    """팔로워 목록 조회."""
    cli, _, _ = authorized_user
    target_cli, target_id = await _create_second_user(client)
    async with target_cli:
        await cli.post(f"/v1/users/{target_id}/follow")
        res = await target_cli.get("/v1/users/me/followers")
        assert res.status_code == 200
        data = res.json()["data"]
        assert len(data["followers"]) == 1


@pytest.mark.asyncio
async def test_follow_09_follow_counts_in_profile(client, authorized_user):
    """프로필에 팔로워/팔로잉 카운트 포함."""
    cli, _, _ = authorized_user
    target_cli, target_id = await _create_second_user(client)
    async with target_cli:
        await cli.post(f"/v1/users/{target_id}/follow")
        res = await cli.get(f"/v1/users/{target_id}")
        assert res.status_code == 200
        user = res.json()["data"]["user"]
        assert "followers_count" in user
        assert user["followers_count"] == 1


@pytest.mark.asyncio
async def test_follow_10_notification_on_new_post(client, authorized_user):
    """팔로우한 사용자가 게시글 작성 시 알림 생성."""
    cli, user_info, _ = authorized_user
    target_cli, target_id = await _create_second_user(client)
    async with target_cli:
        # cli가 target을 팔로우
        await cli.post(f"/v1/users/{target_id}/follow")
        # target이 게시글 작성
        post_res = await target_cli.post(
            "/v1/posts/",
            json={
                "title": "팔로우 알림 테스트",
                "content": "테스트 게시글입니다.",
                "category_id": 1,
            },
        )
        assert post_res.status_code == 201
        # cli의 알림 확인
        notif_res = await cli.get("/v1/notifications/")
        assert notif_res.status_code == 200
        notifications = notif_res.json()["data"]["notifications"]
        follow_notifs = [n for n in notifications if n["type"] == "follow"]
        assert len(follow_notifs) >= 1
        assert follow_notifs[0]["actor"]["nickname"] == "FTarget"


@pytest.mark.asyncio
async def test_follow_11_unauthorized(client):
    """비로그인 팔로우 (401)."""
    res = await client.post("/v1/users/1/follow")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_follow_12_is_following_in_profile(client, authorized_user):
    """프로필 조회 시 is_following 포함."""
    cli, _, _ = authorized_user
    target_cli, target_id = await _create_second_user(client)
    async with target_cli:
        await cli.post(f"/v1/users/{target_id}/follow")
        res = await cli.get(f"/v1/users/{target_id}")
        assert res.status_code == 200
        assert res.json()["data"]["user"]["is_following"] is True
