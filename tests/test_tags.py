"""test_tags: 태그 시스템 테스트 모듈."""

import pytest
from httpx import AsyncClient


# ==========================================
# 헬퍼 함수
# ==========================================

async def create_post(cli: AsyncClient, title: str = "태그 테스트 제목", tags: list | None = None) -> int:
    """게시글 생성 헬퍼."""
    payload = {
        "title": title,
        "content": "테스트 내용입니다.",
        "category_id": 1,
    }
    if tags is not None:
        payload["tags"] = tags
    res = await cli.post("/v1/posts/", json=payload)
    assert res.status_code == 201, f"게시글 생성 실패: {res.text}"
    return res.json()["data"]["post_id"]


# ==========================================
# TAG-01: 게시글 생성 시 태그 포함 → 상세 응답에 tags 포함
# ==========================================

@pytest.mark.asyncio
async def test_tag_01_create_post_with_tags(client: AsyncClient, authorized_user):
    """게시글 생성 시 태그를 지정하면 상세 응답에 tags 필드가 포함된다."""
    cli, _, _ = authorized_user

    post_id = await create_post(cli, tags=["python", "fastapi"])

    detail_res = await cli.get(f"/v1/posts/{post_id}")
    assert detail_res.status_code == 200

    post = detail_res.json()["data"]["post"]
    assert "tags" in post
    tag_names = [t["name"] for t in post["tags"]]
    assert "python" in tag_names
    assert "fastapi" in tag_names


# ==========================================
# TAG-02: 태그 없이 게시글 생성 (하위 호환성)
# ==========================================

@pytest.mark.asyncio
async def test_tag_02_create_post_without_tags(client: AsyncClient, authorized_user):
    """태그 없이 게시글 생성 시 tags 필드는 빈 리스트이다."""
    cli, _, _ = authorized_user

    post_id = await create_post(cli)

    detail_res = await cli.get(f"/v1/posts/{post_id}")
    assert detail_res.status_code == 200

    post = detail_res.json()["data"]["post"]
    assert "tags" in post
    assert post["tags"] == []


# ==========================================
# TAG-03: 태그 최대 5개 초과 시 422
# ==========================================

@pytest.mark.asyncio
async def test_tag_03_max_5_tags(client: AsyncClient, authorized_user):
    """태그 6개 이상 지정 시 422 에러가 발생한다."""
    cli, _, _ = authorized_user

    res = await cli.post("/v1/posts/", json={
        "title": "태그 초과 테스트",
        "content": "내용",
        "category_id": 1,
        "tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6"],
    })
    assert res.status_code == 422


# ==========================================
# TAG-04: 게시글 수정 시 태그 업데이트
# ==========================================

@pytest.mark.asyncio
async def test_tag_04_update_post_tags(client: AsyncClient, authorized_user):
    """게시글 수정 시 tags를 제공하면 태그가 교체된다."""
    cli, _, _ = authorized_user

    post_id = await create_post(cli, tags=["python"])

    # 태그 교체
    update_res = await cli.patch(f"/v1/posts/{post_id}", json={"tags": ["django", "orm"]})
    assert update_res.status_code == 200

    detail_res = await cli.get(f"/v1/posts/{post_id}")
    post = detail_res.json()["data"]["post"]
    tag_names = [t["name"] for t in post["tags"]]
    assert "django" in tag_names
    assert "orm" in tag_names
    assert "python" not in tag_names


# ==========================================
# TAG-05: tags=null이면 태그 변경 없음 (PATCH 의미론)
# ==========================================

@pytest.mark.asyncio
async def test_tag_05_patch_null_no_change(client: AsyncClient, authorized_user):
    """PATCH 시 tags가 null이면 기존 태그가 유지된다."""
    cli, _, _ = authorized_user

    post_id = await create_post(cli, tags=["keep-tag"])

    # tags를 전달하지 않고 제목만 수정
    update_res = await cli.patch(f"/v1/posts/{post_id}", json={"title": "제목 변경만"})
    assert update_res.status_code == 200

    detail_res = await cli.get(f"/v1/posts/{post_id}")
    post = detail_res.json()["data"]["post"]
    tag_names = [t["name"] for t in post["tags"]]
    assert "keep-tag" in tag_names


# ==========================================
# TAG-06: 태그 자동완성 검색 API
# ==========================================

