"""팔로잉 피드 API 테스트.

GET /v1/posts/?following=true 쿼리 파라미터로
팔로우한 사용자의 게시글만 조회하는 기능을 검증합니다.
"""

import pytest

from tests.conftest import create_verified_user, create_test_post


@pytest.mark.asyncio
async def test_following_feed_shows_only_followed_users_posts(client, fake):
    """팔로우한 사용자의 게시글만 반환된다."""
    user1 = await create_verified_user(client, fake)
    user2 = await create_verified_user(client, fake)
    user3 = await create_verified_user(client, fake)

    # user2, user3이 각각 게시글 작성
    post2 = await create_test_post(client, user2["headers"], title="user2의 글")
    post3 = await create_test_post(client, user3["headers"], title="user3의 글")

    # user1이 user2만 팔로우
    follow_res = await client.post(
        f"/v1/users/{user2['user_id']}/follow",
        headers=user1["headers"],
    )
    assert follow_res.status_code == 201

    # 팔로잉 피드 조회
    res = await client.get(
        "/v1/posts/",
        params={"following": "true"},
        headers=user1["headers"],
    )
    assert res.status_code == 200

    posts = res.json()["data"]["posts"]
    post_ids = [p["post_id"] for p in posts]

    assert post2["post_id"] in post_ids
    assert post3["post_id"] not in post_ids


@pytest.mark.asyncio
async def test_following_feed_with_category_filter(client, fake):
    """팔로잉 피드 + 카테고리 필터가 함께 동작한다."""
    user1 = await create_verified_user(client, fake)
    user2 = await create_verified_user(client, fake)

    # user2가 다른 카테고리에 게시글 작성
    post_cat1 = await create_test_post(
        client, user2["headers"], title="자유게시판 글", category_id=1
    )
    post_cat2 = await create_test_post(
        client, user2["headers"], title="질문답변 글", category_id=2
    )

    # user1이 user2를 팔로우
    res = await client.post(
        f"/v1/users/{user2['user_id']}/follow",
        headers=user1["headers"],
    )
    assert res.status_code == 201

    # 카테고리 1로 필터링
    res = await client.get(
        "/v1/posts/",
        params={"following": "true", "category_id": 1},
        headers=user1["headers"],
    )
    assert res.status_code == 200

    posts = res.json()["data"]["posts"]
    post_ids = [p["post_id"] for p in posts]

    assert post_cat1["post_id"] in post_ids
    assert post_cat2["post_id"] not in post_ids


@pytest.mark.asyncio
async def test_following_feed_empty_when_no_following(client, fake):
    """팔로잉 0명이면 빈 배열을 반환한다."""
    user1 = await create_verified_user(client, fake)
    user2 = await create_verified_user(client, fake)

    # user2가 게시글 작성 (user1은 팔로우하지 않음)
    await create_test_post(client, user2["headers"], title="팔로우 안 한 글")

    res = await client.get(
        "/v1/posts/",
        params={"following": "true"},
        headers=user1["headers"],
    )
    assert res.status_code == 200

    data = res.json()["data"]
    assert data["posts"] == []
    assert data["pagination"]["total_count"] == 0
    assert data["pagination"]["has_more"] is False


@pytest.mark.asyncio
async def test_following_feed_sorting(client, fake):
    """팔로잉 피드에서 sort=latest 정렬이 동작한다."""
    user1 = await create_verified_user(client, fake)
    user2 = await create_verified_user(client, fake)

    # user2가 게시글 2개 작성
    await create_test_post(
        client, user2["headers"], title="첫 번째 글"
    )
    await create_test_post(
        client, user2["headers"], title="두 번째 글"
    )

    # user1이 user2를 팔로우
    res = await client.post(
        f"/v1/users/{user2['user_id']}/follow",
        headers=user1["headers"],
    )
    assert res.status_code == 201

    # 최신순 정렬
    res = await client.get(
        "/v1/posts/",
        params={"following": "true", "sort": "latest"},
        headers=user1["headers"],
    )
    assert res.status_code == 200

    posts = res.json()["data"]["posts"]
    assert len(posts) == 2
    # 최신순: 두 번째 글이 먼저
    assert posts[0]["title"] == "두 번째 글"
    assert posts[1]["title"] == "첫 번째 글"
