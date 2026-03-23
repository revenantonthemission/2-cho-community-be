"""Notifications 도메인 -- 읽음 상태 테스트.

개별/전체 읽음 처리, 미읽음 수 조회, 권한 검증.
"""

import pytest

from tests.conftest import create_test_comment, create_verified_user

# ==========================================
# 개별 읽음 처리
# ==========================================


@pytest.mark.asyncio
async def test_mark_notification_as_read(client, two_users_with_post):
    """PATCH /v1/notifications/{id}/read로 개별 알림을 읽음 처리한다."""
    # Arrange
    author = two_users_with_post["author"]
    other = two_users_with_post["other"]
    post_id = two_users_with_post["post"]["post_id"]

    await create_test_comment(client, other["headers"], post_id)

    # 알림 ID 조회
    list_res = await client.get("/v1/notifications/", headers=author["headers"])
    notification_id = list_res.json()["data"]["notifications"][0]["notification_id"]

    # Act
    res = await client.patch(
        f"/v1/notifications/{notification_id}/read",
        headers=author["headers"],
    )

    # Assert
    assert res.status_code == 200
    assert res.json()["code"] == "NOTIFICATION_READ"

    # 읽음 처리 후 알림 목록에서 is_read 확인
    list_res2 = await client.get("/v1/notifications/", headers=author["headers"])
    noti = next(n for n in list_res2.json()["data"]["notifications"] if n["notification_id"] == notification_id)
    assert noti["is_read"] is True


# ==========================================
# 전체 읽음 처리
# ==========================================


@pytest.mark.asyncio
async def test_mark_all_notifications_as_read(client, two_users_with_post):
    """PATCH /v1/notifications/read-all로 모든 알림을 읽음 처리한다."""
    # Arrange — 댓글 여러 개로 알림 누적
    author = two_users_with_post["author"]
    other = two_users_with_post["other"]
    post_id = two_users_with_post["post"]["post_id"]

    for i in range(3):
        await create_test_comment(
            client,
            other["headers"],
            post_id,
            content=f"읽음 테스트 댓글 {i}",
        )

    # Act
    res = await client.patch(
        "/v1/notifications/read-all",
        headers=author["headers"],
    )

    # Assert
    assert res.status_code == 200
    assert res.json()["code"] == "ALL_NOTIFICATIONS_READ"

    # 모든 알림이 읽음 상태인지 확인
    list_res = await client.get("/v1/notifications/", headers=author["headers"])
    for noti in list_res.json()["data"]["notifications"]:
        assert noti["is_read"] is True


# ==========================================
# 미읽음 수 조회
# ==========================================


@pytest.mark.asyncio
async def test_unread_count_returns_correct_number(client, two_users_with_post):
    """GET /v1/notifications/unread-count가 정확한 미읽음 수를 반환한다."""
    # Arrange
    author = two_users_with_post["author"]
    other = two_users_with_post["other"]
    post_id = two_users_with_post["post"]["post_id"]

    for i in range(3):
        await create_test_comment(
            client,
            other["headers"],
            post_id,
            content=f"미읽음 카운트 댓글 {i}",
        )

    # Act
    res = await client.get(
        "/v1/notifications/unread-count",
        headers=author["headers"],
    )

    # Assert
    assert res.status_code == 200
    assert res.json()["data"]["unread_count"] == 3


@pytest.mark.asyncio
async def test_unread_count_decreases_after_mark_read(
    client,
    two_users_with_post,
):
    """개별 알림 읽음 처리 후 미읽음 수가 감소한다."""
    # Arrange
    author = two_users_with_post["author"]
    other = two_users_with_post["other"]
    post_id = two_users_with_post["post"]["post_id"]

    # 알림 2개 생성
    for i in range(2):
        await create_test_comment(
            client,
            other["headers"],
            post_id,
            content=f"감소 테스트 댓글 {i}",
        )

    # 미읽음 수 확인
    count_res1 = await client.get(
        "/v1/notifications/unread-count",
        headers=author["headers"],
    )
    assert count_res1.json()["data"]["unread_count"] == 2

    # Act — 알림 1개 읽음 처리
    list_res = await client.get("/v1/notifications/", headers=author["headers"])
    notification_id = list_res.json()["data"]["notifications"][0]["notification_id"]
    await client.patch(
        f"/v1/notifications/{notification_id}/read",
        headers=author["headers"],
    )

    # Assert — 미읽음 수 1로 감소
    count_res2 = await client.get(
        "/v1/notifications/unread-count",
        headers=author["headers"],
    )
    assert count_res2.json()["data"]["unread_count"] == 1


# ==========================================
# 권한 검증
# ==========================================


@pytest.mark.asyncio
async def test_mark_other_user_notification_returns_403_or_404(
    client,
    fake,
    two_users_with_post,
):
    """다른 사용자의 알림을 읽음 처리하면 404를 반환한다.

    mark_as_read는 user_id 조건이 WHERE에 포함되어 있어
    다른 사용자의 알림은 "존재하지 않음"으로 처리된다 (404).
    """
    # Arrange
    author = two_users_with_post["author"]
    other = two_users_with_post["other"]
    post_id = two_users_with_post["post"]["post_id"]

    await create_test_comment(client, other["headers"], post_id)

    # author의 알림 ID 조회
    list_res = await client.get("/v1/notifications/", headers=author["headers"])
    notification_id = list_res.json()["data"]["notifications"][0]["notification_id"]

    # Act — 제3자가 읽음 처리 시도
    intruder = await create_verified_user(client, fake)
    res = await client.patch(
        f"/v1/notifications/{notification_id}/read",
        headers=intruder["headers"],
    )

    # Assert — WHERE user_id 조건 불일치로 404
    assert res.status_code == 404
