"""Posts 도메인 — 게시글 고정(pin) 테스트."""

import pytest
from httpx import AsyncClient

from tests.conftest import create_admin_user, create_test_post, create_verified_user

# ---------------------------------------------------------------------------
# 관리자 고정/해제
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_pin_post_succeeds(client: AsyncClient, fake):
    """관리자가 게시글을 고정하면 200을 반환한다."""
    admin = await create_admin_user(client, fake)
    post = await create_test_post(client, admin["headers"])
    post_id = post["post_id"]

    res = await client.patch(f"/v1/posts/{post_id}/pin", headers=admin["headers"])

    assert res.status_code == 200


@pytest.mark.asyncio
async def test_non_admin_pin_post_returns_403(client: AsyncClient, fake):
    """일반 사용자가 게시글 고정을 시도하면 403을 반환한다."""
    user = await create_verified_user(client, fake)
    post = await create_test_post(client, user["headers"])
    post_id = post["post_id"]

    res = await client.patch(f"/v1/posts/{post_id}/pin", headers=user["headers"])

    assert res.status_code == 403


@pytest.mark.asyncio
async def test_unpin_post_succeeds(client: AsyncClient, fake):
    """관리자가 고정된 게시글의 고정을 해제하면 200을 반환한다."""
    admin = await create_admin_user(client, fake)
    post = await create_test_post(client, admin["headers"])
    post_id = post["post_id"]

    # 고정
    pin_res = await client.patch(f"/v1/posts/{post_id}/pin", headers=admin["headers"])
    assert pin_res.status_code == 200

    # 고정 해제
    unpin_res = await client.delete(f"/v1/posts/{post_id}/pin", headers=admin["headers"])
    assert unpin_res.status_code == 200


@pytest.mark.asyncio
async def test_pinned_posts_appear_first_in_list(client: AsyncClient, fake):
    """고정된 게시글이 목록의 첫 번째에 나타난다."""
    admin = await create_admin_user(client, fake)

    # 일반 게시글 생성
    await create_test_post(client, admin["headers"], title="일반 게시글입니다")
    # 고정할 게시글 생성
    pinned_post = await create_test_post(client, admin["headers"], title="고정 게시글입니다")

    # 게시글 고정
    pin_res = await client.patch(f"/v1/posts/{pinned_post['post_id']}/pin", headers=admin["headers"])
    assert pin_res.status_code == 200

    # 목록 조회 시 고정 게시글이 먼저 나와야 함
    res = await client.get("/v1/posts/")
    assert res.status_code == 200
    posts = res.json()["data"]["posts"]
    assert len(posts) >= 2
    assert posts[0]["post_id"] == pinned_post["post_id"]
