"""Content 도메인 — 태그 검색/생성/상세 조회 통합 테스트."""

import pytest
from httpx import AsyncClient

from tests.conftest import create_test_post, create_verified_user

# ---------------------------------------------------------------------------
# 태그 검색/자동완성 (GET /v1/tags/?search=...)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_tags_returns_matching_tags(client: AsyncClient, fake):
    """검색어와 일치하는 태그가 post_count와 함께 반환된다."""
    user = await create_verified_user(client, fake)
    await create_test_post(client, user["headers"], tags=["python"])

    res = await client.get("/v1/tags/", params={"search": "python"})

    assert res.status_code == 200
    tags = res.json()["data"]["tags"]
    assert len(tags) >= 1
    python_tag = next(t for t in tags if t["name"] == "python")
    assert python_tag["post_count"] >= 1


@pytest.mark.asyncio
async def test_search_tags_empty_query_returns_empty_list(client: AsyncClient, fake):
    """빈 검색어는 빈 목록을 반환한다."""
    user = await create_verified_user(client, fake)
    await create_test_post(client, user["headers"], tags=["python"])

    res = await client.get("/v1/tags/", params={"search": ""})

    assert res.status_code == 200
    tags = res.json()["data"]["tags"]
    assert tags == []


@pytest.mark.asyncio
async def test_search_tags_no_match_returns_empty_list(client: AsyncClient, fake):
    """일치하는 태그가 없으면 빈 목록을 반환한다."""
    user = await create_verified_user(client, fake)
    await create_test_post(client, user["headers"], tags=["python"])

    res = await client.get("/v1/tags/", params={"search": "zzz-no-match-xyz"})

    assert res.status_code == 200
    tags = res.json()["data"]["tags"]
    assert tags == []


# ---------------------------------------------------------------------------
# 태그 생성 (게시글 생성 시 자동 생성)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_creating_post_with_tags_auto_creates_tags(client: AsyncClient, fake):
    """게시글 생성 시 태그가 자동으로 생성된다."""
    user = await create_verified_user(client, fake)
    await create_test_post(client, user["headers"], tags=["newtag"])

    # 태그 검색으로 생성 확인
    res = await client.get("/v1/tags/", params={"search": "newtag"})

    assert res.status_code == 200
    tags = res.json()["data"]["tags"]
    assert len(tags) == 1
    assert tags[0]["name"] == "newtag"
    assert tags[0]["post_count"] == 1


@pytest.mark.asyncio
async def test_multiple_posts_with_same_tag_increments_count(client: AsyncClient, fake):
    """같은 태그로 여러 게시글을 생성하면 post_count가 증가한다."""
    user = await create_verified_user(client, fake)
    await create_test_post(client, user["headers"], tags=["linux"], title="게시글 1")
    await create_test_post(client, user["headers"], tags=["linux"], title="게시글 2")
    await create_test_post(client, user["headers"], tags=["linux"], title="게시글 3")

    res = await client.get("/v1/tags/", params={"search": "linux"})

    assert res.status_code == 200
    tags = res.json()["data"]["tags"]
    linux_tag = next(t for t in tags if t["name"] == "linux")
    assert linux_tag["post_count"] == 3


@pytest.mark.asyncio
async def test_tag_names_are_normalized(client: AsyncClient, fake):
    """태그 이름은 소문자로 정규화되어 저장된다."""
    user = await create_verified_user(client, fake)
    await create_test_post(client, user["headers"], tags=["Python"])

    # 소문자로 정규화되었는지 확인
    res = await client.get("/v1/tags/", params={"search": "python"})

    assert res.status_code == 200
    tags = res.json()["data"]["tags"]
    assert len(tags) >= 1
    assert tags[0]["name"] == "python"


# ---------------------------------------------------------------------------
# 태그 상세 조회 (GET /v1/tags/{tag_name}/)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_tag_detail_returns_tag_with_posts(client: AsyncClient, fake):
    """태그 상세 조회 시 post_count가 포함된 태그 정보를 반환한다."""
    user = await create_verified_user(client, fake)
    await create_test_post(client, user["headers"], tags=["ubuntu"])

    res = await client.get("/v1/tags/ubuntu")

    assert res.status_code == 200
    data = res.json()["data"]["tag"]
    assert data["name"] == "ubuntu"
    assert data["post_count"] >= 1
    assert "wiki_count" in data


@pytest.mark.asyncio
async def test_get_tag_detail_case_insensitive(client: AsyncClient, fake):
    """태그 상세 조회는 대소문자를 구분하지 않는다 (정규화 후 조회)."""
    user = await create_verified_user(client, fake)
    await create_test_post(client, user["headers"], tags=["FastAPI"])

    # 대문자로 조회해도 정규화되어 찾아야 함
    res = await client.get("/v1/tags/FASTAPI")

    assert res.status_code == 200
    data = res.json()["data"]["tag"]
    assert data["name"] == "fastapi"


@pytest.mark.asyncio
async def test_get_tag_detail_nonexistent_returns_404(client: AsyncClient, fake):
    """존재하지 않는 태그를 조회하면 404를 반환한다."""
    res = await client.get("/v1/tags/nonexistent-tag-xyz")

    assert res.status_code == 404
