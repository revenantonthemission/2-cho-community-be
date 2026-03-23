"""Engagement 도메인 -- 투표(Poll) 테스트."""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from tests.conftest import create_test_post, create_verified_user

# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------


async def _create_post_with_poll(
    client: AsyncClient,
    headers: dict,
    question: str = "좋아하는 언어?",
    options: list[str] | None = None,
    expires_at: str | None = None,
) -> dict:
    """투표가 포함된 게시글을 생성하고 응답 데이터를 반환한다."""
    poll = {
        "question": question,
        "options": options or ["Python", "JavaScript", "Go"],
    }
    if expires_at:
        poll["expires_at"] = expires_at

    res = await client.post(
        "/v1/posts/",
        json={
            "title": "투표 테스트 게시글",
            "content": "투표가 포함된 게시글입니다.",
            "category_id": 1,
            "poll": poll,
        },
        headers=headers,
    )
    assert res.status_code == 201, f"게시글 생성 실패: {res.text}"
    return res.json()["data"]


async def _get_poll_option_id(client: AsyncClient, headers: dict, post_id: int, index: int = 0) -> int:
    """게시글 상세에서 투표 옵션 ID를 가져온다."""
    detail = await client.get(f"/v1/posts/{post_id}", headers=headers)
    assert detail.status_code == 200
    return detail.json()["data"]["post"]["poll"]["options"][index]["option_id"]


# ---------------------------------------------------------------------------
# 투표가 포함된 게시글 생성
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_post_with_poll_returns_201(client: AsyncClient, fake):
    """투표가 포함된 게시글 생성 시 상세 조회에 poll 데이터가 포함된다."""
    # Arrange
    user = await create_verified_user(client, fake)

    # Act
    post_data = await _create_post_with_poll(client, user["headers"])
    post_id = post_data["post_id"]

    # Assert -- 상세 조회로 poll 확인
    detail = await client.get(f"/v1/posts/{post_id}", headers=user["headers"])
    assert detail.status_code == 200

    poll = detail.json()["data"]["post"]["poll"]
    assert poll is not None
    assert poll["question"] == "좋아하는 언어?"
    assert len(poll["options"]) == 3
    assert poll["total_votes"] == 0


@pytest.mark.asyncio
async def test_create_post_without_poll(client: AsyncClient, fake):
    """투표 없이 게시글 생성 시 poll은 None이다."""
    # Arrange
    user = await create_verified_user(client, fake)

    # Act
    post = await create_test_post(client, user["headers"])
    post_id = post["post_id"]

    # Assert
    detail = await client.get(f"/v1/posts/{post_id}", headers=user["headers"])
    assert detail.status_code == 200
    assert detail.json()["data"]["post"]["poll"] is None


# ---------------------------------------------------------------------------
# 투표 참여
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_vote_on_poll_returns_200(client: AsyncClient, fake):
    """투표에 성공적으로 참여하면 200을 반환한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    post_data = await _create_post_with_poll(client, user["headers"])
    post_id = post_data["post_id"]
    option_id = await _get_poll_option_id(client, user["headers"], post_id)

    # Act
    res = await client.post(
        f"/v1/posts/{post_id}/poll/vote",
        json={"option_id": option_id},
        headers=user["headers"],
    )

    # Assert
    assert res.status_code == 200
    assert res.json()["code"] == "POLL_VOTED"


@pytest.mark.asyncio
async def test_duplicate_vote_returns_409(client: AsyncClient, fake):
    """이미 투표한 투표에 다시 투표하면 409를 반환한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    post_data = await _create_post_with_poll(client, user["headers"])
    post_id = post_data["post_id"]
    option_id = await _get_poll_option_id(client, user["headers"], post_id)

    # 첫 번째 투표
    first = await client.post(
        f"/v1/posts/{post_id}/poll/vote",
        json={"option_id": option_id},
        headers=user["headers"],
    )
    assert first.status_code == 200

    # Act -- 중복 투표
    res = await client.post(
        f"/v1/posts/{post_id}/poll/vote",
        json={"option_id": option_id},
        headers=user["headers"],
    )

    # Assert
    assert res.status_code == 409


