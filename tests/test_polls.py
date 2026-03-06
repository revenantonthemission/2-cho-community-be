"""test_polls: 투표(Poll) 시스템 테스트 모듈."""

import pytest
from datetime import datetime, timedelta, timezone
from httpx import AsyncClient


# ==========================================
# 헬퍼 함수
# ==========================================

async def create_post_with_poll(
    cli: AsyncClient,
    question: str = "좋아하는 언어?",
    options: list[str] | None = None,
    expires_at: str | None = None,
) -> int:
    """투표가 포함된 게시글 생성 헬퍼."""
    poll = {
        "question": question,
        "options": options or ["Python", "JavaScript", "Go"],
    }
    if expires_at:
        poll["expires_at"] = expires_at

    res = await cli.post("/v1/posts/", json={
        "title": "투표 테스트 게시글",
        "content": "투표가 포함된 게시글입니다.",
        "category_id": 1,
        "poll": poll,
    })
    assert res.status_code == 201, f"게시글 생성 실패: {res.text}"
    return res.json()["data"]["post_id"]


async def create_post_without_poll(cli: AsyncClient) -> int:
    """투표 없는 게시글 생성 헬퍼."""
    res = await cli.post("/v1/posts/", json={
        "title": "일반 게시글 제목입니다",
        "content": "투표 없는 게시글입니다.",
        "category_id": 1,
    })
    assert res.status_code == 201, f"게시글 생성 실패: {res.text}"
    return res.json()["data"]["post_id"]


# ==========================================
# POLL-01: 투표가 포함된 게시글 생성 (201)
# ==========================================

@pytest.mark.asyncio
async def test_poll_01_create_post_with_poll(client: AsyncClient, authorized_user):
    """투표가 포함된 게시글 생성 시 상세 조회에 poll 데이터가 포함된다."""
    cli, _, _ = authorized_user

    post_id = await create_post_with_poll(cli)

    detail_res = await cli.get(f"/v1/posts/{post_id}")
    assert detail_res.status_code == 200

    post = detail_res.json()["data"]["post"]
    assert post["poll"] is not None
    assert post["poll"]["question"] == "좋아하는 언어?"
    assert len(post["poll"]["options"]) == 3
    assert post["poll"]["total_votes"] == 0


# ==========================================
# POLL-02: 투표 없는 게시글 (poll=None)
# ==========================================

@pytest.mark.asyncio
async def test_poll_02_create_post_without_poll(client: AsyncClient, authorized_user):
    """투표 없이 게시글 생성 시 poll은 None이다."""
    cli, _, _ = authorized_user

    post_id = await create_post_without_poll(cli)

    detail_res = await cli.get(f"/v1/posts/{post_id}")
    assert detail_res.status_code == 200

    post = detail_res.json()["data"]["post"]
    assert post["poll"] is None


# ==========================================
# POLL-03: 투표 참여 (200)
# ==========================================

@pytest.mark.asyncio
async def test_poll_03_vote_on_poll(client: AsyncClient, authorized_user):
    """투표에 성공적으로 참여한다."""
    cli, _, _ = authorized_user

    post_id = await create_post_with_poll(cli)

    # 투표 옵션 ID 가져오기
    detail_res = await cli.get(f"/v1/posts/{post_id}")
    options = detail_res.json()["data"]["post"]["poll"]["options"]
    option_id = options[0]["option_id"]

    # 투표
    vote_res = await cli.post(f"/v1/posts/{post_id}/poll/vote", json={
        "option_id": option_id,
    })
    assert vote_res.status_code == 200
    assert vote_res.json()["code"] == "POLL_VOTED"


# ==========================================
# POLL-04: 중복 투표 (409)
# ==========================================

