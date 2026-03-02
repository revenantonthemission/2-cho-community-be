"""test_notifications: 알림 모델 및 API 테스트.

모델 계층 테스트는 DB를 직접 조작하여 알림 CRUD를 검증합니다.
API 계층 테스트는 Task 5에서 엔드포인트 생성 후 활성화됩니다.
"""

import pytest

from database.connection import get_connection, transactional
from models import notification_models


# ==========================================
# 헬퍼 함수
# ==========================================


async def _create_test_user(
    email: str = "noti_user@example.com",
    nickname: str = "notiuser",
    password: str = "hashedpw",
) -> int:
    """테스트용 사용자를 DB에 직접 생성합니다."""
    async with transactional() as cur:
        await cur.execute(
            """
            INSERT INTO user (email, nickname, password)
            VALUES (%s, %s, %s)
            """,
            (email, nickname, password),
        )
        return cur.lastrowid


async def _create_test_post(author_id: int, title: str = "테스트 게시글") -> int:
    """테스트용 게시글을 DB에 직접 생성합니다."""
    async with transactional() as cur:
        await cur.execute(
            """
            INSERT INTO post (title, content, author_id)
            VALUES (%s, %s, %s)
            """,
            (title, "테스트 내용입니다.", author_id),
        )
        return cur.lastrowid


async def _get_notification_count(user_id: int) -> int:
    """특정 사용자의 알림 총 개수를 DB에서 직접 조회합니다."""
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT COUNT(*) FROM notification WHERE user_id = %s",
                (user_id,),
            )
            return (await cur.fetchone())[0]


# ==========================================
# 1. 모델 계층 테스트 (DB 직접 조작)
# ==========================================


@pytest.mark.asyncio
async def test_create_notification(db):
    """알림 생성 시 DB에 저장되는지 확인."""
    owner = await _create_test_user()
    actor = await _create_test_user(email="actor@example.com", nickname="actor")
    post_id = await _create_test_post(owner)

    await notification_models.create_notification(
        user_id=owner,
        notification_type="comment",
        post_id=post_id,
        actor_id=actor,
    )

    count = await _get_notification_count(owner)
    assert count == 1

    # DB에서 직접 확인
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT user_id, type, post_id, actor_id, is_read FROM notification WHERE user_id = %s",
                (owner,),
            )
            row = await cur.fetchone()
            assert row[0] == owner
            assert row[1] == "comment"
            assert row[2] == post_id
            assert row[3] == actor
            assert row[4] == 0  # is_read 기본값


@pytest.mark.asyncio
async def test_self_notification_skipped(db):
    """자기 자신에 대한 알림은 생성되지 않는지 확인."""
    user = await _create_test_user()
    post_id = await _create_test_post(user)

    await notification_models.create_notification(
        user_id=user,
        notification_type="comment",
        post_id=post_id,
        actor_id=user,  # 본인
    )

    count = await _get_notification_count(user)
    assert count == 0


@pytest.mark.asyncio
async def test_create_notification_with_comment_id(db):
    """comment_id가 포함된 알림이 정상 생성되는지 확인."""
    owner = await _create_test_user()
    actor = await _create_test_user(email="actor@example.com", nickname="actor")
    post_id = await _create_test_post(owner)

    # 댓글 생성
    async with transactional() as cur:
        await cur.execute(
            "INSERT INTO comment (post_id, author_id, content) VALUES (%s, %s, %s)",
            (post_id, actor, "테스트 댓글"),
        )
        comment_id = cur.lastrowid

    await notification_models.create_notification(
        user_id=owner,
        notification_type="comment",
        post_id=post_id,
        actor_id=actor,
        comment_id=comment_id,
    )

    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT comment_id FROM notification WHERE user_id = %s",
                (owner,),
            )
            row = await cur.fetchone()
            assert row[0] == comment_id