@pytest.mark.asyncio
async def test_tag_06_tag_search_autocomplete(client: AsyncClient, authorized_user):
    """태그 검색 API가 자동완성 결과를 반환한다."""
    cli, _, _ = authorized_user

    # 태그를 포함한 게시글 생성
    await create_post(cli, tags=["autocomplete-test"])

    res = await client.get("/v1/tags/?search=autocomplete")
    assert res.status_code == 200

    data = res.json()["data"]
    assert "tags" in data
    tag_names = [t["name"] for t in data["tags"]]
    assert "autocomplete-test" in tag_names


# ==========================================
# TAG-07: 태그로 게시글 목록 필터링
# ==========================================

@pytest.mark.asyncio
async def test_tag_07_filter_posts_by_tag(client: AsyncClient, authorized_user):
    """tag 쿼리 파라미터로 특정 태그가 포함된 게시글만 조회된다."""
    cli, _, _ = authorized_user

    await create_post(cli, title="태그 있는 게시글", tags=["filter-tag"])
    await create_post(cli, title="태그 없는 게시글")

    res = await client.get("/v1/posts/?tag=filter-tag")
    assert res.status_code == 200

    posts = res.json()["data"]["posts"]
    assert len(posts) >= 1
    # 모든 결과 게시글에 filter-tag가 포함되어야 함
    for post in posts:
        tag_names = [t["name"] for t in post["tags"]]
        assert "filter-tag" in tag_names


# ==========================================
# TAG-08: 태그 정규화 (대문자 → 소문자, 특수문자 제거)
# ==========================================

@pytest.mark.asyncio
async def test_tag_08_tag_normalization(client: AsyncClient, authorized_user):
    """태그 이름은 소문자로 정규화되고 허용되지 않는 문자는 제거된다."""
    cli, _, _ = authorized_user

    # 대문자 태그 입력 → 소문자로 저장
    post_id = await create_post(cli, tags=["Python", "FastAPI"])

    detail_res = await cli.get(f"/v1/posts/{post_id}")
    post = detail_res.json()["data"]["post"]
    tag_names = [t["name"] for t in post["tags"]]
    assert "python" in tag_names
    assert "fastapi" in tag_names


# ==========================================
# TAG-09: 게시글 목록에 tags 필드 포함
# ==========================================

@pytest.mark.asyncio
async def test_tag_09_post_list_includes_tags(client: AsyncClient, authorized_user):
    """게시글 목록 조회 시 각 게시글에 tags 필드가 포함된다."""
    cli, _, _ = authorized_user

    await create_post(cli, tags=["list-tag"])

    res = await client.get("/v1/posts/?limit=10")
    assert res.status_code == 200

    posts = res.json()["data"]["posts"]
    assert len(posts) >= 1
    # 모든 게시글에 tags 필드가 있어야 함
    for post in posts:
        assert "tags" in post
        assert isinstance(post["tags"], list)


# ==========================================
# TAG-10: 빈 문자열 태그는 거부됨
# ==========================================

@pytest.mark.asyncio
async def test_tag_10_empty_string_tag_rejected(client: AsyncClient, authorized_user):
    """빈 문자열이나 공백만 있는 태그는 422 에러가 발생한다."""
    cli, _, _ = authorized_user

    res = await cli.post("/v1/posts/", json={
        "title": "빈 태그 테스트",
        "content": "내용",
        "category_id": 1,
        "tags": ["   "],  # 공백만 있는 문자열 → 정규화 후 빈 문자열
    })
    assert res.status_code == 422


# ==========================================
# TAG-11: 30자 초과 태그는 거부됨
# ==========================================

@pytest.mark.asyncio
async def test_tag_11_tag_too_long_rejected(client: AsyncClient, authorized_user):
    """30자를 초과하는 태그는 422 에러가 발생한다."""
    cli, _, _ = authorized_user

    long_tag = "a" * 31  # 31자
    res = await cli.post("/v1/posts/", json={
        "title": "긴 태그 테스트",
        "content": "내용",
        "category_id": 1,
        "tags": [long_tag],
    })
    assert res.status_code == 422


# ==========================================
# TAG-12: 중복 태그는 자동 중복 제거됨
# ==========================================

@pytest.mark.asyncio
async def test_tag_12_duplicate_tags_deduplicated(client: AsyncClient, authorized_user):
    """같은 태그를 여러 번 지정해도 중복 제거 후 1개만 저장된다."""
    cli, _, _ = authorized_user

    post_id = await create_post(cli, tags=["dedup", "dedup", "dedup"])

    detail_res = await cli.get(f"/v1/posts/{post_id}")
    post = detail_res.json()["data"]["post"]
    tag_names = [t["name"] for t in post["tags"]]
    # 중복 제거 후 1개만
    assert tag_names.count("dedup") == 1
