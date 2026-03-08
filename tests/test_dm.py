"""test_dm: DM(쪽지) 기능 테스트."""

import pytest
from httpx import AsyncClient, ASGITransport
from database.connection import get_connection
from main import app


async def _create_second_user(client: AsyncClient) -> tuple[AsyncClient, dict]:
    """두 번째 인증 사용자를 생성합니다."""
    payload = {
        "email": "dm_target@example.com",
        "password": "Password123!",
        "nickname": "dmtest1",
    }
    signup_res = await client.post("/v1/users/", data=payload)
    assert signup_res.status_code == 201

    # 이메일 인증
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE user SET email_verified = 1 WHERE email = %s",
                (payload["email"],),
            )

    login_res = await client.post(
        "/v1/auth/session",
        json={"email": payload["email"], "password": payload["password"]},
    )
    assert login_res.status_code == 200

    data = login_res.json()
    access_token = data["data"]["access_token"]
    user_info = data["data"]["user"]

    transport = ASGITransport(app=app)
    auth_client = AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {access_token}"},
        cookies=login_res.cookies,
    )

    return auth_client, user_info


async def _create_third_user(client: AsyncClient) -> tuple[AsyncClient, dict]:
    """세 번째 인증 사용자를 생성합니다."""
    payload = {
        "email": "dm_third@example.com",
        "password": "Password123!",
        "nickname": "dmtest2",
    }
    signup_res = await client.post("/v1/users/", data=payload)
    assert signup_res.status_code == 201

    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE user SET email_verified = 1 WHERE email = %s",
                (payload["email"],),
            )

    login_res = await client.post(
        "/v1/auth/session",
        json={"email": payload["email"], "password": payload["password"]},
    )
    assert login_res.status_code == 200

    data = login_res.json()
    access_token = data["data"]["access_token"]
    user_info = data["data"]["user"]

    transport = ASGITransport(app=app)
    auth_client = AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {access_token}"},
        cookies=login_res.cookies,
    )

    return auth_client, user_info


@pytest.mark.asyncio
async def test_create_conversation(client: AsyncClient, authorized_user):
    """대화 생성 (201), 상대방 정보 포함 확인."""
    cli, _, _ = authorized_user
    target_cli, target_info = await _create_second_user(client)

    async with target_cli:
        res = await cli.post(
            "/v1/dms",
            json={"recipient_id": target_info["user_id"]},
        )
        assert res.status_code == 201
        data = res.json()["data"]
        assert "conversation" in data
        assert "id" in data["conversation"]
        assert data["conversation"]["other_user"]["user_id"] == target_info["user_id"]


@pytest.mark.asyncio
async def test_create_conversation_returns_existing(client: AsyncClient, authorized_user):
    """같은 상대에게 대화 생성 두 번 → 동일 ID 반환, 두 번째는 200."""
    cli, _, _ = authorized_user
    target_cli, target_info = await _create_second_user(client)

    async with target_cli:
        res1 = await cli.post(
            "/v1/dms",
            json={"recipient_id": target_info["user_id"]},
        )
        assert res1.status_code == 201
        conv_id1 = res1.json()["data"]["conversation"]["id"]

        res2 = await cli.post(
            "/v1/dms",
            json={"recipient_id": target_info["user_id"]},
        )
        assert res2.status_code == 200
        conv_id2 = res2.json()["data"]["conversation"]["id"]
        assert conv_id1 == conv_id2


@pytest.mark.asyncio
async def test_create_conversation_self(client: AsyncClient, authorized_user):
    """자기 자신에게 대화 생성 (400)."""
    cli, user_info, _ = authorized_user

    res = await cli.post(
        "/v1/dms",
        json={"recipient_id": user_info["user_id"]},
    )
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_create_conversation_blocked_user(client: AsyncClient, authorized_user):
    """상대가 나를 차단한 경우 대화 생성 불가 (403)."""
    cli, user_info, _ = authorized_user
    target_cli, target_info = await _create_second_user(client)

    async with target_cli:
        # 상대방이 나를 차단
        block_res = await target_cli.post(f"/v1/users/{user_info['user_id']}/block")
        assert block_res.status_code == 201

        # 차단된 상태에서 대화 시도
        res = await cli.post(
            "/v1/dms",
            json={"recipient_id": target_info["user_id"]},
        )
        assert res.status_code == 403


@pytest.mark.asyncio
async def test_send_message(client: AsyncClient, authorized_user):
    """메시지 전송 (201), 내용 확인."""
    cli, _, _ = authorized_user
    target_cli, target_info = await _create_second_user(client)

    async with target_cli:
        # 대화 생성
        conv_res = await cli.post(
            "/v1/dms",
            json={"recipient_id": target_info["user_id"]},
        )
        conv_id = conv_res.json()["data"]["conversation"]["id"]

        # 메시지 전송
        res = await cli.post(
            f"/v1/dms/{conv_id}/messages",
            json={"content": "안녕하세요!"},
        )
        assert res.status_code == 201
        data = res.json()["data"]
        assert data["message"]["content"] == "안녕하세요!"
        assert data["message"]["conversation_id"] == conv_id