@pytest.mark.asyncio
async def test_get_notifications(db):
    """알림 목록 조회 시 올바른 데이터와 총 개수를 반환하는지 확인."""
    owner = await _create_test_user()
    actor = await _create_test_user(email="actor@example.com", nickname="actor")
    post_id = await _create_test_post(owner, title="좋아요 테스트")

    # 알림 2개 생성
    await notification_models.create_notification(
        user_id=owner,
        notification_type="comment",
        post_id=post_id,
        actor_id=actor,
    )
    await notification_models.create_notification(
        user_id=owner,
        notification_type="like",
        post_id=post_id,
        actor_id=actor,
    )

    notifications, total_count = await notification_models.get_notifications(owner)

    assert total_count == 2
    assert len(notifications) == 2

    # 두 타입 모두 포함되어 있는지 확인
    types = {n["type"] for n in notifications}
    assert types == {"comment", "like"}

    # 필드 구조 확인
    noti = notifications[0]
    assert "notification_id" in noti
    assert "type" in noti
    assert "post_id" in noti
    assert "is_read" in noti
    assert "created_at" in noti
    assert "actor" in noti
    assert "post_title" in noti
    assert noti["is_read"] is False
    assert noti["post_title"] == "좋아요 테스트"
    assert noti["actor"]["nickname"] == "actor"


@pytest.mark.asyncio
async def test_get_notifications_pagination(db):
    """알림 목록의 페이지네이션이 동작하는지 확인."""
    owner = await _create_test_user()
    actor = await _create_test_user(email="actor@example.com", nickname="actor")
    post_id = await _create_test_post(owner)

    # 알림 5개 생성
    for _ in range(5):
        await notification_models.create_notification(
            user_id=owner,
            notification_type="comment",
            post_id=post_id,
            actor_id=actor,
        )

    # limit=2, offset=0
    notifications, total_count = await notification_models.get_notifications(
        owner, offset=0, limit=2
    )
    assert total_count == 5
    assert len(notifications) == 2

    # limit=2, offset=3
    notifications, total_count = await notification_models.get_notifications(
        owner, offset=3, limit=2
    )
    assert total_count == 5
    assert len(notifications) == 2


@pytest.mark.asyncio
async def test_get_unread_count(db):
    """읽지 않은 알림 수를 정확히 반환하는지 확인."""
    owner = await _create_test_user()
    actor = await _create_test_user(email="actor@example.com", nickname="actor")
    post_id = await _create_test_post(owner)

    # 알림 3개 생성 (모두 미읽음)
    for _ in range(3):
        await notification_models.create_notification(
            user_id=owner,
            notification_type="like",
            post_id=post_id,
            actor_id=actor,
        )

    unread = await notification_models.get_unread_count(owner)
    assert unread == 3

    # 알림이 없는 사용자
    other_user = await _create_test_user(email="other@example.com", nickname="other")
    unread = await notification_models.get_unread_count(other_user)
    assert unread == 0


@pytest.mark.asyncio
async def test_mark_as_read(db):
    """개별 알림 읽음 처리가 동작하는지 확인."""
    owner = await _create_test_user()
    actor = await _create_test_user(email="actor@example.com", nickname="actor")
    post_id = await _create_test_post(owner)

    await notification_models.create_notification(
        user_id=owner,
        notification_type="comment",
        post_id=post_id,
        actor_id=actor,
    )

    # 알림 ID 조회
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id FROM notification WHERE user_id = %s",
                (owner,),
            )
            notification_id = (await cur.fetchone())[0]

    # 읽음 처리
    result = await notification_models.mark_as_read(notification_id, owner)
    assert result is True

    # DB에서 확인
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT is_read FROM notification WHERE id = %s",
                (notification_id,),
            )
            row = await cur.fetchone()
            assert row[0] == 1

    # 미읽음 수 확인
    unread = await notification_models.get_unread_count(owner)
    assert unread == 0


@pytest.mark.asyncio
async def test_mark_as_read_wrong_user(db):
    """다른 사용자의 알림은 읽음 처리할 수 없는지 확인."""
    owner = await _create_test_user()
    actor = await _create_test_user(email="actor@example.com", nickname="actor")
    other = await _create_test_user(email="other@example.com", nickname="other")
    post_id = await _create_test_post(owner)

    await notification_models.create_notification(
        user_id=owner,
        notification_type="comment",
        post_id=post_id,
        actor_id=actor,
    )

    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id FROM notification WHERE user_id = %s",
                (owner,),
            )
            notification_id = (await cur.fetchone())[0]

    # 다른 사용자가 읽음 처리 시도
    result = await notification_models.mark_as_read(notification_id, other)
    assert result is False


