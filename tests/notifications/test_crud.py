"""Notifications 도메인 -- CRUD 테스트.

알림 생성(댓글/좋아요/팔로우 부작용), 목록 조회, 삭제, 인증 검증.
"""

import pytest

from tests.conftest import (
    create_verified_user,
    create_test_post,
    create_test_comment,
)


# ==========================================
# 알림 생성 (부작용)
# ==========================================


@pytest.mark.asyncio
async def test_comment_creates_notification_for_post_author(
    client, two_users_with_post,
):
    """다른 사용자가 게시글에 댓글을 작성하면 작성자에게 알림이 생성된다."""
    # Arrange
    author = two_users_with_post["author"]
    other = two_users_with_post["other"]
    post_id = two_users_with_post["post"]["post_id"]

    # Act — 다른 사용자가 댓글 작성
    await create_test_comment(client, other["headers"], post_id)

    # Assert — 게시글 작성자의 알림 확인
    res = await client.get("/v1/notifications/", headers=author["headers"])
    assert res.status_code == 200

    data = res.json()["data"]
    assert data["pagination"]["total_count"] >= 1
    comment_notis = [n for n in data["notifications"] if n["type"] == "comment"]
    assert len(comment_notis) >= 1
    assert comment_notis[0]["post_id"] == post_id


@pytest.mark.asyncio
async def test_like_creates_notification_for_post_author(
    client, two_users_with_post,
):
    """다른 사용자가 게시글에 좋아요를 누르면 작성자에게 알림이 생성된다."""
    # Arrange
    author = two_users_with_post["author"]
    other = two_users_with_post["other"]
    post_id = two_users_with_post["post"]["post_id"]

    # Act — 다른 사용자가 좋아요
    like_res = await client.post(
        f"/v1/posts/{post_id}/likes", headers=other["headers"],
    )
    assert like_res.status_code == 201

    # Assert — 게시글 작성자의 알림 확인
    res = await client.get("/v1/notifications/", headers=author["headers"])
    assert res.status_code == 200

    data = res.json()["data"]
    like_notis = [n for n in data["notifications"] if n["type"] == "like"]
    assert len(like_notis) >= 1
    assert like_notis[0]["post_id"] == post_id


@pytest.mark.asyncio
async def test_follow_creates_notification(client, fake):
    """사용자를 팔로우하면 대상에게 알림이 생성된다."""
    # Arrange
    target = await create_verified_user(client, fake)
    follower = await create_verified_user(client, fake)

    # Act — 팔로우
    follow_res = await client.post(
        f"/v1/users/{target['user_id']}/follow", headers=follower["headers"],
    )
    assert follow_res.status_code == 201

    # Assert — 대상 사용자의 알림 확인
    res = await client.get("/v1/notifications/", headers=target["headers"])
    assert res.status_code == 200

    data = res.json()["data"]
    follow_notis = [n for n in data["notifications"] if n["type"] == "follow"]
    assert len(follow_notis) >= 1


@pytest.mark.asyncio
async def test_self_action_does_not_create_notification(client, fake):
    """본인 게시글에 본인이 좋아요를 누르면 알림이 생성되지 않는다."""
    # Arrange
    user = await create_verified_user(client, fake)
    post = await create_test_post(client, user["headers"])
    post_id = post["post_id"]

    # Act — 본인이 좋아요
    like_res = await client.post(
        f"/v1/posts/{post_id}/likes", headers=user["headers"],
    )
    assert like_res.status_code == 201

    # Assert — 알림이 없어야 함
    res = await client.get("/v1/notifications/", headers=user["headers"])
    assert res.status_code == 200
    assert res.json()["data"]["pagination"]["total_count"] == 0


# ==========================================
# 목록 조회
# ==========================================


@pytest.mark.asyncio
async def test_list_notifications_with_pagination(client, two_users_with_post):
    """알림 목록의 offset/limit 페이지네이션이 동작한다."""
    # Arrange — 좋아요 + 댓글 여러 개 생성으로 알림 누적
    author = two_users_with_post["author"]
    other = two_users_with_post["other"]
    post_id = two_users_with_post["post"]["post_id"]

    # 댓글 3개 작성 → 알림 3개
    for i in range(3):
        await create_test_comment(
            client, other["headers"], post_id,
            content=f"페이지네이션 테스트 댓글 {i}",
        )

    # Act — limit=2로 첫 페이지 조회
    res1 = await client.get(
        "/v1/notifications/?offset=0&limit=2", headers=author["headers"],
    )
    assert res1.status_code == 200
    data1 = res1.json()["data"]
    assert len(data1["notifications"]) == 2
    assert data1["pagination"]["total_count"] >= 3
    assert data1["pagination"]["has_more"] is True

    # Act — offset=2로 나머지 조회
    res2 = await client.get(
        "/v1/notifications/?offset=2&limit=2", headers=author["headers"],
    )
    assert res2.status_code == 200
    data2 = res2.json()["data"]
    assert len(data2["notifications"]) >= 1


# ==========================================
# 삭제
# ==========================================


@pytest.mark.asyncio
async def test_delete_notification_succeeds(client, two_users_with_post):
    """알림을 삭제하면 목록에서 사라진다."""
    # Arrange — 댓글 작성으로 알림 생성
    author = two_users_with_post["author"]
    other = two_users_with_post["other"]
    post_id = two_users_with_post["post"]["post_id"]

    await create_test_comment(client, other["headers"], post_id)

    # 알림 ID 조회
    list_res = await client.get("/v1/notifications/", headers=author["headers"])
    notifications = list_res.json()["data"]["notifications"]
    assert len(notifications) >= 1
    notification_id = notifications[0]["notification_id"]

    # Act
    del_res = await client.delete(
        f"/v1/notifications/{notification_id}", headers=author["headers"],
    )

    # Assert
    assert del_res.status_code == 200
    assert del_res.json()["code"] == "NOTIFICATION_DELETED"

    # 삭제 후 목록에서 해당 알림이 사라졌는지 확인
    list_res2 = await client.get("/v1/notifications/", headers=author["headers"])
    remaining_ids = [
        n["notification_id"]
        for n in list_res2.json()["data"]["notifications"]
    ]
    assert notification_id not in remaining_ids


# ==========================================
# 인증
# ==========================================


@pytest.mark.asyncio
async def test_list_notifications_without_auth_returns_401(client):
    """인증 없이 알림 목록을 조회하면 401을 반환한다."""
    res = await client.get("/v1/notifications/")
    assert res.status_code == 401