@pytest.mark.asyncio
async def test_get_messages(client: AsyncClient, authorized_user):
    """메시지 목록 조회 (200), 순서 확인."""
    cli, _, _ = authorized_user
    target_cli, target_info = await _create_second_user(client)

    async with target_cli:
        conv_res = await cli.post(
            "/v1/dms",
            json={"recipient_id": target_info["user_id"]},
        )
        conv_id = conv_res.json()["data"]["conversation"]["id"]

        # 여러 메시지 전송
        await cli.post(
            f"/v1/dms/{conv_id}/messages",
            json={"content": "첫 번째"},
        )
        await target_cli.post(
            f"/v1/dms/{conv_id}/messages",
            json={"content": "두 번째"},
        )

        # 조회
        res = await cli.get(f"/v1/dms/{conv_id}")
        assert res.status_code == 200
        messages = res.json()["data"]["messages"]
        assert len(messages) == 2
        # 시간순 정렬 확인
        assert messages[0]["content"] == "첫 번째"
        assert messages[1]["content"] == "두 번째"


@pytest.mark.asyncio
async def test_send_message_non_participant(client: AsyncClient, authorized_user):
    """대화 참여자가 아닌 사용자가 메시지 전송 (403)."""
    cli, _, _ = authorized_user
    target_cli, target_info = await _create_second_user(client)
    third_cli, _ = await _create_third_user(client)

    async with target_cli, third_cli:
        conv_res = await cli.post(
            "/v1/dms",
            json={"recipient_id": target_info["user_id"]},
        )
        conv_id = conv_res.json()["data"]["conversation"]["id"]

        # 제3자가 메시지 전송 시도
        res = await third_cli.post(
            f"/v1/dms/{conv_id}/messages",
            json={"content": "침입 메시지"},
        )
        assert res.status_code == 403


@pytest.mark.asyncio
async def test_mark_read(client: AsyncClient, authorized_user):
    """메시지 읽음 처리 (200)."""
    cli, _, _ = authorized_user
    target_cli, target_info = await _create_second_user(client)

    async with target_cli:
        conv_res = await cli.post(
            "/v1/dms",
            json={"recipient_id": target_info["user_id"]},
        )
        conv_id = conv_res.json()["data"]["conversation"]["id"]

        # 상대방이 메시지 전송
        await target_cli.post(
            f"/v1/dms/{conv_id}/messages",
            json={"content": "읽어주세요"},
        )

        # 읽음 처리
        res = await cli.patch(f"/v1/dms/{conv_id}/read")
        assert res.status_code == 200


@pytest.mark.asyncio
async def test_unread_count(client: AsyncClient, authorized_user):
    """읽지 않은 대화 수 조회 (200)."""
    cli, _, _ = authorized_user
    target_cli, target_info = await _create_second_user(client)

    async with target_cli:
        conv_res = await cli.post(
            "/v1/dms",
            json={"recipient_id": target_info["user_id"]},
        )
        conv_id = conv_res.json()["data"]["conversation"]["id"]

        # 상대방이 메시지 전송 → 내가 읽지 않은 상태
        await target_cli.post(
            f"/v1/dms/{conv_id}/messages",
            json={"content": "안읽은 메시지"},
        )

        res = await cli.get("/v1/dms/unread-count")
        assert res.status_code == 200
        assert res.json()["data"]["unread_count"] >= 1


@pytest.mark.asyncio
async def test_get_conversations(client: AsyncClient, authorized_user):
    """대화 목록 조회 (200), 최소 1개."""
    cli, _, _ = authorized_user
    target_cli, target_info = await _create_second_user(client)

    async with target_cli:
        await cli.post(
            "/v1/dms",
            json={"recipient_id": target_info["user_id"]},
        )

        res = await cli.get("/v1/dms")
        assert res.status_code == 200
        data = res.json()["data"]
        assert len(data["conversations"]) >= 1
        assert "other_user" in data["conversations"][0]


@pytest.mark.asyncio
async def test_delete_conversation(client: AsyncClient, authorized_user):
    """대화 삭제 (200) 후 조회 시 404."""
    cli, _, _ = authorized_user
    target_cli, target_info = await _create_second_user(client)

    async with target_cli:
        conv_res = await cli.post(
            "/v1/dms",
            json={"recipient_id": target_info["user_id"]},
        )
        conv_id = conv_res.json()["data"]["conversation"]["id"]

        # 삭제
        del_res = await cli.delete(f"/v1/dms/{conv_id}")
        assert del_res.status_code == 200

        # 삭제 후 메시지 조회 시 404
        get_res = await cli.get(f"/v1/dms/{conv_id}")
        assert get_res.status_code == 404


@pytest.mark.asyncio
async def test_send_empty_message(client: AsyncClient, authorized_user):
    """빈 메시지 전송 (422)."""
    cli, _, _ = authorized_user
    target_cli, target_info = await _create_second_user(client)

    async with target_cli:
        conv_res = await cli.post(
            "/v1/dms",
            json={"recipient_id": target_info["user_id"]},
        )
        conv_id = conv_res.json()["data"]["conversation"]["id"]

        res = await cli.post(
            f"/v1/dms/{conv_id}/messages",
            json={"content": ""},
        )
        assert res.status_code == 422


@pytest.mark.asyncio
async def test_send_long_message(client: AsyncClient, authorized_user):
    """2001자 메시지 전송 (422)."""
    cli, _, _ = authorized_user
    target_cli, target_info = await _create_second_user(client)

    async with target_cli:
        conv_res = await cli.post(
            "/v1/dms",
            json={"recipient_id": target_info["user_id"]},
        )
        conv_id = conv_res.json()["data"]["conversation"]["id"]

        res = await cli.post(
            f"/v1/dms/{conv_id}/messages",
            json={"content": "가" * 2001},
        )
        assert res.status_code == 422


@pytest.mark.asyncio
async def test_dm_unauthorized(client: AsyncClient):
    """미인증 사용자 DM 접근 (401)."""
    res = await client.get("/v1/dms")
    assert res.status_code == 401
