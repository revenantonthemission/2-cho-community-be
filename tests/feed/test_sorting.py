"""게시글 정렬 옵션 API 테스트.

GET /v1/posts/?sort=... 쿼리 파라미터로
다양한 정렬 옵션(latest, likes, views, comments, hot)을 검증합니다.
"""

import pytest

from tests.conftest import (
    create_test_comment,
    create_test_post,
    create_verified_user,
)


@pytest.mark.asyncio
async def test_sort_by_latest(client, fake):
    """기본 정렬(latest): 최신 게시글이 먼저 반환된다."""
    user = await create_verified_user(client, fake)

    post_old = await create_test_post(client, user["headers"], title="오래된 글")
    post_new = await create_test_post(client, user["headers"], title="최신 글")

    res = await client.get("/v1/posts/", params={"sort": "latest"})
    assert res.status_code == 200

    posts = res.json()["data"]["posts"]
    post_ids = [p["post_id"] for p in posts]

    idx_new = post_ids.index(post_new["post_id"])
    idx_old = post_ids.index(post_old["post_id"])
    assert idx_new < idx_old


@pytest.mark.asyncio
async def test_sort_by_likes(client, fake):
    """likes 정렬: 좋아요가 많은 게시글이 먼저 반환된다."""
    user1 = await create_verified_user(client, fake)
    user2 = await create_verified_user(client, fake)

    post_no_like = await create_test_post(client, user1["headers"], title="좋아요 없는 글")
    post_liked = await create_test_post(client, user1["headers"], title="좋아요 있는 글")

    # user2가 post_liked에 좋아요
    like_res = await client.post(
        f"/v1/posts/{post_liked['post_id']}/likes",
        headers=user2["headers"],
    )
    assert like_res.status_code == 201

    res = await client.get("/v1/posts/", params={"sort": "likes"})
    assert res.status_code == 200

    posts = res.json()["data"]["posts"]
    post_ids = [p["post_id"] for p in posts]

    idx_liked = post_ids.index(post_liked["post_id"])
    idx_no_like = post_ids.index(post_no_like["post_id"])
    assert idx_liked < idx_no_like


@pytest.mark.asyncio
async def test_sort_by_views(client, fake):
    """views 정렬: 조회수가 많은 게시글이 먼저 반환된다."""
    user1 = await create_verified_user(client, fake)
    user2 = await create_verified_user(client, fake)

    post_low_views = await create_test_post(client, user1["headers"], title="조회수 적은 글")
    post_high_views = await create_test_post(client, user1["headers"], title="조회수 많은 글")

    # user2가 post_high_views를 여러 번 조회하여 조회수 증가
    # (조회수는 게시글 상세 조회 시 증가)
    for _ in range(3):
        await client.get(
            f"/v1/posts/{post_high_views['post_id']}",
            headers=user2["headers"],
        )

    res = await client.get("/v1/posts/", params={"sort": "views"})
    assert res.status_code == 200

    posts = res.json()["data"]["posts"]
    post_ids = [p["post_id"] for p in posts]

    idx_high = post_ids.index(post_high_views["post_id"])
    idx_low = post_ids.index(post_low_views["post_id"])
    assert idx_high < idx_low


@pytest.mark.asyncio
async def test_sort_by_comments(client, fake):
    """comments 정렬: 댓글이 많은 게시글이 먼저 반환된다."""
    user = await create_verified_user(client, fake)

    post_no_comment = await create_test_post(client, user["headers"], title="댓글 없는 글")
    post_with_comments = await create_test_post(client, user["headers"], title="댓글 있는 글")

    # 댓글 3개 추가
    for i in range(3):
        await create_test_comment(
            client,
            user["headers"],
            post_with_comments["post_id"],
            content=f"댓글 {i}",
        )

    res = await client.get("/v1/posts/", params={"sort": "comments"})
    assert res.status_code == 200

    posts = res.json()["data"]["posts"]
    post_ids = [p["post_id"] for p in posts]

    idx_with = post_ids.index(post_with_comments["post_id"])
    idx_no = post_ids.index(post_no_comment["post_id"])
    assert idx_with < idx_no


@pytest.mark.asyncio
async def test_sort_by_hot(client, fake):
    """hot 정렬: 200 응답과 게시글 목록을 반환한다."""
    user = await create_verified_user(client, fake)

    await create_test_post(client, user["headers"], title="인기글 테스트")

    res = await client.get("/v1/posts/", params={"sort": "hot"})
    assert res.status_code == 200

    data = res.json()["data"]
    assert "posts" in data
    assert len(data["posts"]) > 0


@pytest.mark.asyncio
async def test_invalid_sort_falls_back_to_latest(client, fake):
    """유효하지 않은 정렬 옵션은 latest로 폴백한다."""
    user = await create_verified_user(client, fake)

    await create_test_post(client, user["headers"], title="오래된 글")
    await create_test_post(client, user["headers"], title="최신 글")

    # 유효하지 않은 정렬 옵션
    res_invalid = await client.get("/v1/posts/", params={"sort": "invalid_sort_option"})
    assert res_invalid.status_code == 200

    # latest 정렬
    res_latest = await client.get("/v1/posts/", params={"sort": "latest"})
    assert res_latest.status_code == 200

    # 동일한 순서
    invalid_ids = [p["post_id"] for p in res_invalid.json()["data"]["posts"]]
    latest_ids = [p["post_id"] for p in res_latest.json()["data"]["posts"]]
    assert invalid_ids == latest_ids