# ---------------------------------------------------------------------------
# 옵션 수 검증 (422)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_poll_too_many_options_returns_422(client: AsyncClient, fake):
    """투표 옵션이 10개를 초과하면 422를 반환한다."""
    # Arrange
    user = await create_verified_user(client, fake)

    # Act
    res = await client.post(
        "/v1/posts/",
        json={
            "title": "옵션 초과 테스트입니다",
            "content": "옵션이 너무 많은 투표입니다.",
            "category_id": 1,
            "poll": {
                "question": "너무 많은 옵션?",
                "options": [f"옵션{i}" for i in range(11)],
            },
        },
        headers=user["headers"],
    )

    # Assert
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_poll_too_few_options_returns_422(client: AsyncClient, fake):
    """투표 옵션이 2개 미만이면 422를 반환한다."""
    # Arrange
    user = await create_verified_user(client, fake)

    # Act
    res = await client.post(
        "/v1/posts/",
        json={
            "title": "옵션 부족 테스트입니다",
            "content": "옵션이 부족한 투표입니다.",
            "category_id": 1,
            "poll": {
                "question": "옵션 부족?",
                "options": ["하나만"],
            },
        },
        headers=user["headers"],
    )

    # Assert
    assert res.status_code == 422


# ---------------------------------------------------------------------------
# 투표 결과 확인
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_poll_results_after_vote(client: AsyncClient, fake):
    """투표 후 상세 조회 시 total_votes와 my_vote가 반영된다."""
    # Arrange
    user = await create_verified_user(client, fake)
    post_data = await _create_post_with_poll(client, user["headers"])
    post_id = post_data["post_id"]
    option_id = await _get_poll_option_id(client, user["headers"], post_id, index=1)

    # 투표
    vote_res = await client.post(
        f"/v1/posts/{post_id}/poll/vote",
        json={"option_id": option_id},
        headers=user["headers"],
    )
    assert vote_res.status_code == 200

    # Act -- 상세 조회
    detail = await client.get(f"/v1/posts/{post_id}", headers=user["headers"])

    # Assert
    poll = detail.json()["data"]["post"]["poll"]
    assert poll["total_votes"] == 1
    assert poll["my_vote"] == option_id


@pytest.mark.asyncio
async def test_poll_with_expiry(client: AsyncClient, fake):
    """만료일이 설정된 투표가 정상 생성되고, is_expired=False이다."""
    # Arrange
    user = await create_verified_user(client, fake)
    future = (datetime.now(UTC) + timedelta(days=7)).isoformat()

    # Act
    post_data = await _create_post_with_poll(client, user["headers"], expires_at=future)
    post_id = post_data["post_id"]

    # Assert
    detail = await client.get(f"/v1/posts/{post_id}", headers=user["headers"])
    assert detail.status_code == 200

    poll = detail.json()["data"]["post"]["poll"]
    assert poll["expires_at"] is not None
    assert poll["is_expired"] is False


