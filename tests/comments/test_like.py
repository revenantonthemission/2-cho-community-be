"""Comments 도메인 — 댓글 좋아요 테스트."""

import pytest
from httpx import AsyncClient

from tests.conftest import create_test_comment, create_test_post, create_verified_user

# ---------------------------------------------------------------------------
# 댓글 좋아요 / 취소
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_like_comment_returns_201(client: AsyncClient, fake):
    """댓글 좋아요 시 201을 반환한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    post = await create_test_post(client, user["headers"])
    post_id = post["post_id"]
    comment = await create_test_comment(client, user["headers"], post_id)
    comment_id = comment["comment_id"]

    # Act
    res = await client.post(
        f"/v1/posts/{post_id}/comments/{comment_id}/like",
        headers=user["headers"],
    )

    # Assert
    assert res.status_code == 201


@pytest.mark.asyncio
async def test_unlike_comment_returns_200(client: AsyncClient, fake):
    """댓글 좋아요 취소 시 200을 반환한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    post = await create_test_post(client, user["headers"])
    post_id = post["post_id"]
    comment = await create_test_comment(client, user["headers"], post_id)
    comment_id = comment["comment_id"]

    # 좋아요 먼저
    like_res = await client.post(
        f"/v1/posts/{post_id}/comments/{comment_id}/like",
        headers=user["headers"],
    )
    assert like_res.status_code == 201

    # Act
    res = await client.delete(
        f"/v1/posts/{post_id}/comments/{comment_id}/like",
        headers=user["headers"],
    )

    # Assert
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_duplicate_comment_like_returns_409(client: AsyncClient, fake):
    """동일 댓글에 중복 좋아요 시 409를 반환한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    post = await create_test_post(client, user["headers"])
    post_id = post["post_id"]
    comment = await create_test_comment(client, user["headers"], post_id)
    comment_id = comment["comment_id"]

    # 첫 번째 좋아요
    first = await client.post(
        f"/v1/posts/{post_id}/comments/{comment_id}/like",
        headers=user["headers"],
    )
    assert first.status_code == 201

    # Act — 중복 좋아요
    res = await client.post(
        f"/v1/posts/{post_id}/comments/{comment_id}/like",
        headers=user["headers"],
    )

    # Assert
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_like_nonexistent_comment_returns_404(client: AsyncClient, fake):
    """존재하지 않는 댓글에 좋아요 시 404를 반환한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    post = await create_test_post(client, user["headers"])
    post_id = post["post_id"]

    # Act
    res = await client.post(
        f"/v1/posts/{post_id}/comments/99999/like",
        headers=user["headers"],
    )

    # Assert
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_comment_like_status_in_post_detail(client: AsyncClient, fake):
    """좋아요한 댓글의 상태가 게시글 상세에 반영된다."""
    # Arrange
    user = await create_verified_user(client, fake)
    post = await create_test_post(client, user["headers"])
    post_id = post["post_id"]
    comment = await create_test_comment(client, user["headers"], post_id)
    comment_id = comment["comment_id"]

    # 좋아요
    like_res = await client.post(
        f"/v1/posts/{post_id}/comments/{comment_id}/like",
        headers=user["headers"],
    )
    assert like_res.status_code == 201

    # Act — 게시글 상세 조회
    detail = await client.get(f"/v1/posts/{post_id}", headers=user["headers"])

    # Assert
    assert detail.status_code == 200
    comments = detail.json()["data"]["comments"]
    target = next(c for c in comments if c["comment_id"] == comment_id)
    assert target["likes_count"] >= 1
    assert target["is_liked"] is True
