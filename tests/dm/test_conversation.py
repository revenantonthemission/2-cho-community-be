"""DM 대화(conversation) 도메인 테스트."""

import pytest


@pytest.mark.asyncio
async def test_create_conversation_returns_201(two_users):
    """대화 생성 시 201과 conversation 정보를 반환한다."""
    # Arrange
    user_a, user_b = two_users

    # Act
    res = await user_a["client"].post(
        "/v1/dms",
        json={"recipient_id": user_b["user_id"]},
    )

    # Assert
    assert res.status_code == 201
    data = res.json()["data"]
    assert "conversation" in data
    conv = data["conversation"]
    assert "id" in conv
    assert conv["other_user"]["user_id"] == user_b["user_id"]
    assert conv["other_user"]["nickname"] == user_b["nickname"]


@pytest.mark.asyncio
async def test_create_conversation_returns_existing(two_users):
    """같은 상대에게 두 번 생성 요청 시 기존 대화(200)를 반환한다."""
    # Arrange
    user_a, user_b = two_users

    res1 = await user_a["client"].post(
        "/v1/dms",
        json={"recipient_id": user_b["user_id"]},
    )
    assert res1.status_code == 201
    conv_id_1 = res1.json()["data"]["conversation"]["id"]

    # Act — 동일 요청 재전송
    res2 = await user_a["client"].post(
        "/v1/dms",
        json={"recipient_id": user_b["user_id"]},
    )

    # Assert
    assert res2.status_code == 200
    conv_id_2 = res2.json()["data"]["conversation"]["id"]
    assert conv_id_1 == conv_id_2


@pytest.mark.asyncio
async def test_list_conversations(two_users):
    """대화 생성 후 목록 조회에 포함된다."""
    # Arrange
    user_a, user_b = two_users

    conv_res = await user_a["client"].post(
        "/v1/dms",
        json={"recipient_id": user_b["user_id"]},
    )
    conv_id = conv_res.json()["data"]["conversation"]["id"]

    # Act
    res = await user_a["client"].get("/v1/dms")

    # Assert
    assert res.status_code == 200
    data = res.json()["data"]
    conv_ids = [c["id"] for c in data["conversations"]]
    assert conv_id in conv_ids
    assert "pagination" in data


@pytest.mark.asyncio
async def test_delete_conversation(two_users):
    """대화 삭제(200) 후 메시지 조회 시 404."""
    # Arrange
    user_a, user_b = two_users

    conv_res = await user_a["client"].post(
        "/v1/dms",
        json={"recipient_id": user_b["user_id"]},
    )
    conv_id = conv_res.json()["data"]["conversation"]["id"]

    # Act
    del_res = await user_a["client"].delete(f"/v1/dms/{conv_id}")

    # Assert
    assert del_res.status_code == 200

    get_res = await user_a["client"].get(f"/v1/dms/{conv_id}")
    assert get_res.status_code == 404


@pytest.mark.asyncio
async def test_create_conversation_with_self_returns_400(two_users):
    """자기 자신에게 대화 생성 시 400."""
    # Arrange
    user_a, _ = two_users

    # Act
    res = await user_a["client"].post(
        "/v1/dms",
        json={"recipient_id": user_a["user_id"]},
    )

    # Assert
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_create_conversation_with_blocked_user_returns_403(two_users):
    """차단 관계에서 대화 생성 시 403."""
    # Arrange — user_b가 user_a를 차단
    user_a, user_b = two_users

    block_res = await user_b["client"].post(
        f"/v1/users/{user_a['user_id']}/block",
    )
    assert block_res.status_code == 201

    # Act — user_a가 user_b에게 대화 생성 시도
    res = await user_a["client"].post(
        "/v1/dms",
        json={"recipient_id": user_b["user_id"]},
    )

    # Assert
    assert res.status_code == 403
