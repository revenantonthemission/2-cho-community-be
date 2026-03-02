"""test_comment_like: 댓글 좋아요 기능 테스트."""

import pytest
from httpx import AsyncClient


async def _create_post_and_comment(cli: AsyncClient) -> tuple[int, int]:
    """테스트 헬퍼: 게시글 + 댓글 생성 후 (post_id, comment_id) 반환."""
    post_res = await cli.post(
        "/v1/posts/",
        json={"title": "댓글 좋아요 테스트", "content": "내용입니다", "category_id": 1},
    )
    post_id = post_res.json()["data"]["post_id"]

    comment_res = await cli.post(
        f"/v1/posts/{post_id}/comments",
        json={"content": "댓글입니다"},
    )
    comment_id = comment_res.json()["data"]["comment_id"]

    return post_id, comment_id


@pytest.mark.asyncio
async def test_comment_like_add(client: AsyncClient, authorized_user):
    """댓글 좋아요 추가 (201)."""
    cli, _, _ = authorized_user
    post_id, comment_id = await _create_post_and_comment(cli)

    res = await cli.post(f"/v1/posts/{post_id}/comments/{comment_id}/like")
    assert res.status_code == 201
    assert res.json()["code"] == "COMMENT_LIKE_ADDED"
    assert res.json()["data"]["likes_count"] == 1


@pytest.mark.asyncio
async def test_comment_like_duplicate(client: AsyncClient, authorized_user):
    """중복 댓글 좋아요 (409)."""
    cli, _, _ = authorized_user
    post_id, comment_id = await _create_post_and_comment(cli)

    await cli.post(f"/v1/posts/{post_id}/comments/{comment_id}/like")
    res = await cli.post(f"/v1/posts/{post_id}/comments/{comment_id}/like")
    assert res.status_code == 409
    assert res.json()["detail"]["error"] == "already_liked_comment"


@pytest.mark.asyncio
async def test_comment_like_remove(client: AsyncClient, authorized_user):
    """댓글 좋아요 취소 (200)."""
    cli, _, _ = authorized_user
    post_id, comment_id = await _create_post_and_comment(cli)

    await cli.post(f"/v1/posts/{post_id}/comments/{comment_id}/like")
    res = await cli.delete(f"/v1/posts/{post_id}/comments/{comment_id}/like")
    assert res.status_code == 200
    assert res.json()["code"] == "COMMENT_LIKE_REMOVED"
    assert res.json()["data"]["likes_count"] == 0


@pytest.mark.asyncio
async def test_comment_like_not_liked(client: AsyncClient, authorized_user):
    """좋아요하지 않은 댓글 취소 (404)."""
    cli, _, _ = authorized_user
    post_id, comment_id = await _create_post_and_comment(cli)

    res = await cli.delete(f"/v1/posts/{post_id}/comments/{comment_id}/like")
    assert res.status_code == 404
    assert res.json()["detail"]["error"] == "comment_like_not_found"


@pytest.mark.asyncio
async def test_comment_like_nonexistent_post(client: AsyncClient, authorized_user):
    """존재하지 않는 게시글의 댓글 좋아요 (404)."""
    cli, _, _ = authorized_user

    res = await cli.post("/v1/posts/99999/comments/1/like")
    assert res.status_code == 404
    assert res.json()["detail"]["error"] == "post_not_found"


@pytest.mark.asyncio
async def test_comment_like_nonexistent_comment(client: AsyncClient, authorized_user):
    """존재하지 않는 댓글 좋아요 (404)."""
    cli, _, _ = authorized_user

    post_res = await cli.post(
        "/v1/posts/",
        json={"title": "댓글 없음 테스트", "content": "내용입니다", "category_id": 1},
    )
    post_id = post_res.json()["data"]["post_id"]

    res = await cli.post(f"/v1/posts/{post_id}/comments/99999/like")
    assert res.status_code == 404
    assert res.json()["detail"]["error"] == "comment_not_found"


@pytest.mark.asyncio
async def test_comment_like_wrong_post(client: AsyncClient, authorized_user):
    """다른 게시글에 속한 댓글 좋아요 시도 (404)."""
    cli, _, _ = authorized_user

    # 게시글 2개 생성
    post1_res = await cli.post(
        "/v1/posts/",
        json={"title": "게시글1", "content": "내용입니다", "category_id": 1},
    )
    post1_id = post1_res.json()["data"]["post_id"]

    post2_res = await cli.post(
        "/v1/posts/",
        json={"title": "게시글2", "content": "내용입니다", "category_id": 1},
    )
    post2_id = post2_res.json()["data"]["post_id"]

    # 게시글1에 댓글 작성
    comment_res = await cli.post(
        f"/v1/posts/{post1_id}/comments",
        json={"content": "게시글1의 댓글"},
    )
    comment_id = comment_res.json()["data"]["comment_id"]

    # 게시글2에서 해당 댓글 좋아요 시도
    res = await cli.post(f"/v1/posts/{post2_id}/comments/{comment_id}/like")
    assert res.status_code == 404
    assert res.json()["detail"]["error"] == "comment_not_found"


@pytest.mark.asyncio
async def test_comment_like_unauthorized(client: AsyncClient):
    """미인증 사용자 댓글 좋아요 (401)."""
    res = await client.post("/v1/posts/1/comments/1/like")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_comment_like_in_post_detail(client: AsyncClient, authorized_user):
    """게시글 상세 댓글 트리에서 likes_count + is_liked 확인."""
    cli, _, _ = authorized_user
    post_id, comment_id = await _create_post_and_comment(cli)

    # 좋아요 전
    detail = await cli.get(f"/v1/posts/{post_id}")
    comments = detail.json()["data"]["comments"]
    assert len(comments) == 1
    assert comments[0]["likes_count"] == 0
    assert comments[0]["is_liked"] is False

    # 좋아요 후
    await cli.post(f"/v1/posts/{post_id}/comments/{comment_id}/like")
    detail2 = await cli.get(f"/v1/posts/{post_id}")
    comments2 = detail2.json()["data"]["comments"]
    assert comments2[0]["likes_count"] == 1
    assert comments2[0]["is_liked"] is True
