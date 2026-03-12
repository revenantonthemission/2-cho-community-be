"""Comments 도메인 — CRUD 테스트."""

import pytest
from httpx import AsyncClient

from tests.conftest import create_verified_user, create_test_post, create_test_comment


# ---------------------------------------------------------------------------
# 댓글 생성
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_comment_returns_201(client: AsyncClient, fake):
    """댓글 생성 시 201을 반환한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    post = await create_test_post(client, user["headers"])
    post_id = post["post_id"]

    # Act
    res = await client.post(
        f"/v1/posts/{post_id}/comments",
        json={"content": "테스트 댓글입니다."},
        headers=user["headers"],
    )

    # Assert
    assert res.status_code == 201
    data = res.json()["data"]
    assert data["comment_id"] > 0
    assert data["content"] == "테스트 댓글입니다."


@pytest.mark.asyncio
async def test_create_comment_without_auth_returns_401(client: AsyncClient, fake):
    """인증 없이 댓글 생성 시 401을 반환한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    post = await create_test_post(client, user["headers"])
    post_id = post["post_id"]

    # Act
    res = await client.post(
        f"/v1/posts/{post_id}/comments",
        json={"content": "무인증 댓글"},
    )

    # Assert
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_create_comment_on_deleted_post_returns_404(client: AsyncClient, fake):
    """삭제된 게시글에 댓글 작성 시 404를 반환한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    post = await create_test_post(client, user["headers"])
    post_id = post["post_id"]

    # 게시글 삭제
    del_res = await client.delete(f"/v1/posts/{post_id}", headers=user["headers"])
    assert del_res.status_code == 200

    # Act
    res = await client.post(
        f"/v1/posts/{post_id}/comments",
        json={"content": "삭제된 게시글에 댓글"},
        headers=user["headers"],
    )

    # Assert
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# 댓글 수정
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_comment_succeeds(client: AsyncClient, fake):
    """작성자가 댓글을 수정하면 200을 반환한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    post = await create_test_post(client, user["headers"])
    post_id = post["post_id"]
    comment = await create_test_comment(client, user["headers"], post_id)
    comment_id = comment["comment_id"]

    # Act
    res = await client.put(
        f"/v1/posts/{post_id}/comments/{comment_id}",
        json={"content": "수정된 댓글입니다."},
        headers=user["headers"],
    )

    # Assert
    assert res.status_code == 200
    assert res.json()["data"]["content"] == "수정된 댓글입니다."


@pytest.mark.asyncio
async def test_update_other_user_comment_returns_403(client: AsyncClient, fake):
    """다른 사용자의 댓글을 수정하려 하면 403을 반환한다."""
    # Arrange
    user1 = await create_verified_user(client, fake)
    user2 = await create_verified_user(client, fake)
    post = await create_test_post(client, user1["headers"])
    post_id = post["post_id"]
    comment = await create_test_comment(client, user1["headers"], post_id)
    comment_id = comment["comment_id"]

    # Act
    res = await client.put(
        f"/v1/posts/{post_id}/comments/{comment_id}",
        json={"content": "탈취 수정 시도"},
        headers=user2["headers"],
    )

    # Assert
    assert res.status_code == 403


# ---------------------------------------------------------------------------
# 댓글 삭제
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_comment_soft_deletes(client: AsyncClient, fake):
    """댓글 삭제 후 게시글 상세에서 해당 댓글이 보이지 않는다 (soft delete)."""
    # Arrange
    user = await create_verified_user(client, fake)
    post = await create_test_post(client, user["headers"])
    post_id = post["post_id"]
    comment = await create_test_comment(client, user["headers"], post_id)
    comment_id = comment["comment_id"]

    # Act
    del_res = await client.delete(
        f"/v1/posts/{post_id}/comments/{comment_id}",
        headers=user["headers"],
    )

    # Assert
    assert del_res.status_code == 200

    # 게시글 상세에서 댓글이 보이지 않아야 함
    detail = await client.get(f"/v1/posts/{post_id}", headers=user["headers"])
    comments = detail.json()["data"]["comments"]
    comment_ids = [c["comment_id"] for c in comments]
    assert comment_id not in comment_ids


@pytest.mark.asyncio
async def test_delete_other_user_comment_returns_403(client: AsyncClient, fake):
    """다른 사용자의 댓글을 삭제하려 하면 403을 반환한다."""
    # Arrange
    user1 = await create_verified_user(client, fake)
    user2 = await create_verified_user(client, fake)
    post = await create_test_post(client, user1["headers"])
    post_id = post["post_id"]
    comment = await create_test_comment(client, user1["headers"], post_id)
    comment_id = comment["comment_id"]

    # Act
    res = await client.delete(
        f"/v1/posts/{post_id}/comments/{comment_id}",
        headers=user2["headers"],
    )

    # Assert
    assert res.status_code == 403
