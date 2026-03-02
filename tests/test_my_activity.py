"""내 활동 API 테스트."""

import pytest


@pytest.mark.asyncio
async def test_my_posts(authorized_user):
    """내가 쓴 글 목록을 조회합니다."""
    client, _, _ = authorized_user

    await client.post("/v1/posts/", json={"title": "내 글 1", "content": "내용"})
    await client.post("/v1/posts/", json={"title": "내 글 2", "content": "내용"})

    res = await client.get("/v1/users/me/posts")
    assert res.status_code == 200

    data = res.json()["data"]
    assert len(data["posts"]) == 2
    assert data["pagination"]["total_count"] == 2


@pytest.mark.asyncio
async def test_my_comments(authorized_user):
    """내가 쓴 댓글 목록을 조회합니다."""
    client, _, _ = authorized_user

    post_res = await client.post(
        "/v1/posts/", json={"title": "게시글", "content": "내용"}
    )
    post_id = post_res.json()["data"]["post_id"]

    await client.post(f"/v1/posts/{post_id}/comments", json={"content": "댓글 1"})
    await client.post(f"/v1/posts/{post_id}/comments", json={"content": "댓글 2"})

    res = await client.get("/v1/users/me/comments")
    assert res.status_code == 200

    data = res.json()["data"]
    assert len(data["comments"]) == 2
    assert data["pagination"]["total_count"] == 2
    assert data["comments"][0]["post_id"] == post_id


@pytest.mark.asyncio
async def test_my_likes(authorized_user):
    """좋아요한 글 목록을 조회합니다."""
    client, _, _ = authorized_user

    post_res = await client.post(
        "/v1/posts/", json={"title": "게시글", "content": "내용"}
    )
    post_id = post_res.json()["data"]["post_id"]

    await client.post(f"/v1/posts/{post_id}/likes", json={})

    res = await client.get("/v1/users/me/likes")
    assert res.status_code == 200

    data = res.json()["data"]
    assert len(data["posts"]) == 1
    assert data["posts"][0]["post_id"] == post_id


@pytest.mark.asyncio
async def test_my_activity_unauthenticated(client):
    """미로그인 시 401을 반환합니다."""
    res = await client.get("/v1/users/me/posts")
    assert res.status_code == 401
