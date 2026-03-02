"""이메일 미인증 사용자의 쓰기 기능 차단 테스트."""

import pytest


@pytest.mark.asyncio
async def test_unverified_user_cannot_create_post(unverified_user):
    """미인증 사용자는 게시글을 작성할 수 없습니다."""
    client, _, _ = unverified_user
    res = await client.post("/v1/posts/", json={"title": "테스트 글", "content": "내용", "category_id": 1})
    assert res.status_code == 403
    assert res.json()["detail"]["error"] == "email_not_verified"


@pytest.mark.asyncio
async def test_unverified_user_cannot_comment(unverified_user, authorized_user):
    """미인증 사용자는 댓글을 작성할 수 없습니다."""
    auth_client, _, _ = authorized_user
    # 인증된 사용자가 게시글 생성
    post_res = await auth_client.post(
        "/v1/posts/", json={"title": "테스트 글", "content": "내용", "category_id": 1}
    )
    post_id = post_res.json()["data"]["post_id"]

    unverified_client, _, _ = unverified_user
    res = await unverified_client.post(
        f"/v1/posts/{post_id}/comments", json={"content": "댓글"}
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_unverified_user_cannot_like(unverified_user, authorized_user):
    """미인증 사용자는 좋아요를 할 수 없습니다."""
    auth_client, _, _ = authorized_user
    post_res = await auth_client.post(
        "/v1/posts/", json={"title": "테스트 글", "content": "내용", "category_id": 1}
    )
    post_id = post_res.json()["data"]["post_id"]

    unverified_client, _, _ = unverified_user
    res = await unverified_client.post(f"/v1/posts/{post_id}/likes", json={})
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_unverified_user_can_read_posts(unverified_user, authorized_user):
    """미인증 사용자는 게시글 조회는 가능합니다."""
    auth_client, _, _ = authorized_user
    await auth_client.post("/v1/posts/", json={"title": "테스트", "content": "내용", "category_id": 1})

    unverified_client, _, _ = unverified_user
    res = await unverified_client.get("/v1/posts/")
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_verified_user_can_create_post(authorized_user):
    """인증된 사용자는 게시글을 작성할 수 있습니다."""
    client, _, _ = authorized_user
    res = await client.post("/v1/posts/", json={"title": "테스트 글", "content": "내용", "category_id": 1})
    assert res.status_code == 201
