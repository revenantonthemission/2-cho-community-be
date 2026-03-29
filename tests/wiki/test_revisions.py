"""Wiki 도메인 — 리비전 API 통합 테스트."""

import pytest
from httpx import AsyncClient

from tests.conftest import create_verified_user
from tests.wiki.conftest import (
    create_wiki_page,
    create_wiki_page_with_revisions,
)

# ---------------------------------------------------------------------------
# 위키 생성 시 초기 리비전 생성 확인
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_wiki_creates_initial_revision(client: AsyncClient, fake):
    """위키 페이지 생성 시 revision_number=1인 초기 리비전이 생성된다."""
    user = await create_verified_user(client, fake)
    slug = await create_wiki_page(client, user["headers"])

    res = await client.get(
        f"/v1/wiki/{slug}/history",
        follow_redirects=True,
    )

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["total"] == 1
    revisions = data["revisions"]
    assert len(revisions) == 1
    assert revisions[0]["revision_number"] == 1


# ---------------------------------------------------------------------------
# 위키 수정 시 리비전 생성 확인
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_wiki_creates_revision(client: AsyncClient, fake):
    """위키 페이지 수정 시 새 리비전이 생성된다."""
    user = await create_verified_user(client, fake)
    slug = await create_wiki_page(client, user["headers"])

    # 수정
    update_res = await client.put(
        f"/v1/wiki/{slug}",
        json={
            "content": "수정된 내용입니다. 변경 사항을 테스트합니다.",
            "edit_summary": "내용 수정 테스트",
        },
        headers=user["headers"],
        follow_redirects=True,
    )
    assert update_res.status_code == 200

    # 히스토리 확인
    res = await client.get(
        f"/v1/wiki/{slug}/history",
        follow_redirects=True,
    )

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["total"] >= 2


# ---------------------------------------------------------------------------
# 리비전 상세 조회
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_revision_detail(client: AsyncClient, fake):
    """특정 리비전 번호로 리비전 상세 정보를 조회할 수 있다."""
    user = await create_verified_user(client, fake)
    slug = await create_wiki_page_with_revisions(client, user["headers"])

    res = await client.get(
        f"/v1/wiki/{slug}/revisions/1",
        follow_redirects=True,
    )

    assert res.status_code == 200
    revision = res.json()["data"]["revision"]
    assert revision["revision_number"] == 1
    assert "title" in revision
    assert "content" in revision
    assert "edit_summary" in revision
    # 편집자 정보는 editor 객체 안에 포함
    assert "editor" in revision
    assert "nickname" in revision["editor"]


# ---------------------------------------------------------------------------
# 두 리비전 간 diff 조회
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_diff_between_revisions(client: AsyncClient, fake):
    """두 리비전 간 diff를 조회하면 변경 내역이 반환된다."""
    user = await create_verified_user(client, fake)
    slug = await create_wiki_page_with_revisions(client, user["headers"])

    res = await client.get(
        f"/v1/wiki/{slug}/diff",
        params={"from": 1, "to": 2},
        follow_redirects=True,
    )

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["from_revision"] == 1
    assert data["to_revision"] == 2
    assert "changes" in data
    assert isinstance(data["changes"], list)


# ---------------------------------------------------------------------------
# 잘못된 리비전 순서 (from >= to)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_diff_invalid_order(client: AsyncClient, fake):
    """from >= to인 diff 요청은 400을 반환한다."""
    user = await create_verified_user(client, fake)
    slug = await create_wiki_page_with_revisions(client, user["headers"])

    res = await client.get(
        f"/v1/wiki/{slug}/diff",
        params={"from": 2, "to": 1},
        follow_redirects=True,
    )

    assert res.status_code == 400


# ---------------------------------------------------------------------------
# 롤백
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rollback(client: AsyncClient, fake):
    """리비전 1로 롤백하면 현재 페이지 내용이 리비전 1과 동일해진다."""
    user = await create_verified_user(client, fake)
    slug = await create_wiki_page_with_revisions(client, user["headers"])

    # 리비전 1의 내용 확인
    rev1_res = await client.get(
        f"/v1/wiki/{slug}/revisions/1",
        follow_redirects=True,
    )
    assert rev1_res.status_code == 200
    rev1_content = rev1_res.json()["data"]["revision"]["content"]

    # 리비전 1로 롤백
    rollback_res = await client.post(
        f"/v1/wiki/{slug}/rollback/1",
        headers=user["headers"],
        follow_redirects=True,
    )
    assert rollback_res.status_code == 200

    # 현재 페이지 내용이 리비전 1과 동일한지 확인
    page_res = await client.get(
        f"/v1/wiki/{slug}",
        follow_redirects=True,
    )
    assert page_res.status_code == 200
    current_content = page_res.json()["data"]["wiki_page"]["content"]
    assert current_content == rev1_content


# ---------------------------------------------------------------------------
# edit_summary 누락 시 422 검증
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_edit_summary_required_on_update(client: AsyncClient, fake):
    """위키 수정 시 edit_summary가 없으면 422 검증 오류를 반환한다."""
    user = await create_verified_user(client, fake)
    slug = await create_wiki_page(client, user["headers"])

    res = await client.put(
        f"/v1/wiki/{slug}",
        json={"content": "수정된 내용입니다. edit_summary 없이 요청합니다."},
        headers=user["headers"],
        follow_redirects=True,
    )

    assert res.status_code == 422
