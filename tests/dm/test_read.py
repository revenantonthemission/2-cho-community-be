"""DM 읽음(read) 상태 도메인 테스트."""

import pytest

from tests.conftest import create_verified_user

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
async def test_mark_conversation_as_read(two_users):
    """PATCH /v1/dms/{id}/read 로 읽음 처리하면 read_count를 반환한다."""
    # Arrange
    user_a, user_b = two_users
    conv_id = await _create_conversation(user_a, user_b)

    # user_b가 메시지 전송 → user_a에게 unread
    await user_b["client"].post(
        f"/v1/dms/{conv_id}/messages",
        json={"content": "읽어주세요"},
    )

    # Act
    res = await user_a["client"].patch(f"/v1/dms/{conv_id}/read")

    # Assert
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["read_count"] >= 1


@pytest.mark.asyncio
async def test_unread_count_returns_correct_number(two_users):
    """상대방 메시지 전송 후 unread-count가 1 이상이다."""
    # Arrange
    user_a, user_b = two_users
    conv_id = await _create_conversation(user_a, user_b)

    await user_b["client"].post(
        f"/v1/dms/{conv_id}/messages",
        json={"content": "안읽은 메시지"},
    )

    # Act
    res = await user_a["client"].get("/v1/dms/unread-count")

    # Assert
    assert res.status_code == 200
    assert res.json()["data"]["unread_count"] >= 1


@pytest.mark.asyncio
async def test_unread_count_decreases_after_read(two_users):
    """읽음 처리 후 unread-count가 감소한다."""
    # Arrange
    user_a, user_b = two_users
    conv_id = await _create_conversation(user_a, user_b)

    await user_b["client"].post(
        f"/v1/dms/{conv_id}/messages",
        json={"content": "읽기 전 메시지"},
    )

    before_res = await user_a["client"].get("/v1/dms/unread-count")
    before_count = before_res.json()["data"]["unread_count"]
    assert before_count >= 1

    # Act — 읽음 처리
    await user_a["client"].patch(f"/v1/dms/{conv_id}/read")

    # Assert
    after_res = await user_a["client"].get("/v1/dms/unread-count")
    after_count = after_res.json()["data"]["unread_count"]
    assert after_count < before_count


@pytest.mark.asyncio
async def test_mark_read_non_participant_returns_403(client, fake):
    """대화 비참여자가 읽음 처리 시 403."""
    # Arrange — 3명 필요
    user_a = await create_verified_user(client, fake)
    user_b = await create_verified_user(client, fake)
    user_c = await create_verified_user(client, fake)

    async with user_a["client"], user_b["client"], user_c["client"]:
        conv_id = await _create_conversation(user_a, user_b)

        # Act — user_c가 읽음 처리 시도
        res = await user_c["client"].patch(f"/v1/dms/{conv_id}/read")

        # Assert
        assert res.status_code == 403