@pytest.mark.asyncio
async def test_mark_all_as_read(db):
    """모든 알림 일괄 읽음 처리가 동작하는지 확인."""
    owner = await _create_test_user()
    actor = await _create_test_user(email="actor@example.com", nickname="actor")
    post_id = await _create_test_post(owner)

    # 알림 3개 생성
    for _ in range(3):
        await notification_models.create_notification(
            user_id=owner,
            notification_type="like",
            post_id=post_id,
            actor_id=actor,
        )

    changed = await notification_models.mark_all_as_read(owner)
    assert changed == 3

    # 미읽음 수 확인
    unread = await notification_models.get_unread_count(owner)
    assert unread == 0

    # 이미 모두 읽은 상태에서 다시 호출
    changed = await notification_models.mark_all_as_read(owner)
    assert changed == 0


@pytest.mark.asyncio
async def test_delete_notification(db):
    """알림 삭제가 동작하는지 확인."""
    owner = await _create_test_user()
    actor = await _create_test_user(email="actor@example.com", nickname="actor")
    post_id = await _create_test_post(owner)

    await notification_models.create_notification(
        user_id=owner,
        notification_type="comment",
        post_id=post_id,
        actor_id=actor,
    )

    # 알림 ID 조회
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id FROM notification WHERE user_id = %s",
                (owner,),
            )
            notification_id = (await cur.fetchone())[0]

    result = await notification_models.delete_notification(notification_id, owner)
    assert result is True

    # 삭제 확인
    count = await _get_notification_count(owner)
    assert count == 0


@pytest.mark.asyncio
async def test_delete_notification_nonexistent(db):
    """존재하지 않는 알림 삭제 시 False를 반환하는지 확인."""
    owner = await _create_test_user()

    result = await notification_models.delete_notification(99999, owner)
    assert result is False


@pytest.mark.asyncio
async def test_delete_notification_wrong_user(db):
    """다른 사용자의 알림은 삭제할 수 없는지 확인."""
    owner = await _create_test_user()
    actor = await _create_test_user(email="actor@example.com", nickname="actor")
    other = await _create_test_user(email="other@example.com", nickname="other")
    post_id = await _create_test_post(owner)

    await notification_models.create_notification(
        user_id=owner,
        notification_type="comment",
        post_id=post_id,
        actor_id=actor,
    )

    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id FROM notification WHERE user_id = %s",
                (owner,),
            )
            notification_id = (await cur.fetchone())[0]

    # 다른 사용자가 삭제 시도
    result = await notification_models.delete_notification(notification_id, other)
    assert result is False

    # 원본 유지 확인
    count = await _get_notification_count(owner)
    assert count == 1


# ==========================================
# 2. API 엔드포인트 테스트 (Task 5에서 활성화)
# ==========================================


@pytest.mark.asyncio
async def test_create_notification_on_comment(authorized_user, client, user_payload):
    """댓글 작성 시 게시글 작성자에게 알림이 생성됩니다."""
    auth_client, user_info, _ = authorized_user

    # 다른 사용자 생성 (댓글 작성자)
    commenter_payload = {
        "email": "commenter@example.com",
        "password": "Password123!",
        "nickname": "commenter1",
    }
    signup_res = await client.post("/v1/users/", data=commenter_payload)
    assert signup_res.status_code == 201

    # 이메일 인증 처리
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE user SET email_verified = 1 WHERE email = %s",
                (commenter_payload["email"],),
            )

    login_res = await client.post(
        "/v1/auth/session",
        json={"email": commenter_payload["email"], "password": commenter_payload["password"]},
    )
    assert login_res.status_code == 200
    commenter_token = login_res.json()["data"]["access_token"]

    # 게시글 작성 (소유자)
    post_res = await auth_client.post(
        "/v1/posts/",
        json={"title": "알림 테스트 게시글", "content": "알림 테스트용 게시글입니다.", "category_id": 1},
    )
    assert post_res.status_code == 201
    post_id = post_res.json()["data"]["post_id"]

    # 다른 사용자가 댓글 작성
    from httpx import AsyncClient, ASGITransport
    from main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {commenter_token}"},
    ) as commenter_client:
        comment_res = await commenter_client.post(
            f"/v1/posts/{post_id}/comments",
            json={"content": "알림 테스트 댓글"},
        )
        assert comment_res.status_code == 201

    # 게시글 작성자의 알림 확인
    noti_res = await auth_client.get("/v1/notifications/")
    assert noti_res.status_code == 200
    data = noti_res.json()["data"]
    assert data["pagination"]["total_count"] == 1
    assert data["notifications"][0]["type"] == "comment"
    assert data["notifications"][0]["post_id"] == post_id


