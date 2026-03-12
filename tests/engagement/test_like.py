"""Engagement 도메인 -- 게시글 좋아요 테스트."""

import pytest
from httpx import AsyncClient

from tests.conftest import create_verified_user


# ---------------------------------------------------------------------------
# 좋아요 추가 / 취소
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_like_post_returns_201(client: AsyncClient, fake, post_for_engagement):
    """게시글 좋아요 시 201을 반환한다."""
    # Arrange
    other = post_for_engagement["other"]
    post_id = post_for_engagement["post"]["post_id"]

    # Act
    res = await client.post(
        f"/v1/posts/{post_id}/likes",
        headers=other["headers"],
    )

    # Assert
    assert res.status_code == 201
    assert res.json()["code"] == "LIKE_ADDED"


@pytest.mark.asyncio
async def test_unlike_post_returns_200(client: AsyncClient, fake, post_for_engagement):
    """게시글 좋아요 취소 시 200을 반환한다."""
    # Arrange
    other = post_for_engagement["other"]
    post_id = post_for_engagement["post"]["post_id"]

    # 좋아요 먼저
    like_res = await client.post(
        f"/v1/posts/{post_id}/likes",
        headers=other["headers"],
    )
    assert like_res.status_code == 201

    # Act
    res = await client.delete(
        f"/v1/posts/{post_id}/likes",
        headers=other["headers"],
    )

    # Assert
    assert res.status_code == 200
    assert res.json()["code"] == "LIKE_REMOVED"


@pytest.mark.asyncio
async def test_duplicate_like_returns_409(client: AsyncClient, fake, post_for_engagement):
    """동일 게시글에 중복 좋아요 시 409를 반환한다."""
    # Arrange
    other = post_for_engagement["other"]
    post_id = post_for_engagement["post"]["post_id"]

    # 첫 번째 좋아요
    first = await client.post(
        f"/v1/posts/{post_id}/likes",
        headers=other["headers"],
    )
    assert first.status_code == 201

    # Act -- 중복 좋아요
    res = await client.post(
        f"/v1/posts/{post_id}/likes",
        headers=other["headers"],
    )

    # Assert
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_like_nonexistent_post_returns_404(client: AsyncClient, fake):
    """존재하지 않는 게시글에 좋아요 시 404를 반환한다."""
    # Arrange
    user = await create_verified_user(client, fake)

    # Act
    res = await client.post(
        "/v1/posts/99999/likes",
        headers=user["headers"],
    )

    # Assert
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_like_count_in_post_detail(client: AsyncClient, fake, post_for_engagement):
    """좋아요 후 게시글 상세에서 like_count가 반영된다."""
    # Arrange
    other = post_for_engagement["other"]
    post_id = post_for_engagement["post"]["post_id"]

    # 좋아요
    like_res = await client.post(
        f"/v1/posts/{post_id}/likes",
        headers=other["headers"],
    )
    assert like_res.status_code == 201

    # Act -- 게시글 상세 조회
    detail = await client.get(
        f"/v1/posts/{post_id}",
        headers=other["headers"],
    )

    # Assert
    assert detail.status_code == 200
    post_data = detail.json()["data"]["post"]
    assert post_data["likes_count"] >= 1
    assert post_data["is_liked"] is True


@pytest.mark.asyncio
async def test_like_without_auth_returns_401(client: AsyncClient, fake, post_for_engagement):
    """미인증 사용자의 좋아요 시 401을 반환한다."""
    # Arrange
    post_id = post_for_engagement["post"]["post_id"]

    # Act -- 인증 헤더 없이 요청
    res = await client.post(f"/v1/posts/{post_id}/likes")

    # Assert
    assert res.status_code == 401
