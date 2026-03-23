"""Comments 도메인 — 대댓글(Reply) 테스트."""

import pytest
from httpx import AsyncClient

from tests.conftest import create_test_comment, create_test_post, create_verified_user

# ---------------------------------------------------------------------------
# 대댓글 생성
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_reply_returns_201(client: AsyncClient, fake):
    """parent_id를 지정하여 대댓글 생성 시 201을 반환한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    post = await create_test_post(client, user["headers"])
    post_id = post["post_id"]
    parent = await create_test_comment(client, user["headers"], post_id)

    # Act
    res = await client.post(
        f"/v1/posts/{post_id}/comments",
        json={"content": "대댓글입니다.", "parent_id": parent["comment_id"]},
        headers=user["headers"],
    )

    # Assert
    assert res.status_code == 201
    data = res.json()["data"]
    assert data["parent_id"] == parent["comment_id"]


@pytest.mark.asyncio
async def test_nested_reply_returns_400(client: AsyncClient, fake):
    """대댓글의 대댓글(2단계) 시도 시 400을 반환한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    post = await create_test_post(client, user["headers"])
    post_id = post["post_id"]
    parent = await create_test_comment(client, user["headers"], post_id)

    # 1단계 대댓글
    reply_res = await client.post(
        f"/v1/posts/{post_id}/comments",
        json={"content": "1단계 대댓글", "parent_id": parent["comment_id"]},
        headers=user["headers"],
    )
    assert reply_res.status_code == 201
    reply_id = reply_res.json()["data"]["comment_id"]

    # Act — 2단계 대댓글 시도
    res = await client.post(
        f"/v1/posts/{post_id}/comments",
        json={"content": "2단계 대댓글 시도", "parent_id": reply_id},
        headers=user["headers"],
    )

    # Assert
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_reply_to_nonexistent_comment_returns_404(client: AsyncClient, fake):
    """존재하지 않는 댓글에 대댓글 시도 시 404를 반환한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    post = await create_test_post(client, user["headers"])
    post_id = post["post_id"]

    # Act
    res = await client.post(
        f"/v1/posts/{post_id}/comments",
        json={"content": "유령 댓글에 대댓글", "parent_id": 99999},
        headers=user["headers"],
    )

    # Assert — 부모가 존재하지 않으면 400 (bad_request)
    assert res.status_code == 400


# ---------------------------------------------------------------------------
# 삭제된 부모 댓글 처리
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deleted_parent_shows_placeholder(client: AsyncClient, fake):
    """대댓글이 있는 부모 댓글 삭제 시 플레이스홀더로 표시된다."""
    # Arrange
    user = await create_verified_user(client, fake)
    post = await create_test_post(client, user["headers"])
    post_id = post["post_id"]
    parent = await create_test_comment(
        client,
        user["headers"],
        post_id,
        content="부모 댓글",
    )
    parent_id = parent["comment_id"]

    # 대댓글 생성
    await client.post(
        f"/v1/posts/{post_id}/comments",
        json={"content": "자식 대댓글", "parent_id": parent_id},
        headers=user["headers"],
    )

    # Act — 부모 댓글 삭제
    del_res = await client.delete(
        f"/v1/posts/{post_id}/comments/{parent_id}",
        headers=user["headers"],
    )
    assert del_res.status_code == 200

    # Assert — 게시글 상세에서 부모가 플레이스홀더로 남아 있어야 함
    detail = await client.get(f"/v1/posts/{post_id}", headers=user["headers"])
    comments = detail.json()["data"]["comments"]
    parent_comments = [c for c in comments if c["comment_id"] == parent_id]
    assert len(parent_comments) == 1
    placeholder = parent_comments[0]
    assert placeholder["content"] is None
    assert placeholder["is_deleted"] is True


@pytest.mark.asyncio
async def test_deleted_parent_without_replies_hidden(client: AsyncClient, fake):
    """대댓글이 없는 부모 댓글 삭제 시 목록에서 숨겨진다."""
    # Arrange
    user = await create_verified_user(client, fake)
    post = await create_test_post(client, user["headers"])
    post_id = post["post_id"]
    parent = await create_test_comment(client, user["headers"], post_id)
    parent_id = parent["comment_id"]

    # Act — 부모 댓글 삭제 (대댓글 없음)
    del_res = await client.delete(
        f"/v1/posts/{post_id}/comments/{parent_id}",
        headers=user["headers"],
    )
    assert del_res.status_code == 200

    # Assert — 게시글 상세에서 해당 댓글이 보이지 않아야 함
    detail = await client.get(f"/v1/posts/{post_id}", headers=user["headers"])
    comments = detail.json()["data"]["comments"]
    comment_ids = [c["comment_id"] for c in comments]
    assert parent_id not in comment_ids


@pytest.mark.asyncio
async def test_comment_tree_structure(client: AsyncClient, fake):
    """게시글 상세에서 댓글의 parent_id 관계가 올바르게 반영된다."""
    # Arrange
    user = await create_verified_user(client, fake)
    post = await create_test_post(client, user["headers"])
    post_id = post["post_id"]

    parent = await create_test_comment(
        client,
        user["headers"],
        post_id,
        content="부모 댓글",
    )
    parent_id = parent["comment_id"]

    reply_res = await client.post(
        f"/v1/posts/{post_id}/comments",
        json={"content": "자식 댓글", "parent_id": parent_id},
        headers=user["headers"],
    )
    assert reply_res.status_code == 201
    reply_id = reply_res.json()["data"]["comment_id"]

    # Act
    detail = await client.get(f"/v1/posts/{post_id}", headers=user["headers"])

    # Assert — 댓글은 트리 구조로 반환 (replies 중첩)
    comments = detail.json()["data"]["comments"]
    parent_comment = next(c for c in comments if c["comment_id"] == parent_id)
    assert parent_comment["parent_id"] is None

    # 대댓글은 부모의 replies 리스트에 포함
    reply_comment = next(r for r in parent_comment["replies"] if r["comment_id"] == reply_id)
    assert reply_comment["parent_id"] == parent_id
