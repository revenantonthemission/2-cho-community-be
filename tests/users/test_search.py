"""Users 도메인 — 사용자 검색 테스트."""

import pytest
from httpx import AsyncClient

from tests.conftest import create_verified_user

# ---------------------------------------------------------------------------
# 닉네임 검색
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_users_by_nickname(client: AsyncClient, fake):
    """GET /v1/users/search?q= — 닉네임으로 사용자를 검색한다."""
    # Arrange — 검색 가능한 닉네임으로 사용자 생성
    await create_verified_user(client, fake, nickname="searchme1")
    searcher = await create_verified_user(client, fake)

    # Act — user1의 닉네임으로 검색
    res = await searcher["client"].get("/v1/users/search", params={"q": "searchme1"})

    # Assert
    assert res.status_code == 200
    results = res.json()["data"]
    nicknames = [r["nickname"] for r in results]
    assert "searchme1" in nicknames


@pytest.mark.asyncio
async def test_search_users_partial_match(client: AsyncClient, fake):
    """닉네임 접두어로 부분 매칭 검색이 동작한다."""
    # Arrange
    await create_verified_user(client, fake, nickname="partial01")
    await create_verified_user(client, fake, nickname="partial02")
    searcher = await create_verified_user(client, fake)

    # Act — 접두어 "partial"로 검색
    res = await searcher["client"].get("/v1/users/search", params={"q": "partial"})

    # Assert
    assert res.status_code == 200
    results = res.json()["data"]
    assert len(results) >= 2
    for r in results:
        assert r["nickname"].startswith("partial")


@pytest.mark.asyncio
async def test_search_users_no_results(client: AsyncClient, fake):
    """존재하지 않는 닉네임 검색 시 빈 리스트를 반환한다."""
    # Arrange
    searcher = await create_verified_user(client, fake)

    # Act
    res = await searcher["client"].get("/v1/users/search", params={"q": "nonexistent999"})

    # Assert
    assert res.status_code == 200
    assert res.json()["data"] == []


@pytest.mark.asyncio
async def test_search_users_for_mention(client: AsyncClient, fake):
    """멘션 자동완성용 응답 구조를 검증한다 (user_id, nickname, profileImageUrl)."""
    # Arrange
    await create_verified_user(client, fake, nickname="mention01")
    searcher = await create_verified_user(client, fake)

    # Act
    res = await searcher["client"].get("/v1/users/search", params={"q": "mention"})

    # Assert — 응답 구조 검증
    assert res.status_code == 200
    results = res.json()["data"]
    assert len(results) >= 1
    first = results[0]
    assert "user_id" in first
    assert "nickname" in first
    assert "profileImageUrl" in first
