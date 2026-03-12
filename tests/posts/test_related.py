"""Posts 도메인 — 연관 게시글 추천 테스트."""

import pytest
from httpx import AsyncClient

from tests.conftest import create_verified_user, create_test_post


# ---------------------------------------------------------------------------
# 태그 기반 연관 추천
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_related_posts_by_tag(client: AsyncClient, fake):
    """같은 태그를 가진 게시글이 연관 게시글로 추천된다."""
    user = await create_verified_user(client, fake)

    # 기준 게시글 (태그: python, fastapi)
    base = await create_test_post(
        client, user["headers"], title="기준 게시글입니다", tags=["python", "fastapi"]
    )
    # 같은 태그 게시글
    related = await create_test_post(
        client, user["headers"], title="관련 게시글입니다", tags=["python"]
    )
    # 다른 태그 게시글
    await create_test_post(
        client, user["headers"], title="무관한 게시글입니다", tags=["javascript"]
    )

    res = await client.get(
        f"/v1/posts/{base['post_id']}/related", headers=user["headers"]
    )
    assert res.status_code == 200

    post_ids = [p["post_id"] for p in res.json()["data"]["posts"]]
    assert related["post_id"] in post_ids


# ---------------------------------------------------------------------------
# 카테고리 폴백
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_related_posts_fallback_to_category(client: AsyncClient, fake):
    """태그가 없는 게시글은 같은 카테고리의 게시글이 연관으로 추천된다."""
    user = await create_verified_user(client, fake)

    base = await create_test_post(
        client, user["headers"], title="태그없는 기준글", category_id=2
    )
    same_cat = await create_test_post(
        client, user["headers"], title="같은카테고리 게시글", category_id=2
    )
    diff_cat = await create_test_post(
        client, user["headers"], title="다른카테고리 게시글", category_id=3
    )

    res = await client.get(
        f"/v1/posts/{base['post_id']}/related", headers=user["headers"]
    )
    assert res.status_code == 200
    post_ids = [p["post_id"] for p in res.json()["data"]["posts"]]

    # 같은 카테고리 게시글이 다른 카테고리보다 상위에 있어야 함
    if same_cat["post_id"] in post_ids and diff_cat["post_id"] in post_ids:
        assert post_ids.index(same_cat["post_id"]) < post_ids.index(
            diff_cat["post_id"]
        )


# ---------------------------------------------------------------------------
# 차단 사용자 제외
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_related_posts_excludes_blocked_users(client: AsyncClient, fake):
    """차단한 사용자의 게시글은 연관 목록에서 제외된다."""
    user1 = await create_verified_user(client, fake)
    user2 = await create_verified_user(client, fake)

    # user1 기준 게시글
    base = await create_test_post(
        client, user1["headers"], title="기준 게시글입니다", tags=["block-test"]
    )
    # user2가 같은 태그로 게시글 작성
    blocked_post = await create_test_post(
        client, user2["headers"], title="차단될 게시글입니다", tags=["block-test"]
    )

    # user1이 user2를 차단
    block_res = await client.post(
        f"/v1/users/{user2['user_id']}/block", headers=user1["headers"]
    )
    assert block_res.status_code == 201

    # 연관 게시글 조회
    res = await client.get(
        f"/v1/posts/{base['post_id']}/related", headers=user1["headers"]
    )
    assert res.status_code == 200

    post_ids = [p["post_id"] for p in res.json()["data"]["posts"]]
    assert blocked_post["post_id"] not in post_ids


# ---------------------------------------------------------------------------
# limit 파라미터
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_related_posts_limit(client: AsyncClient, fake):
    """limit 파라미터로 반환 개수를 제한할 수 있다."""
    user = await create_verified_user(client, fake)

    base = await create_test_post(
        client, user["headers"], title="기준 게시글입니다", tags=["limit-test"]
    )
    for i in range(5):
        await create_test_post(
            client,
            user["headers"],
            title=f"관련 게시글 {i} 입니다",
            tags=["limit-test"],
        )

    res = await client.get(
        f"/v1/posts/{base['post_id']}/related?limit=2", headers=user["headers"]
    )
    assert res.status_code == 200
    assert len(res.json()["data"]["posts"]) <= 2


# ---------------------------------------------------------------------------
# 자기 자신 제외
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_related_posts_excludes_self(client: AsyncClient, fake):
    """연관 게시글 목록에 기준 게시글 자신은 포함되지 않는다."""
    user = await create_verified_user(client, fake)

    base = await create_test_post(
        client, user["headers"], title="자기자신 제외 테스트", tags=["self-test"]
    )
    await create_test_post(
        client, user["headers"], title="관련 게시글입니다", tags=["self-test"]
    )

    res = await client.get(
        f"/v1/posts/{base['post_id']}/related", headers=user["headers"]
    )
    assert res.status_code == 200

    post_ids = [p["post_id"] for p in res.json()["data"]["posts"]]
    assert base["post_id"] not in post_ids