@pytest.mark.asyncio
async def test_no_self_notification(authorized_user):
    """본인 게시글에 본인이 댓글 작성 시 알림이 생성되지 않습니다."""
    auth_client, user_info, _ = authorized_user

    # 게시글 작성
    post_res = await auth_client.post(
        "/v1/posts/",
        json={"title": "셀프 알림 테스트", "content": "본인 게시글입니다.", "category_id": 1},
    )
    assert post_res.status_code == 201
    post_id = post_res.json()["data"]["post_id"]

    # 본인이 댓글 작성
    comment_res = await auth_client.post(
        f"/v1/posts/{post_id}/comments",
        json={"content": "본인 댓글"},
    )
    assert comment_res.status_code == 201

    # 알림이 생성되지 않았는지 확인
    noti_res = await auth_client.get("/v1/notifications/")
    assert noti_res.status_code == 200
    assert noti_res.json()["data"]["pagination"]["total_count"] == 0


@pytest.mark.asyncio
async def test_unread_count(authorized_user):
    """GET /v1/notifications/unread-count로 미읽음 수를 조회합니다."""
    auth_client, user_info, _ = authorized_user
    owner_id = user_info["user_id"]

    # 알림 직접 생성 (모델 함수 사용)
    actor_id = await _create_test_user(email="actor_api@example.com", nickname="actorapi")
    post_id = await _create_test_post(owner_id)
    for _ in range(3):
        await notification_models.create_notification(
            user_id=owner_id,
            notification_type="like",
            post_id=post_id,
            actor_id=actor_id,
        )

    res = await auth_client.get("/v1/notifications/unread-count")
    assert res.status_code == 200
    assert res.json()["data"]["unread_count"] == 3


@pytest.mark.asyncio
async def test_mark_notification_read(authorized_user):
    """PATCH /v1/notifications/{id}/read로 개별 알림을 읽음 처리합니다."""
    auth_client, user_info, _ = authorized_user
    owner_id = user_info["user_id"]

    actor_id = await _create_test_user(email="actor_read@example.com", nickname="actorread")
    post_id = await _create_test_post(owner_id)
    await notification_models.create_notification(
        user_id=owner_id,
        notification_type="comment",
        post_id=post_id,
        actor_id=actor_id,
    )

    # 알림 ID 조회
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id FROM notification WHERE user_id = %s", (owner_id,)
            )
            notification_id = (await cur.fetchone())[0]

    res = await auth_client.patch(f"/v1/notifications/{notification_id}/read")
    assert res.status_code == 200
    assert res.json()["code"] == "NOTIFICATION_READ"

    # 미읽음 수 확인
    count_res = await auth_client.get("/v1/notifications/unread-count")
    assert count_res.json()["data"]["unread_count"] == 0


@pytest.mark.asyncio
async def test_mark_all_read(authorized_user):
    """PATCH /v1/notifications/read-all로 모든 알림을 읽음 처리합니다."""
    auth_client, user_info, _ = authorized_user
    owner_id = user_info["user_id"]

    actor_id = await _create_test_user(email="actor_all@example.com", nickname="actorall")
    post_id = await _create_test_post(owner_id)
    for _ in range(3):
        await notification_models.create_notification(
            user_id=owner_id,
            notification_type="like",
            post_id=post_id,
            actor_id=actor_id,
        )

    res = await auth_client.patch("/v1/notifications/read-all")
    assert res.status_code == 200
    assert res.json()["code"] == "ALL_NOTIFICATIONS_READ"

    # 미읽음 수 확인
    count_res = await auth_client.get("/v1/notifications/unread-count")
    assert count_res.json()["data"]["unread_count"] == 0


@pytest.mark.asyncio
async def test_delete_notification_api(authorized_user):
    """DELETE /v1/notifications/{id}로 알림을 삭제합니다."""
    auth_client, user_info, _ = authorized_user
    owner_id = user_info["user_id"]

    actor_id = await _create_test_user(email="actor_del@example.com", nickname="actordel")
    post_id = await _create_test_post(owner_id)
    await notification_models.create_notification(
        user_id=owner_id,
        notification_type="comment",
        post_id=post_id,
        actor_id=actor_id,
    )

    # 알림 ID 조회
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id FROM notification WHERE user_id = %s", (owner_id,)
            )
            notification_id = (await cur.fetchone())[0]

    res = await auth_client.delete(f"/v1/notifications/{notification_id}")
    assert res.status_code == 200
    assert res.json()["code"] == "NOTIFICATION_DELETED"

    # 삭제 확인
    count = await _get_notification_count(owner_id)
    assert count == 0
