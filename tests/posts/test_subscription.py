"""Posts 도메인 -- 게시글 구독 테스트."""

import pytest
from httpx import AsyncClient

from tests.conftest import create_test_post, create_verified_user


@pytest.mark.asyncio
async def test_subscribe_to_post(client: AsyncClient, fake, db):
    """PUT watching 후 GET으로 watching 상태를 확인한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    post = await create_test_post(client, user["headers"])
    post_id = post["post_id"]

    # Act — watching으로 구독
    put_res = await client.put(
        f"/v1/posts/{post_id}/subscription",
        json={"level": "watching"},
        headers=user["headers"],
    )
    assert put_res.status_code == 200
    assert put_res.json()["level"] == "watching"

    # Assert — GET으로 확인
    get_res = await client.get(
        f"/v1/posts/{post_id}/subscription",
        headers=user["headers"],
    )
    assert get_res.status_code == 200
    assert get_res.json()["level"] == "watching"


@pytest.mark.asyncio
async def test_unsubscribe_from_post(client: AsyncClient, fake, db):
    """PUT watching → DELETE → GET으로 normal 상태를 확인한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    post = await create_test_post(client, user["headers"])
    post_id = post["post_id"]

    # watching으로 구독
    put_res = await client.put(
        f"/v1/posts/{post_id}/subscription",
        json={"level": "watching"},
        headers=user["headers"],
    )
    assert put_res.status_code == 200

    # Act — 구독 해제
    del_res = await client.delete(
        f"/v1/posts/{post_id}/subscription",
        headers=user["headers"],
    )
    assert del_res.status_code == 200
    assert del_res.json()["level"] == "normal"

    # Assert — GET으로 normal 확인
    get_res = await client.get(
        f"/v1/posts/{post_id}/subscription",
        headers=user["headers"],
    )
    assert get_res.status_code == 200
    assert get_res.json()["level"] == "normal"


@pytest.mark.asyncio
async def test_mute_post(client: AsyncClient, fake, db):
    """PUT muted 후 GET으로 muted 상태를 확인한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    post = await create_test_post(client, user["headers"])
    post_id = post["post_id"]

    # Act — muted로 구독
    put_res = await client.put(
        f"/v1/posts/{post_id}/subscription",
        json={"level": "muted"},
        headers=user["headers"],
    )
    assert put_res.status_code == 200
    assert put_res.json()["level"] == "muted"

    # Assert — GET으로 확인
    get_res = await client.get(
        f"/v1/posts/{post_id}/subscription",
        headers=user["headers"],
    )
    assert get_res.status_code == 200
    assert get_res.json()["level"] == "muted"


@pytest.mark.asyncio
async def test_default_subscription_is_normal(client: AsyncClient, fake, db):
    """게시글에 참여하지 않은 사용자의 구독 상태는 normal이다."""
    # Arrange
    author = await create_verified_user(client, fake)
    reader = await create_verified_user(client, fake)
    post = await create_test_post(client, author["headers"])
    post_id = post["post_id"]

    # Act — 게시글에 참여하지 않은 사용자가 조회
    get_res = await client.get(
        f"/v1/posts/{post_id}/subscription",
        headers=reader["headers"],
    )

    # Assert
    assert get_res.status_code == 200
    assert get_res.json()["level"] == "normal"


@pytest.mark.asyncio
async def test_subscription_requires_auth(client: AsyncClient, fake, db):
    """미인증 사용자의 구독 조회 시 401을 반환한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    post = await create_test_post(client, user["headers"])
    post_id = post["post_id"]

    # Act — 인증 헤더 없이 요청
    get_res = await client.get(f"/v1/posts/{post_id}/subscription")

    # Assert
    assert get_res.status_code == 401


# ---------------------------------------------------------------------------
# 자동 구독 + reply 알림 팬아웃 테스트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auto_subscribe_on_post_creation(client: AsyncClient, fake, db):
    """게시글 작성 시 작성자가 자동으로 watching 구독된다."""
    user = await create_verified_user(client, fake)
    post = await create_test_post(client, user["headers"])

    res = await client.get(
        f"/v1/posts/{post['post_id']}/subscription",
        headers=user["headers"],
    )
    assert res.status_code == 200
    assert res.json()["level"] == "watching"


@pytest.mark.asyncio
async def test_auto_subscribe_on_comment(client: AsyncClient, fake, db):
    """댓글 작성 시 댓글 작성자가 자동으로 watching 구독된다."""
    author = await create_verified_user(client, fake)
    commenter = await create_verified_user(client, fake)
    post = await create_test_post(client, author["headers"])

    comment_res = await client.post(
        f"/v1/posts/{post['post_id']}/comments",
        json={"content": "좋은 글!"},
        headers=commenter["headers"],
    )
    assert comment_res.status_code == 201

    res = await client.get(
        f"/v1/posts/{post['post_id']}/subscription",
        headers=commenter["headers"],
    )
    assert res.status_code == 200
    assert res.json()["level"] == "watching"


@pytest.mark.asyncio
async def test_reply_notification_to_subscribers(client: AsyncClient, fake, db):
    """watching 구독자에게 reply 알림이 발송된다."""
    author = await create_verified_user(client, fake)
    subscriber = await create_verified_user(client, fake)
    commenter = await create_verified_user(client, fake)
    post = await create_test_post(client, author["headers"])

    # subscriber가 watching 구독
    put_res = await client.put(
        f"/v1/posts/{post['post_id']}/subscription",
        json={"level": "watching"},
        headers=subscriber["headers"],
    )
    assert put_res.status_code == 200

    # commenter가 댓글 작성
    comment_res = await client.post(
        f"/v1/posts/{post['post_id']}/comments",
        json={"content": "새 댓글"},
        headers=commenter["headers"],
    )
    assert comment_res.status_code == 201

    # subscriber의 알림 확인
    res = await client.get("/v1/notifications/", headers=subscriber["headers"])
    assert res.status_code == 200
    notifs = res.json()["data"]["notifications"]
    reply_notifs = [n for n in notifs if n["type"] == "reply"]
    assert len(reply_notifs) == 1


@pytest.mark.asyncio
async def test_no_reply_notification_if_muted(client: AsyncClient, fake, db):
    """muted 구독자에게는 reply 알림이 발송되지 않는다."""
    author = await create_verified_user(client, fake)
    muted_user = await create_verified_user(client, fake)
    commenter = await create_verified_user(client, fake)
    post = await create_test_post(client, author["headers"])

    # muted_user가 muted 구독
    put_res = await client.put(
        f"/v1/posts/{post['post_id']}/subscription",
        json={"level": "muted"},
        headers=muted_user["headers"],
    )
    assert put_res.status_code == 200

    # commenter가 댓글 작성
    comment_res = await client.post(
        f"/v1/posts/{post['post_id']}/comments",
        json={"content": "새 댓글"},
        headers=commenter["headers"],
    )
    assert comment_res.status_code == 201

    # muted_user의 알림 확인 — reply 알림 없어야 함
    res = await client.get("/v1/notifications/", headers=muted_user["headers"])
    assert res.status_code == 200
    notifs = res.json()["data"]["notifications"]
    reply_notifs = [n for n in notifs if n["type"] == "reply"]
    assert len(reply_notifs) == 0
