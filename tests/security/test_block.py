"""사용자 차단 API 통합 테스트.

차단/해제/목록 조회 및 차단된 사용자의 게시글·댓글 필터링을 검증한다.
"""

import pytest

from tests.conftest import (
    create_test_comment,
    create_test_post,
    create_verified_user,
)

# ---------------------------------------------------------------------------
# 차단 / 해제
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_block_user_returns_201(client, fake):
    """사용자 차단 시 201을 반환해야 한다."""
    # Arrange
    user1 = await create_verified_user(client, fake)
    user2 = await create_verified_user(client, fake)

    # Act
    res = await user1["client"].post(f"/v1/users/{user2['user_id']}/block")

    # Assert
    assert res.status_code == 201
    assert res.json()["code"] == "USER_BLOCKED"


@pytest.mark.asyncio
async def test_unblock_user_returns_200(client, fake):
    """차단 해제 시 200을 반환해야 한다."""
    # Arrange
    user1 = await create_verified_user(client, fake)
    user2 = await create_verified_user(client, fake)
    await user1["client"].post(f"/v1/users/{user2['user_id']}/block")

    # Act
    res = await user1["client"].delete(f"/v1/users/{user2['user_id']}/block")

    # Assert
    assert res.status_code == 200
    assert res.json()["code"] == "USER_UNBLOCKED"


@pytest.mark.asyncio
async def test_block_self_returns_400(client, fake):
    """자기 자신을 차단하면 400을 반환해야 한다."""
    # Arrange
    user = await create_verified_user(client, fake)

    # Act
    res = await user["client"].post(f"/v1/users/{user['user_id']}/block")

    # Assert
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_duplicate_block_returns_409(client, fake):
    """이미 차단한 사용자를 다시 차단하면 409를 반환해야 한다."""
    # Arrange
    user1 = await create_verified_user(client, fake)
    user2 = await create_verified_user(client, fake)
    await user1["client"].post(f"/v1/users/{user2['user_id']}/block")

    # Act
    res = await user1["client"].post(f"/v1/users/{user2['user_id']}/block")

    # Assert
    assert res.status_code == 409


# ---------------------------------------------------------------------------
# 차단 목록 조회
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_my_block_list(client, fake):
    """차단 목록 조회 시 차단한 사용자가 포함되어야 한다."""
    # Arrange
    user1 = await create_verified_user(client, fake)
    user2 = await create_verified_user(client, fake)
    await user1["client"].post(f"/v1/users/{user2['user_id']}/block")

    # Act
    res = await user1["client"].get("/v1/users/me/blocks")

    # Assert
    assert res.status_code == 200
    data = res.json()["data"]
    blocked_ids = [b["user_id"] for b in data["blocks"]]
    assert user2["user_id"] in blocked_ids


# ---------------------------------------------------------------------------
# 차단된 사용자 콘텐츠 필터링
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_blocked_user_posts_excluded_from_list(client, fake):
    """차단한 사용자의 게시글이 목록에서 제외되어야 한다."""
    # Arrange
    user1 = await create_verified_user(client, fake)
    user2 = await create_verified_user(client, fake)

    # user2가 게시글 작성
    await create_test_post(user2["client"], user2["headers"], title="차단 테스트 게시글")

    # user1이 user2 차단
    await user1["client"].post(f"/v1/users/{user2['user_id']}/block")

    # Act — user1이 게시글 목록 조회
    res = await user1["client"].get("/v1/posts/")

    # Assert — user2의 게시글이 목록에 없어야 함
    assert res.status_code == 200
    posts = res.json()["data"]["posts"]
    post_author_ids = [p["author"]["user_id"] for p in posts]
    assert user2["user_id"] not in post_author_ids


@pytest.mark.asyncio
async def test_blocked_user_comments_filtered(client, fake):
    """차단한 사용자의 댓글이 게시글 상세에서 필터링되어야 한다."""
    # Arrange
    user1 = await create_verified_user(client, fake)
    user2 = await create_verified_user(client, fake)

    # user1이 게시글 작성
    post = await create_test_post(user1["client"], user1["headers"], title="댓글 필터 테스트")

    # user2가 댓글 작성
    await create_test_comment(user2["client"], user2["headers"], post["post_id"], content="차단될 댓글")

    # user1이 user2 차단
    await user1["client"].post(f"/v1/users/{user2['user_id']}/block")

    # Act — user1이 게시글 상세 조회 (댓글 포함)
    res = await user1["client"].get(f"/v1/posts/{post['post_id']}")

    # Assert — user2의 댓글이 필터링됨
    assert res.status_code == 200
    comments = res.json()["data"]["comments"]
    comment_author_ids = [c["author"]["user_id"] for c in comments if c.get("author")]
    assert user2["user_id"] not in comment_author_ids
