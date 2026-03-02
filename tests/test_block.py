"""test_block: 사용자 차단 기능 테스트."""

import pytest
from httpx import AsyncClient, ASGITransport
from database.connection import get_connection
from main import app


async def _create_second_authorized_user(client: AsyncClient) -> tuple[AsyncClient, dict]:
    """두 번째 인증 사용자를 생성합니다."""
    payload = {
        "email": "block_target@example.com",
        "password": "Password123!",
        "nickname": "blocktest1",
    }
    signup_res = await client.post("/v1/users/", data=payload)
    assert signup_res.status_code == 201

    # 이메일 인증
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE user SET email_verified = 1 WHERE email = %s",
                (payload["email"],),
            )

    login_res = await client.post(
        "/v1/auth/session",
        json={"email": payload["email"], "password": payload["password"]},
    )
    assert login_res.status_code == 200

    data = login_res.json()
    access_token = data["data"]["access_token"]
    user_info = data["data"]["user"]

    transport = ASGITransport(app=app)
    auth_client = AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {access_token}"},
        cookies=login_res.cookies,
    )

    return auth_client, user_info


@pytest.mark.asyncio
async def test_block_user(client: AsyncClient, authorized_user):
    """사용자 차단 (201)."""
    cli, _, _ = authorized_user
    target_cli, target_info = await _create_second_authorized_user(client)

    async with target_cli:
        res = await cli.post(f"/v1/users/{target_info['user_id']}/block")
        assert res.status_code == 201
        assert res.json()["code"] == "USER_BLOCKED"


@pytest.mark.asyncio
async def test_block_duplicate(client: AsyncClient, authorized_user):
    """중복 차단 (409)."""
    cli, _, _ = authorized_user
    target_cli, target_info = await _create_second_authorized_user(client)

    async with target_cli:
        await cli.post(f"/v1/users/{target_info['user_id']}/block")
        res = await cli.post(f"/v1/users/{target_info['user_id']}/block")
        assert res.status_code == 409
        assert res.json()["detail"]["error"] == "already_blocked"


@pytest.mark.asyncio
async def test_block_self(client: AsyncClient, authorized_user):
    """자기 자신 차단 (400)."""
    cli, user_info, _ = authorized_user

    res = await cli.post(f"/v1/users/{user_info['user_id']}/block")
    assert res.status_code == 400
    assert res.json()["detail"]["error"] == "cannot_block_self"


@pytest.mark.asyncio
async def test_block_nonexistent_user(client: AsyncClient, authorized_user):
    """존재하지 않는 사용자 차단 (404)."""
    cli, _, _ = authorized_user

    res = await cli.post("/v1/users/99999/block")
    assert res.status_code == 404
    assert res.json()["detail"]["error"] == "user_not_found"


@pytest.mark.asyncio
async def test_unblock_user(client: AsyncClient, authorized_user):
    """차단 해제 (200)."""
    cli, _, _ = authorized_user
    target_cli, target_info = await _create_second_authorized_user(client)

    async with target_cli:
        await cli.post(f"/v1/users/{target_info['user_id']}/block")
        res = await cli.delete(f"/v1/users/{target_info['user_id']}/block")
        assert res.status_code == 200
        assert res.json()["code"] == "USER_UNBLOCKED"


@pytest.mark.asyncio
async def test_unblock_not_blocked(client: AsyncClient, authorized_user):
    """차단하지 않은 사용자 해제 (404)."""
    cli, _, _ = authorized_user
    target_cli, target_info = await _create_second_authorized_user(client)

    async with target_cli:
        res = await cli.delete(f"/v1/users/{target_info['user_id']}/block")
        assert res.status_code == 404
        assert res.json()["detail"]["error"] == "block_not_found"


@pytest.mark.asyncio
async def test_block_unauthorized(client: AsyncClient):
    """미인증 사용자 차단 (401)."""
    res = await client.post("/v1/users/1/block")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_my_blocks_list(client: AsyncClient, authorized_user):
    """차단 목록 조회."""
    cli, _, _ = authorized_user
    target_cli, target_info = await _create_second_authorized_user(client)

    async with target_cli:
        await cli.post(f"/v1/users/{target_info['user_id']}/block")

    res = await cli.get("/v1/users/me/blocks")
    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data["blocks"]) == 1
    assert data["blocks"][0]["user_id"] == target_info["user_id"]
    assert data["pagination"]["total_count"] == 1


@pytest.mark.asyncio
async def test_blocked_user_posts_hidden(client: AsyncClient, authorized_user):
    """차단된 사용자 게시글이 목록에서 숨겨지는지 확인."""
    cli, _, _ = authorized_user
    target_cli, target_info = await _create_second_authorized_user(client)

    async with target_cli:
        # 차단 대상이 게시글 작성
        await target_cli.post(
            "/v1/posts/",
            json={"title": "차단 대상 글", "content": "내용입니다", "category_id": 1},
        )

        # 차단 전: 목록에 보임
        before = await cli.get("/v1/posts/")
        before_posts = before.json()["data"]["posts"]
        assert any(p["title"] == "차단 대상 글" for p in before_posts)

        # 차단
        await cli.post(f"/v1/users/{target_info['user_id']}/block")

        # 차단 후: 목록에서 숨김
        after = await cli.get("/v1/posts/")
        after_posts = after.json()["data"]["posts"]
        assert not any(p["title"] == "차단 대상 글" for p in after_posts)


@pytest.mark.asyncio
async def test_blocked_user_comments_hidden(client: AsyncClient, authorized_user):
    """차단된 사용자 댓글이 상세에서 숨겨지는지 확인."""
    cli, _, _ = authorized_user
    target_cli, target_info = await _create_second_authorized_user(client)

    async with target_cli:
        # 내가 게시글 작성
        post_res = await cli.post(
            "/v1/posts/",
            json={"title": "댓글 차단 테스트", "content": "내용입니다", "category_id": 1},
        )
        post_id = post_res.json()["data"]["post_id"]

        # 차단 대상이 댓글 작성
        await target_cli.post(
            f"/v1/posts/{post_id}/comments",
            json={"content": "차단 대상 댓글"},
        )

        # 차단 전: 댓글 보임
        before = await cli.get(f"/v1/posts/{post_id}")
        before_comments = before.json()["data"]["comments"]
        assert len(before_comments) == 1

        # 차단
        await cli.post(f"/v1/users/{target_info['user_id']}/block")

        # 차단 후: 댓글 숨김
        after = await cli.get(f"/v1/posts/{post_id}")
        after_comments = after.json()["data"]["comments"]
        assert len(after_comments) == 0
