"""Engagement 도메인 -- 투표(Poll) 테스트."""

import pytest
from datetime import datetime, timedelta, timezone
from httpx import AsyncClient

from tests.conftest import create_verified_user, create_test_post


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


async def _get_poll_option_id(
    client: AsyncClient, headers: dict, post_id: int, index: int = 0
) -> int:
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
    future = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()

    # Act
    post_data = await _create_post_with_poll(
        client, user["headers"], expires_at=future
    )
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
