"""Content 도메인 — 태그 상세 조회/수정 API 테스트."""

import aiomysql
import pytest
from httpx import AsyncClient

from core.database.connection import get_connection
from tests.conftest import create_test_post, create_verified_user

# ---------------------------------------------------------------------------
# 태그 상세 조회 성공
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_tag_detail_success(client: AsyncClient, fake):
    """태그가 포함된 게시글 생성 후 태그 상세 조회 시 200을 반환한다."""
    user = await create_verified_user(client, fake)
    await create_test_post(client, user["headers"], tags=["ubuntu"])

    res = await client.get("/v1/tags/ubuntu")

    assert res.status_code == 200
    data = res.json()["data"]["tag"]
    assert data["name"] == "ubuntu"
    assert data["post_count"] >= 1
    assert data["wiki_count"] >= 0


# ---------------------------------------------------------------------------
# 존재하지 않는 태그 조회
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_tag_detail_not_found(client: AsyncClient, fake):
    """존재하지 않는 태그를 조회하면 404를 반환한다."""
    res = await client.get("/v1/tags/nonexistent-tag-xyz")

    assert res.status_code == 404


# ---------------------------------------------------------------------------
# 태그 설명 수정 성공
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_tag_description(client: AsyncClient, fake):
    """신뢰 등급 1 이상 사용자가 태그 설명을 수정하면 200을 반환한다."""
    user = await create_verified_user(client, fake)
    await create_test_post(client, user["headers"], tags=["ubuntu"])

    # 신뢰 등급 1로 설정 (trust_level 직접 업데이트)
    async with get_connection() as conn, conn.cursor(aiomysql.DictCursor) as cur:
        await cur.execute(
            "UPDATE user SET trust_level = 1, reputation_score = 50 WHERE id = %s",
            (user["user_id"],),
        )

    res = await client.put(
        "/v1/tags/ubuntu",
        json={"description": "우분투 관련 태그입니다.", "body": "우분투에 대한 상세 설명"},
        headers=user["headers"],
    )

    assert res.status_code == 200
    data = res.json()["data"]["tag"]
    assert data["description"] == "우분투 관련 태그입니다."
    assert data["body"] == "우분투에 대한 상세 설명"


# ---------------------------------------------------------------------------
# 태그 수정 권한 부족 (신뢰 등급 0)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_tag_requires_trust_level(client: AsyncClient, fake):
    """신뢰 등급 0 사용자가 태그를 수정하려 하면 403을 반환한다."""
    user = await create_verified_user(client, fake)
    await create_test_post(client, user["headers"], tags=["ubuntu"])

    res = await client.put(
        "/v1/tags/ubuntu",
        json={"description": "수정 시도"},
        headers=user["headers"],
    )

    assert res.status_code == 403


# ---------------------------------------------------------------------------
# 미인증 상태에서 태그 수정 시도
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_tag_requires_auth(client: AsyncClient, fake):
    """인증 없이 태그를 수정하려 하면 401을 반환한다."""
    user = await create_verified_user(client, fake)
    await create_test_post(client, user["headers"], tags=["ubuntu"])

    res = await client.put(
        "/v1/tags/ubuntu",
        json={"description": "수정 시도"},
    )

    assert res.status_code == 401


# ---------------------------------------------------------------------------
# 태그 검색 시 설명 포함 여부
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_tags_includes_description(client: AsyncClient, fake):
    """태그에 설명을 설정한 후 검색하면 description 필드가 포함된다."""
    user = await create_verified_user(client, fake)
    await create_test_post(client, user["headers"], tags=["ubuntu"])

    # 신뢰 등급 1로 설정 (trust_level 직접 업데이트)
    async with get_connection() as conn, conn.cursor(aiomysql.DictCursor) as cur:
        await cur.execute(
            "UPDATE user SET trust_level = 1, reputation_score = 50 WHERE id = %s",
            (user["user_id"],),
        )

    # 태그 설명 설정
    await client.put(
        "/v1/tags/ubuntu",
        json={"description": "우분투 관련 태그"},
        headers=user["headers"],
    )

    # 태그 검색
    res = await client.get("/v1/tags/", params={"search": "ubuntu"})

    assert res.status_code == 200
    tags = res.json()["data"]["tags"]
    assert len(tags) >= 1
    ubuntu_tag = next(t for t in tags if t["name"] == "ubuntu")
    assert "description" in ubuntu_tag
