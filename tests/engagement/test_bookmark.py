"""Engagement 도메인 -- 북마크 테스트."""

import pytest
from httpx import AsyncClient

from tests.conftest import create_verified_user

# ---------------------------------------------------------------------------
# 북마크 추가 / 해제
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bookmark_post_returns_201(client: AsyncClient, fake, post_for_engagement):
    """게시글 북마크 시 201을 반환한다."""
    # Arrange
    other = post_for_engagement["other"]
    post_id = post_for_engagement["post"]["post_id"]

    # Act
    res = await client.post(
        f"/v1/posts/{post_id}/bookmark",
        headers=other["headers"],
    )

    # Assert
    assert res.status_code == 201
    assert res.json()["code"] == "BOOKMARK_ADDED"


@pytest.mark.asyncio
async def test_unbookmark_post_returns_200(client: AsyncClient, fake, post_for_engagement):
    """북마크 해제 시 200을 반환한다."""
    # Arrange
    other = post_for_engagement["other"]
    post_id = post_for_engagement["post"]["post_id"]

    # 북마크 먼저
    bm_res = await client.post(
        f"/v1/posts/{post_id}/bookmark",
        headers=other["headers"],
    )
    assert bm_res.status_code == 201

    # Act
    res = await client.delete(
        f"/v1/posts/{post_id}/bookmark",
        headers=other["headers"],
    )

    # Assert
    assert res.status_code == 200
    assert res.json()["code"] == "BOOKMARK_REMOVED"


@pytest.mark.asyncio
async def test_duplicate_bookmark_returns_409(client: AsyncClient, fake, post_for_engagement):
    """동일 게시글에 중복 북마크 시 409를 반환한다."""
    # Arrange
    other = post_for_engagement["other"]
    post_id = post_for_engagement["post"]["post_id"]

    # 첫 번째 북마크
    first = await client.post(
        f"/v1/posts/{post_id}/bookmark",
        headers=other["headers"],
    )
    assert first.status_code == 201

    # Act -- 중복 북마크
    res = await client.post(
        f"/v1/posts/{post_id}/bookmark",
        headers=other["headers"],
    )

    # Assert
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_my_bookmarks_list(client: AsyncClient, fake, post_for_engagement):
    """북마크한 게시글이 내 북마크 목록에 나타난다."""
    # Arrange
    other = post_for_engagement["other"]
    post_id = post_for_engagement["post"]["post_id"]

    # 북마크
    bm_res = await client.post(
        f"/v1/posts/{post_id}/bookmark",
        headers=other["headers"],
    )
    assert bm_res.status_code == 201

    # Act -- 내 북마크 목록 조회
    res = await client.get(
        "/v1/users/me/bookmarks",
        headers=other["headers"],
    )

    # Assert
    assert res.status_code == 200
    bookmarks = res.json()["data"]["posts"]
    post_ids = [b["post_id"] for b in bookmarks]
    assert post_id in post_ids


@pytest.mark.asyncio
async def test_bookmark_without_auth_returns_401(client: AsyncClient, fake, post_for_engagement):
    """미인증 사용자의 북마크 시 401을 반환한다."""
    # Arrange
    post_id = post_for_engagement["post"]["post_id"]

    # Act -- 인증 헤더 없이 요청
    res = await client.post(f"/v1/posts/{post_id}/bookmark")

    # Assert
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_bookmark_nonexistent_post_returns_404(client: AsyncClient, fake):
    """존재하지 않는 게시글 북마크 시 404를 반환한다."""
    # Arrange
    user = await create_verified_user(client, fake)

    # Act
    res = await client.post(
        "/v1/posts/99999/bookmark",
        headers=user["headers"],
    )

    # Assert
    assert res.status_code == 404