@pytest.mark.asyncio
async def test_vote_without_auth_returns_401(client: AsyncClient, fake):
    """미인증 사용자의 투표 시 401을 반환한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    post_data = await _create_post_with_poll(client, user["headers"])
    post_id = post_data["post_id"]

    # Act -- 인증 헤더 없이 요청
    res = await client.post(
        f"/v1/posts/{post_id}/poll/vote",
        json={"option_id": 1},
    )

    # Assert
    assert res.status_code == 401


# ---------------------------------------------------------------------------
# 투표 취소 (DELETE)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_vote_returns_200(client: AsyncClient, fake):
    """투표 취소에 성공하면 200을 반환하고, 이후 my_vote가 None이 된다."""
    # Arrange
    user = await create_verified_user(client, fake)
    post_data = await _create_post_with_poll(client, user["headers"])
    post_id = post_data["post_id"]
    option_id = await _get_poll_option_id(client, user["headers"], post_id)

    # 먼저 투표
    vote_res = await client.post(
        f"/v1/posts/{post_id}/poll/vote",
        json={"option_id": option_id},
        headers=user["headers"],
    )
    assert vote_res.status_code == 200

    # Act -- 투표 취소
    res = await client.request(
        "DELETE",
        f"/v1/posts/{post_id}/poll/vote",
        headers=user["headers"],
    )

    # Assert
    assert res.status_code == 200
    assert res.json()["code"] == "POLL_VOTE_CANCELLED"

    # 상세 조회로 확인
    detail = await client.get(f"/v1/posts/{post_id}", headers=user["headers"])
    poll = detail.json()["data"]["post"]["poll"]
    assert poll["my_vote"] is None
    assert poll["total_votes"] == 0


@pytest.mark.asyncio
async def test_cancel_vote_without_vote_returns_404(client: AsyncClient, fake):
    """투표하지 않은 상태에서 취소하면 404를 반환한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    post_data = await _create_post_with_poll(client, user["headers"])
    post_id = post_data["post_id"]

    # Act -- 투표 없이 취소 요청
    res = await client.request(
        "DELETE",
        f"/v1/posts/{post_id}/poll/vote",
        headers=user["headers"],
    )

    # Assert
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_cancel_vote_expired_poll_returns_400(client: AsyncClient, fake):
    """만료된 투표의 취소 시 400을 반환한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    post_data = await _create_post_with_poll(client, user["headers"], expires_at=past)
    post_id = post_data["post_id"]

    # Act
    res = await client.request(
        "DELETE",
        f"/v1/posts/{post_id}/poll/vote",
        headers=user["headers"],
    )

    # Assert
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_cancel_vote_without_auth_returns_401(client: AsyncClient, fake):
    """미인증 사용자의 투표 취소 시 401을 반환한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    post_data = await _create_post_with_poll(client, user["headers"])
    post_id = post_data["post_id"]

    # Act
    res = await client.request(
        "DELETE",
        f"/v1/posts/{post_id}/poll/vote",
    )

    # Assert
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_cancel_then_revote(client: AsyncClient, fake):
    """투표 취소 후 다시 투표할 수 있다."""
    # Arrange
    user = await create_verified_user(client, fake)
    post_data = await _create_post_with_poll(client, user["headers"])
    post_id = post_data["post_id"]
    option_0 = await _get_poll_option_id(client, user["headers"], post_id, index=0)
    option_1 = await _get_poll_option_id(client, user["headers"], post_id, index=1)

    # 첫 번째 투표
    await client.post(
        f"/v1/posts/{post_id}/poll/vote",
        json={"option_id": option_0},
        headers=user["headers"],
    )

    # 취소
    cancel_res = await client.request(
        "DELETE",
        f"/v1/posts/{post_id}/poll/vote",
        headers=user["headers"],
    )
    assert cancel_res.status_code == 200

    # Act -- 다른 옵션으로 재투표
    res = await client.post(
        f"/v1/posts/{post_id}/poll/vote",
        json={"option_id": option_1},
        headers=user["headers"],
    )

    # Assert
    assert res.status_code == 200
    detail = await client.get(f"/v1/posts/{post_id}", headers=user["headers"])
    poll = detail.json()["data"]["post"]["poll"]
    assert poll["my_vote"] == option_1
    assert poll["total_votes"] == 1


# ---------------------------------------------------------------------------
# 투표 변경 (PUT)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_change_vote_returns_200(client: AsyncClient, fake):
    """투표 변경에 성공하면 200을 반환하고, my_vote가 변경된다."""
    # Arrange
    user = await create_verified_user(client, fake)
    post_data = await _create_post_with_poll(client, user["headers"])
    post_id = post_data["post_id"]
    option_0 = await _get_poll_option_id(client, user["headers"], post_id, index=0)
    option_1 = await _get_poll_option_id(client, user["headers"], post_id, index=1)

    # 첫 번째 투표
    vote_res = await client.post(
        f"/v1/posts/{post_id}/poll/vote",
        json={"option_id": option_0},
        headers=user["headers"],
    )
    assert vote_res.status_code == 200

    # Act -- 투표 변경
    res = await client.put(
        f"/v1/posts/{post_id}/poll/vote",
        json={"option_id": option_1},
        headers=user["headers"],
    )

    # Assert
    assert res.status_code == 200
    assert res.json()["code"] == "POLL_VOTE_CHANGED"

    # 상세 조회로 확인
    detail = await client.get(f"/v1/posts/{post_id}", headers=user["headers"])
    poll = detail.json()["data"]["post"]["poll"]
    assert poll["my_vote"] == option_1
    assert poll["total_votes"] == 1


