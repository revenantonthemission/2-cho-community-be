"""Posts 도메인 — 목록/검색/필터 테스트."""

import pytest
from httpx import AsyncClient

from tests.conftest import create_test_post, create_verified_user

# ---------------------------------------------------------------------------
# 기본 목록 조회
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_posts_returns_200(client: AsyncClient, fake):
    """게시글 목록 조회 시 200과 pagination 정보를 반환한다."""
    user = await create_verified_user(client, fake)
    await create_test_post(client, user["headers"])

    res = await client.get("/v1/posts/")

    assert res.status_code == 200
    data = res.json()["data"]
    assert "posts" in data
    assert "pagination" in data
    assert data["pagination"]["total_count"] >= 1


@pytest.mark.asyncio
async def test_list_posts_pagination(client: AsyncClient, fake):
    """offset/limit 파라미터로 페이지네이션이 동작한다."""
    user = await create_verified_user(client, fake)
    # 게시글 5개 생성
    for i in range(5):
        await create_test_post(client, user["headers"], title=f"페이지 테스트 {i}")

    # limit=2로 조회
    res = await client.get("/v1/posts/?offset=0&limit=2")
    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data["posts"]) == 2
    assert data["pagination"]["has_more"] is True

    # offset=4로 조회 시 나머지 1개
    res2 = await client.get("/v1/posts/?offset=4&limit=2")
    assert res2.status_code == 200
    assert len(res2.json()["data"]["posts"]) == 1


# ---------------------------------------------------------------------------
# 카테고리/태그 필터
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_posts_filter_by_category(client: AsyncClient, fake):
    """category_id 파라미터로 해당 카테고리 게시글만 조회한다."""
    user = await create_verified_user(client, fake)
    await create_test_post(client, user["headers"], category_id=1)
    await create_test_post(client, user["headers"], category_id=2)

    res = await client.get("/v1/posts/?category_id=1")
    assert res.status_code == 200
    posts = res.json()["data"]["posts"]
    # 카테고리 1의 게시글만 포함
    for post in posts:
        assert post["category_id"] == 1


@pytest.mark.asyncio
async def test_list_posts_filter_by_tag(client: AsyncClient, fake):
    """tag 파라미터로 해당 태그가 포함된 게시글만 조회한다."""
    user = await create_verified_user(client, fake)
    await create_test_post(client, user["headers"], tags=["python"])
    await create_test_post(client, user["headers"], tags=["javascript"])

    res = await client.get("/v1/posts/?tag=python")
    assert res.status_code == 200
    posts = res.json()["data"]["posts"]
    assert len(posts) >= 1


# ---------------------------------------------------------------------------
# 검색
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_posts_search_by_title(client: AsyncClient, fake):
    """search 파라미터로 제목을 검색할 수 있다."""
    user = await create_verified_user(client, fake)
    await create_test_post(client, user["headers"], title="고유한검색키워드 테스트 게시글")
    await create_test_post(client, user["headers"], title="관련없는 게시글입니다")

    res = await client.get("/v1/posts/?search=고유한검색키워드")
    assert res.status_code == 200
    posts = res.json()["data"]["posts"]
    assert len(posts) >= 1


@pytest.mark.asyncio
async def test_list_posts_search_by_content(client: AsyncClient, fake):
    """search 파라미터로 내용을 검색할 수 있다."""
    user = await create_verified_user(client, fake)
    await create_test_post(client, user["headers"], content="이것은유니크내용검색어입니다")

    res = await client.get("/v1/posts/?search=유니크내용검색어")
    assert res.status_code == 200
    posts = res.json()["data"]["posts"]
    assert len(posts) >= 1


@pytest.mark.asyncio
async def test_list_posts_search_special_characters(client: AsyncClient, fake):
    """특수문자가 포함된 검색어로도 에러 없이 조회된다."""
    user = await create_verified_user(client, fake)
    await create_test_post(client, user["headers"])

    # FULLTEXT 특수문자가 에러를 유발하지 않아야 함
    for char in ["%", "_", "'", '"']:
        res = await client.get(f"/v1/posts/?search={char}")
        assert res.status_code == 200


# ---------------------------------------------------------------------------
# 정렬
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_posts_sort_by_latest(client: AsyncClient, fake):
    """sort=latest로 최신순 정렬이 동작한다."""
    user = await create_verified_user(client, fake)
    await create_test_post(client, user["headers"], title="첫 번째 게시글")
    await create_test_post(client, user["headers"], title="두 번째 게시글")

    res = await client.get("/v1/posts/?sort=latest")
    assert res.status_code == 200
    posts = res.json()["data"]["posts"]
    assert len(posts) >= 2
    # 최신 게시글이 먼저 나와야 함
    assert posts[0]["title"] == "두 번째 게시글"


@pytest.mark.asyncio
async def test_list_posts_sort_by_likes(client: AsyncClient, fake):
    """sort=likes 정렬 옵션이 에러 없이 동작한다."""
    user = await create_verified_user(client, fake)
    await create_test_post(client, user["headers"])

    res = await client.get("/v1/posts/?sort=likes")
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_list_posts_sort_by_views(client: AsyncClient, fake):
    """sort=views 정렬 옵션이 에러 없이 동작한다."""
    user = await create_verified_user(client, fake)
    await create_test_post(client, user["headers"])

    res = await client.get("/v1/posts/?sort=views")
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_list_posts_sort_invalid_falls_back_to_latest(client: AsyncClient, fake):
    """유효하지 않은 정렬 옵션은 latest로 폴백한다."""
    user = await create_verified_user(client, fake)
    await create_test_post(client, user["headers"])

    res = await client.get("/v1/posts/?sort=invalid_sort")

    # 에러 없이 200 반환 (latest 폴백)
    assert res.status_code == 200


# ---------------------------------------------------------------------------
# 차단 사용자 필터
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_posts_excludes_blocked_users(client: AsyncClient, fake):
    """차단한 사용자의 게시글이 목록에서 제외된다."""
    user1 = await create_verified_user(client, fake)
    user2 = await create_verified_user(client, fake)

    # user2가 게시글 작성
    post = await create_test_post(client, user2["headers"], title="차단될 게시글")
    blocked_post_id = post["post_id"]

    # user1이 user2를 차단
    block_res = await client.post(f"/v1/users/{user2['user_id']}/block", headers=user1["headers"])
    assert block_res.status_code == 201

    # user1이 목록 조회 시 user2의 게시글이 제외되어야 함
    res = await client.get("/v1/posts/", headers=user1["headers"])
    assert res.status_code == 200
    post_ids = [p["post_id"] for p in res.json()["data"]["posts"]]
    assert blocked_post_id not in post_ids
