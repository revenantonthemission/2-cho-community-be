"""Wiki 도메인 — 테스트 픽스처."""

import pytest
from httpx import AsyncClient


@pytest.fixture
def wiki_slug():
    """테스트용 위키 슬러그를 반환한다."""
    return "test-wiki-page"


async def create_wiki_page(
    client: AsyncClient,
    headers: dict,
    slug: str = "test-wiki-page",
    title: str = "테스트 위키 페이지",
    content: str = "이것은 테스트용 위키 페이지 내용입니다. 최소 길이를 충족합니다.",
    tags: list[str] | None = None,
) -> str:
    """위키 페이지를 생성하고 슬러그를 반환하는 헬퍼.

    Returns:
        생성된 위키 페이지의 슬러그.
    """
    payload = {
        "title": title,
        "slug": slug,
        "content": content,
        "tags": tags or [],
    }
    res = await client.post(
        "/v1/wiki/",
        json=payload,
        headers=headers,
        follow_redirects=True,
    )
    assert res.status_code == 201, f"위키 페이지 생성 실패: {res.status_code}, {res.text}"
    return slug


async def create_wiki_page_with_revisions(
    client: AsyncClient,
    headers: dict,
    slug: str = "test-wiki-page",
) -> str:
    """위키 페이지를 생성하고 2회 수정하여 총 3개 리비전을 만드는 헬퍼.

    Returns:
        생성된 위키 페이지의 슬러그.
    """
    # 리비전 1: 초기 생성
    await create_wiki_page(
        client,
        headers,
        slug=slug,
        title="초기 제목",
        content="초기 내용입니다. 최소 길이를 충족하기 위한 텍스트입니다.",
    )

    # 리비전 2: 첫 번째 수정
    res2 = await client.put(
        f"/v1/wiki/{slug}",
        json={
            "content": "첫 번째 수정된 내용입니다. 변경 사항을 반영합니다.",
            "edit_summary": "첫 번째 수정",
        },
        headers=headers,
        follow_redirects=True,
    )
    assert res2.status_code == 200, f"첫 번째 수정 실패: {res2.status_code}, {res2.text}"

    # 리비전 3: 두 번째 수정
    res3 = await client.put(
        f"/v1/wiki/{slug}",
        json={
            "content": "두 번째 수정된 내용입니다. 추가 변경 사항을 반영합니다.",
            "edit_summary": "두 번째 수정",
        },
        headers=headers,
        follow_redirects=True,
    )
    assert res3.status_code == 200, f"두 번째 수정 실패: {res3.status_code}, {res3.text}"

    return slug