@pytest.mark.asyncio
async def test_change_vote_without_vote_returns_404(client: AsyncClient, fake):
    """투표하지 않은 상태에서 변경하면 404를 반환한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    post_data = await _create_post_with_poll(client, user["headers"])
    post_id = post_data["post_id"]
    option_id = await _get_poll_option_id(client, user["headers"], post_id)

    # Act
    res = await client.put(
        f"/v1/posts/{post_id}/poll/vote",
        json={"option_id": option_id},
        headers=user["headers"],
    )

    # Assert
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_change_vote_invalid_option_returns_400(client: AsyncClient, fake):
    """존재하지 않는 옵션으로 변경하면 400을 반환한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    post_data = await _create_post_with_poll(client, user["headers"])
    post_id = post_data["post_id"]
    option_id = await _get_poll_option_id(client, user["headers"], post_id)

    # 먼저 투표
    await client.post(
        f"/v1/posts/{post_id}/poll/vote",
        json={"option_id": option_id},
        headers=user["headers"],
    )

    # Act -- 유효하지 않은 옵션 ID로 변경
    res = await client.put(
        f"/v1/posts/{post_id}/poll/vote",
        json={"option_id": 999999},
        headers=user["headers"],
    )

    # Assert
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_change_vote_expired_poll_returns_400(client: AsyncClient, fake):
    """만료된 투표를 변경하면 400을 반환한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    post_data = await _create_post_with_poll(client, user["headers"], expires_at=past)
    post_id = post_data["post_id"]

    # Act
    res = await client.put(
        f"/v1/posts/{post_id}/poll/vote",
        json={"option_id": 1},
        headers=user["headers"],
    )

    # Assert
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_change_vote_without_auth_returns_401(client: AsyncClient, fake):
    """미인증 사용자의 투표 변경 시 401을 반환한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    post_data = await _create_post_with_poll(client, user["headers"])
    post_id = post_data["post_id"]

    # Act
    res = await client.put(
        f"/v1/posts/{post_id}/poll/vote",
        json={"option_id": 1},
    )

    # Assert
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_change_vote_preserves_total_votes(client: AsyncClient, fake):
    """투표 변경 시 총 투표 수는 변하지 않고, 옵션별 수가 이동한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    other = await create_verified_user(client, fake)
    post_data = await _create_post_with_poll(client, user["headers"])
    post_id = post_data["post_id"]
    option_0 = await _get_poll_option_id(client, user["headers"], post_id, index=0)
    option_1 = await _get_poll_option_id(client, user["headers"], post_id, index=1)

    # 두 사용자가 같은 옵션에 투표
    await client.post(
        f"/v1/posts/{post_id}/poll/vote",
        json={"option_id": option_0},
        headers=user["headers"],
    )
    await client.post(
        f"/v1/posts/{post_id}/poll/vote",
        json={"option_id": option_0},
        headers=other["headers"],
    )

    # Act -- user가 option_1로 변경
    res = await client.put(
        f"/v1/posts/{post_id}/poll/vote",
        json={"option_id": option_1},
        headers=user["headers"],
    )
    assert res.status_code == 200

    # Assert
    detail = await client.get(f"/v1/posts/{post_id}", headers=user["headers"])
    poll = detail.json()["data"]["post"]["poll"]
    assert poll["total_votes"] == 2

    # 옵션별 확인
    opt_map = {opt["option_id"]: opt["vote_count"] for opt in poll["options"]}
    assert opt_map[option_0] == 1
    assert opt_map[option_1] == 1
