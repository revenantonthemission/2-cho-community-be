"""위키 페이지 API 통합 테스트."""

import pytest
from faker import Faker
from httpx import AsyncClient

from tests.conftest import create_verified_user

# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------


async def _create_wiki_page(
    client: AsyncClient,
    token: str,
    slug: str = "test-page",
    title: str = "테스트 페이지",
    tags: list[str] | None = None,
) -> dict:
    """위키 페이지를 생성하고 응답 전체를 반환하는 헬퍼."""
    data = {
        "title": title,
        "slug": slug,
        "content": "이것은 테스트 위키 페이지입니다. 충분히 긴 내용을 작성합니다.",
        "tags": tags or [],
    }
    resp = await client.post(
        "/v1/wiki/",
        json=data,
        headers={"Authorization": f"Bearer {token}"},
    )
    return resp


# ===========================================================================
# 1. 위키 페이지 생성 (POST /v1/wiki/)
# ===========================================================================


@pytest.mark.asyncio
async def test_create_wiki_page_success(client: AsyncClient, fake: Faker):
    """인증된 사용자가 위키 페이지를 생성할 수 있다."""
    user = await create_verified_user(client, fake)
    resp = await _create_wiki_page(client, user["token"])
    assert resp.status_code == 201
    body = resp.json()["data"]
    assert body["slug"] == "test-page"
    assert "wiki_page_id" in body


@pytest.mark.asyncio
async def test_create_wiki_page_unauthenticated(client: AsyncClient):
    """미인증 사용자는 위키 페이지를 생성할 수 없다 (401)."""
    data = {
        "title": "인증 없는 페이지",
        "slug": "no-auth-page",
        "content": "이것은 인증 없이 생성하려는 위키 페이지입니다.",
        "tags": [],
    }
    resp = await client.post("/v1/wiki/", json=data)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_wiki_page_duplicate_slug(client: AsyncClient, fake: Faker):
    """중복 슬러그로 생성 시 400 (SLUG_DUPLICATE) 오류가 발생한다."""
    user = await create_verified_user(client, fake)
    resp1 = await _create_wiki_page(client, user["token"], slug="dup-slug")
    assert resp1.status_code == 201

    resp2 = await _create_wiki_page(client, user["token"], slug="dup-slug")
    assert resp2.status_code == 400
    assert "SLUG_DUPLICATE" in resp2.text


@pytest.mark.asyncio
async def test_create_wiki_page_invalid_slug(client: AsyncClient, fake: Faker):
    """잘못된 슬러그 형식 시 422 오류가 발생한다."""
    user = await create_verified_user(client, fake)
    # 대문자와 밑줄 포함 — 슬러그 패턴 위반
    resp = await _create_wiki_page(client, user["token"], slug="Invalid_Slug!")
    assert resp.status_code == 422


# ===========================================================================
# 2. 위키 페이지 목록 (GET /v1/wiki/)
# ===========================================================================


@pytest.mark.asyncio
async def test_list_wiki_pages_empty(client: AsyncClient):
    """페이지가 없으면 빈 목록을 반환한다."""
    resp = await client.get("/v1/wiki/")
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["wiki_pages"] == []
    assert body["pagination"]["total_count"] == 0


@pytest.mark.asyncio
async def test_list_wiki_pages_after_creation(client: AsyncClient, fake: Faker):
    """페이지 생성 후 목록에 표시된다."""
    user = await create_verified_user(client, fake)
    await _create_wiki_page(client, user["token"], slug="listed-page")

    resp = await client.get("/v1/wiki/")
    assert resp.status_code == 200
    pages = resp.json()["data"]["wiki_pages"]
    assert len(pages) == 1


@pytest.mark.asyncio
async def test_list_wiki_pages_pagination(client: AsyncClient, fake: Faker):
    """offset과 limit으로 페이지네이션이 동작한다."""
    user = await create_verified_user(client, fake)
    for i in range(3):
        r = await _create_wiki_page(
            client,
            user["token"],
            slug=f"page-{i}",
            title=f"페이지 {i}",
        )
        assert r.status_code == 201

    # limit=2이면 첫 2개만 반환, has_more=True
    resp = await client.get("/v1/wiki/", params={"offset": 0, "limit": 2})
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert len(body["wiki_pages"]) == 2
    assert body["pagination"]["has_more"] is True

    # offset=2이면 나머지 1개만 반환, has_more=False
    resp2 = await client.get("/v1/wiki/", params={"offset": 2, "limit": 2})
    assert resp2.status_code == 200
    body2 = resp2.json()["data"]
    assert len(body2["wiki_pages"]) == 1
    assert body2["pagination"]["has_more"] is False


@pytest.mark.asyncio
async def test_list_wiki_pages_tag_filter(client: AsyncClient, fake: Faker):
    """태그로 필터링이 동작한다."""
    user = await create_verified_user(client, fake)
    await _create_wiki_page(
        client,
        user["token"],
        slug="tagged-page",
        tags=["ubuntu"],
    )
    await _create_wiki_page(
        client,
        user["token"],
        slug="other-page",
        tags=["fedora"],
    )

    resp = await client.get("/v1/wiki/", params={"tag": "ubuntu"})
    assert resp.status_code == 200
    pages = resp.json()["data"]["wiki_pages"]
    assert len(pages) == 1


# ===========================================================================
# 3. 위키 페이지 상세 (GET /v1/wiki/{slug})
# ===========================================================================


