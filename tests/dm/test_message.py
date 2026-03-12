"""DM 메시지(message) 도메인 테스트."""

import pytest


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

async def _create_conversation(user_a: dict, user_b: dict) -> int:
    """두 사용자 간 대화를 생성하고 conversation_id를 반환한다."""
    res = await user_a["client"].post(
        "/v1/dms",
        json={"recipient_id": user_b["user_id"]},
    )
    assert res.status_code in (200, 201)
    return res.json()["data"]["conversation"]["id"]


# ---------------------------------------------------------------------------
# 테스트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_message_returns_201(two_users):
    """메시지 전송 시 201과 메시지 내용을 반환한다."""
    # Arrange
    user_a, user_b = two_users
    conv_id = await _create_conversation(user_a, user_b)

    # Act
    res = await user_a["client"].post(
        f"/v1/dms/{conv_id}/messages",
        json={"content": "안녕하세요!"},
    )

    # Assert
    assert res.status_code == 201
    msg = res.json()["data"]["message"]
    assert msg["content"] == "안녕하세요!"
    assert msg["conversation_id"] == conv_id
    assert msg["sender_id"] == user_a["user_id"]


@pytest.mark.asyncio
async def test_list_messages_with_pagination(two_users):
    """여러 메시지 전송 후 offset/limit 페이지네이션을 검증한다."""
    # Arrange
    user_a, user_b = two_users
    conv_id = await _create_conversation(user_a, user_b)

    # 5개 메시지 전송
    for i in range(5):
        await user_a["client"].post(
            f"/v1/dms/{conv_id}/messages",
            json={"content": f"메시지 {i}"},
        )

    # Act — offset=2, limit=2
    res = await user_a["client"].get(
        f"/v1/dms/{conv_id}",
        params={"offset": 2, "limit": 2},
    )

    # Assert
    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data["messages"]) == 2
    assert data["pagination"]["total_count"] == 5
    assert data["pagination"]["has_more"] is True


@pytest.mark.asyncio
async def test_delete_message_soft_deletes(two_users):
    """메시지 삭제 후 조회 시 is_deleted=True, content=None."""
    # Arrange
    user_a, user_b = two_users
    conv_id = await _create_conversation(user_a, user_b)

    msg_res = await user_a["client"].post(
        f"/v1/dms/{conv_id}/messages",
        json={"content": "삭제 예정"},
    )
    msg_id = msg_res.json()["data"]["message"]["id"]

    # Act
    del_res = await user_a["client"].delete(
        f"/v1/dms/{conv_id}/messages/{msg_id}",
    )

    # Assert
    assert del_res.status_code == 200

    get_res = await user_a["client"].get(f"/v1/dms/{conv_id}")
    messages = get_res.json()["data"]["messages"]
    deleted = [m for m in messages if m["id"] == msg_id][0]
    assert deleted["is_deleted"] is True
    assert deleted["content"] is None


@pytest.mark.asyncio
async def test_delete_other_user_message_returns_403(two_users):
    """상대방 메시지 삭제 시도 시 403."""
    # Arrange
    user_a, user_b = two_users
    conv_id = await _create_conversation(user_a, user_b)

    # user_b가 메시지 전송
    msg_res = await user_b["client"].post(
        f"/v1/dms/{conv_id}/messages",
        json={"content": "user_b의 메시지"},
    )
    msg_id = msg_res.json()["data"]["message"]["id"]

    # Act — user_a가 user_b 메시지 삭제 시도
    res = await user_a["client"].delete(
        f"/v1/dms/{conv_id}/messages/{msg_id}",
    )

    # Assert
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_send_empty_message_returns_422(two_users):
    """빈 문자열 메시지 전송 시 422."""
    # Arrange
    user_a, user_b = two_users
    conv_id = await _create_conversation(user_a, user_b)

    # Act
    res = await user_a["client"].post(
        f"/v1/dms/{conv_id}/messages",
        json={"content": ""},
    )

    # Assert
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_send_message_to_blocked_user_returns_403(two_users):
    """차단 관계에서 메시지 전송 시 403."""
    # Arrange
    user_a, user_b = two_users
    conv_id = await _create_conversation(user_a, user_b)

    # user_b가 user_a를 차단
    block_res = await user_b["client"].post(
        f"/v1/users/{user_a['user_id']}/block",
    )
    assert block_res.status_code == 201

    # Act — user_a가 메시지 전송 시도
    res = await user_a["client"].post(
        f"/v1/dms/{conv_id}/messages",
        json={"content": "차단 후 메시지"},
    )

    # Assert
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_send_message_as_non_participant_returns_403(three_users):
    """대화 비참여자가 메시지 전송 시 403."""
    # Arrange
    user_a, user_b, user_c = three_users
    conv_id = await _create_conversation(user_a, user_b)

    # Act — user_c가 user_a-user_b 대화에 메시지 전송 시도
    res = await user_c["client"].post(
        f"/v1/dms/{conv_id}/messages",
        json={"content": "제3자 메시지"},
    )

    # Assert
    assert res.status_code == 403