@pytest.mark.asyncio
async def test_poll_04_duplicate_vote(client: AsyncClient, authorized_user):
    """이미 투표한 투표에 다시 투표하면 409 에러가 발생한다."""
    cli, _, _ = authorized_user

    post_id = await create_post_with_poll(cli)

    detail_res = await cli.get(f"/v1/posts/{post_id}")
    options = detail_res.json()["data"]["post"]["poll"]["options"]
    option_id = options[0]["option_id"]

    # 첫 번째 투표
    await cli.post(f"/v1/posts/{post_id}/poll/vote", json={"option_id": option_id})

    # 중복 투표
    vote_res = await cli.post(f"/v1/posts/{post_id}/poll/vote", json={"option_id": option_id})
    assert vote_res.status_code == 409


# ==========================================
# POLL-05: 투표 결과 (total_votes, my_vote)
# ==========================================

@pytest.mark.asyncio
async def test_poll_05_vote_results(client: AsyncClient, authorized_user):
    """투표 후 상세 조회 시 total_votes와 my_vote가 반영된다."""
    cli, _, _ = authorized_user

    post_id = await create_post_with_poll(cli)

    # 옵션 ID 가져오기
    detail_res = await cli.get(f"/v1/posts/{post_id}")
    options = detail_res.json()["data"]["post"]["poll"]["options"]
    option_id = options[1]["option_id"]

    # 투표
    await cli.post(f"/v1/posts/{post_id}/poll/vote", json={"option_id": option_id})

    # 결과 확인
    detail_res = await cli.get(f"/v1/posts/{post_id}")
    poll = detail_res.json()["data"]["post"]["poll"]
    assert poll["total_votes"] == 1
    assert poll["my_vote"] == option_id


# ==========================================
# POLL-06: 옵션 10개 초과 시 422
# ==========================================

@pytest.mark.asyncio
async def test_poll_06_too_many_options(client: AsyncClient, authorized_user):
    """투표 옵션이 10개를 초과하면 422 에러가 발생한다."""
    cli, _, _ = authorized_user

    res = await cli.post("/v1/posts/", json={
        "title": "옵션 초과 테스트입니다",
        "content": "옵션이 너무 많은 투표입니다.",
        "category_id": 1,
        "poll": {
            "question": "너무 많은 옵션?",
            "options": [f"옵션{i}" for i in range(11)],
        },
    })
    assert res.status_code == 422


# ==========================================
# POLL-07: 옵션 2개 미만 시 422
# ==========================================

@pytest.mark.asyncio
async def test_poll_07_too_few_options(client: AsyncClient, authorized_user):
    """투표 옵션이 2개 미만이면 422 에러가 발생한다."""
    cli, _, _ = authorized_user

    res = await cli.post("/v1/posts/", json={
        "title": "옵션 부족 테스트입니다",
        "content": "옵션이 부족한 투표입니다.",
        "category_id": 1,
        "poll": {
            "question": "옵션 부족?",
            "options": ["하나만"],
        },
    })
    assert res.status_code == 422


# ==========================================
# POLL-08: 미인증 투표 (401)
# ==========================================

@pytest.mark.asyncio
async def test_poll_08_vote_unauthorized(client: AsyncClient, authorized_user):
    """비로그인 사용자는 투표할 수 없다."""
    cli, _, _ = authorized_user

    post_id = await create_post_with_poll(cli)

    # 비인증 클라이언트로 투표
    vote_res = await client.post(f"/v1/posts/{post_id}/poll/vote", json={
        "option_id": 1,
    })
    assert vote_res.status_code == 401


# ==========================================
# POLL-09: 만료일 설정 투표
# ==========================================

@pytest.mark.asyncio
async def test_poll_09_poll_with_expiry(client: AsyncClient, authorized_user):
    """만료일이 설정된 투표가 정상 생성되고, is_expired=False이다."""
    cli, _, _ = authorized_user

    future = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    post_id = await create_post_with_poll(cli, expires_at=future)

    detail_res = await cli.get(f"/v1/posts/{post_id}")
    assert detail_res.status_code == 200

    poll = detail_res.json()["data"]["post"]["poll"]
    assert poll["expires_at"] is not None
    assert poll["is_expired"] is False