@pytest.mark.asyncio
async def test_get_wiki_page_success(client: AsyncClient, fake: Faker):
    """존재하는 슬러그로 위키 페이지를 조회할 수 있다."""
    user = await create_verified_user(client, fake)
    await _create_wiki_page(client, user["token"], slug="detail-page")

    resp = await client.get("/v1/wiki/detail-page")
    assert resp.status_code == 200
    page = resp.json()["data"]["wiki_page"]
    assert page["slug"] == "detail-page"
    assert page["title"] == "테스트 페이지"


@pytest.mark.asyncio
async def test_get_wiki_page_increments_views(client: AsyncClient, fake: Faker):
    """위키 페이지를 조회하면 조회수가 증가한다."""
    user = await create_verified_user(client, fake)
    await _create_wiki_page(client, user["token"], slug="views-page")

    resp1 = await client.get("/v1/wiki/views-page")
    views1 = resp1.json()["data"]["wiki_page"]["views_count"]

    resp2 = await client.get("/v1/wiki/views-page")
    views2 = resp2.json()["data"]["wiki_page"]["views_count"]

    assert views2 == views1 + 1


@pytest.mark.asyncio
async def test_get_wiki_page_not_found(client: AsyncClient):
    """존재하지 않는 슬러그로 조회 시 404를 반환한다."""
    resp = await client.get("/v1/wiki/nonexistent-slug")
    assert resp.status_code == 404


# ===========================================================================
# 4. 위키 페이지 편집 (PUT /v1/wiki/{slug})
# ===========================================================================


@pytest.mark.asyncio
async def test_update_wiki_page_by_author(client: AsyncClient, fake: Faker):
    """작성자가 위키 페이지를 수정할 수 있다."""
    user = await create_verified_user(client, fake)
    await _create_wiki_page(client, user["token"], slug="edit-page")

    resp = await client.put(
        "/v1/wiki/edit-page",
        json={"title": "수정된 제목"},
        headers=user["headers"],
    )
    assert resp.status_code == 200
    page = resp.json()["data"]["wiki_page"]
    assert page["title"] == "수정된 제목"


@pytest.mark.asyncio
async def test_update_wiki_page_by_another_user(client: AsyncClient, fake: Faker):
    """다른 사용자도 위키 페이지를 수정할 수 있다 (위키 특성: 누구나 편집 가능)."""
    author = await create_verified_user(client, fake)
    await _create_wiki_page(client, author["token"], slug="shared-page")

    editor = await create_verified_user(client, fake)
    resp = await client.put(
        "/v1/wiki/shared-page",
        json={"title": "다른 사용자가 수정한 제목"},
        headers=editor["headers"],
    )
    assert resp.status_code == 200
    page = resp.json()["data"]["wiki_page"]
    assert page["title"] == "다른 사용자가 수정한 제목"


@pytest.mark.asyncio
async def test_update_wiki_page_last_edited_by(client: AsyncClient, fake: Faker):
    """편집 후 last_edited_by가 편집자 정보로 업데이트된다."""
    author = await create_verified_user(client, fake)
    await _create_wiki_page(client, author["token"], slug="edited-page")

    editor = await create_verified_user(client, fake)
    resp = await client.put(
        "/v1/wiki/edited-page",
        json={"content": "편집자가 수정한 충분히 긴 내용입니다."},
        headers=editor["headers"],
    )
    assert resp.status_code == 200
    page = resp.json()["data"]["wiki_page"]
    assert page["last_edited_by"] == editor["user_id"]


@pytest.mark.asyncio
async def test_update_wiki_page_unauthenticated(client: AsyncClient, fake: Faker):
    """미인증 사용자는 위키 페이지를 수정할 수 없다 (401)."""
    user = await create_verified_user(client, fake)
    await _create_wiki_page(client, user["token"], slug="no-edit-page")

    resp = await client.put(
        "/v1/wiki/no-edit-page",
        json={"title": "수정 시도"},
    )
    assert resp.status_code == 401


# ===========================================================================
# 5. 위키 페이지 삭제 (DELETE /v1/wiki/{slug})
# ===========================================================================


@pytest.mark.asyncio
async def test_delete_wiki_page_by_author(client: AsyncClient, fake: Faker):
    """작성자가 위키 페이지를 삭제할 수 있다."""
    user = await create_verified_user(client, fake)
    await _create_wiki_page(client, user["token"], slug="del-page")

    resp = await client.delete(
        "/v1/wiki/del-page",
        headers=user["headers"],
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_delete_wiki_page_by_other_user_forbidden(
    client: AsyncClient,
    fake: Faker,
):
    """작성자가 아닌 사용자는 삭제할 수 없다 (403)."""
    author = await create_verified_user(client, fake)
    await _create_wiki_page(client, author["token"], slug="protected-page")

    other = await create_verified_user(client, fake)
    resp = await client.delete(
        "/v1/wiki/protected-page",
        headers=other["headers"],
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_wiki_page_hidden_from_list(client: AsyncClient, fake: Faker):
    """삭제한 위키 페이지는 목록에서 더 이상 표시되지 않는다."""
    user = await create_verified_user(client, fake)
    await _create_wiki_page(client, user["token"], slug="gone-page")

    # 삭제 전 목록에 존재
    list_before = await client.get("/v1/wiki/")
    assert len(list_before.json()["data"]["wiki_pages"]) == 1

    # 삭제
    await client.delete("/v1/wiki/gone-page", headers=user["headers"])

    # 삭제 후 목록에서 사라짐
    list_after = await client.get("/v1/wiki/")
    assert len(list_after.json()["data"]["wiki_pages"]) == 0
