"""타 사용자 프로필 관련 테스트."""

import pytest


@pytest.mark.asyncio
async def test_get_user_profile(authorized_user, client):
    """타 사용자 프로필을 조회합니다 (이메일 비공개)."""
    _, user_info, _ = authorized_user
    user_id = user_info["user_id"]

    res = await client.get(f"/v1/users/{user_id}")
    assert res.status_code == 200

    data = res.json()["data"]
    user = data["user"]
    assert user["user_id"] == user_id
    assert "nickname" in user
    assert "email" not in user  # 타 사용자에게 이메일 비공개


@pytest.mark.asyncio
async def test_filter_posts_by_author(authorized_user):
    """author_id로 게시글을 필터링합니다."""
    client, user_info, _ = authorized_user
    user_id = user_info["user_id"]

    await client.post("/v1/posts/", json={"title": "내 글", "content": "내용", "category_id": 1})

    res = await client.get(f"/v1/posts/?author_id={user_id}")
    assert res.status_code == 200

    posts = res.json()["data"]["posts"]
    assert len(posts) >= 1
    for post in posts:
        assert post["author"]["user_id"] == user_id
