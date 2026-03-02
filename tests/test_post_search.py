"""게시글 검색 및 정렬 기능 테스트."""

import pytest


@pytest.mark.asyncio
async def test_search_posts_by_title(authorized_user):
    """제목 키워드로 게시글을 검색합니다."""
    client, _, _ = authorized_user

    # 게시글 3개 생성 (제목이 서로 다름)
    await client.post("/v1/posts/", json={"title": "파이썬 입문 가이드", "content": "내용1", "category_id": 1})
    await client.post("/v1/posts/", json={"title": "자바스크립트 튜토리얼", "content": "내용2", "category_id": 1})
    await client.post("/v1/posts/", json={"title": "파이썬 고급 패턴", "content": "내용3", "category_id": 1})

    # "파이썬"으로 검색
    res = await client.get("/v1/posts/", params={"search": "파이썬"})
    assert res.status_code == 200

    data = res.json()["data"]
    posts = data["posts"]
    assert len(posts) == 2
    for post in posts:
        assert "파이썬" in post["title"]

    # 총 개수도 검색 결과에 맞아야 함
    assert data["pagination"]["total_count"] == 2


@pytest.mark.asyncio
async def test_search_posts_by_content(authorized_user):
    """내용 키워드로 게시글을 검색합니다."""
    client, _, _ = authorized_user

    await client.post(
        "/v1/posts/",
        json={"title": "일반 제목", "content": "데이터베이스 최적화 전략에 대해 알아봅시다", "category_id": 1},
    )
    await client.post(
        "/v1/posts/",
        json={"title": "다른 제목", "content": "프론트엔드 개발 이야기", "category_id": 1},
    )

    res = await client.get("/v1/posts/", params={"search": "데이터베이스"})
    assert res.status_code == 200

    posts = res.json()["data"]["posts"]
    assert len(posts) == 1


@pytest.mark.asyncio
async def test_search_empty_keyword_returns_all(authorized_user):
    """빈 검색어는 전체 게시글을 반환합니다."""
    client, _, _ = authorized_user

    await client.post("/v1/posts/", json={"title": "제목1", "content": "내용1", "category_id": 1})
    await client.post("/v1/posts/", json={"title": "제목2", "content": "내용2", "category_id": 1})

    # search 파라미터 없이 조회
    res = await client.get("/v1/posts/")
    assert res.status_code == 200
    all_posts = res.json()["data"]["posts"]

    # 빈 문자열로 검색해도 동일한 결과
    res_empty = await client.get("/v1/posts/", params={"search": ""})
    assert res_empty.status_code == 200
    empty_search_posts = res_empty.json()["data"]["posts"]

    assert len(all_posts) == len(empty_search_posts)


@pytest.mark.asyncio
async def test_search_no_results(authorized_user):
    """존재하지 않는 키워드 검색 시 빈 목록을 반환합니다."""
    client, _, _ = authorized_user

    await client.post("/v1/posts/", json={"title": "일반 게시글", "content": "일반 내용", "category_id": 1})

    res = await client.get("/v1/posts/", params={"search": "존재하지않는특수키워드xyz"})
    assert res.status_code == 200

    data = res.json()["data"]
    assert len(data["posts"]) == 0
    assert data["pagination"]["total_count"] == 0


@pytest.mark.asyncio
async def test_sort_by_latest(authorized_user):
    """최신순 정렬을 확인합니다."""
    client, _, _ = authorized_user

    res1 = await client.post("/v1/posts/", json={"title": "첫번째 글", "content": "내용", "category_id": 1})
    res2 = await client.post("/v1/posts/", json={"title": "두번째 글", "content": "내용", "category_id": 1})

    post_id_1 = res1.json()["data"]["post_id"]
    post_id_2 = res2.json()["data"]["post_id"]

    res = await client.get("/v1/posts/", params={"sort": "latest"})
    assert res.status_code == 200

    posts = res.json()["data"]["posts"]
    assert len(posts) >= 2
    # 최신 글이 먼저 와야 함
    assert posts[0]["post_id"] == post_id_2
    assert posts[1]["post_id"] == post_id_1


@pytest.mark.asyncio
async def test_sort_by_views(authorized_user):
    """조회수순 정렬을 확인합니다."""
    client, _, _ = authorized_user

    await client.post("/v1/posts/", json={"title": "조회수 적은 글", "content": "내용", "category_id": 1})
    res2 = await client.post("/v1/posts/", json={"title": "조회수 많은 글", "content": "내용", "category_id": 1})

    post_id_2 = res2.json()["data"]["post_id"]

    # post_id_2를 조회하여 조회수 증가
    await client.get(f"/v1/posts/{post_id_2}")

    res = await client.get("/v1/posts/", params={"sort": "views"})
    assert res.status_code == 200

    posts = res.json()["data"]["posts"]
    assert len(posts) >= 2
    # 조회수가 많은 글이 먼저
    assert posts[0]["post_id"] == post_id_2


@pytest.mark.asyncio
async def test_sort_invalid_fallback_to_latest(authorized_user):
    """유효하지 않은 정렬 옵션은 기본값(latest)으로 대체됩니다."""
    client, _, _ = authorized_user

    await client.post("/v1/posts/", json={"title": "테스트 글", "content": "내용", "category_id": 1})

    res = await client.get("/v1/posts/", params={"sort": "invalid_option"})
    assert res.status_code == 200
    assert len(res.json()["data"]["posts"]) >= 1


@pytest.mark.asyncio
async def test_search_with_sort(authorized_user):
    """검색과 정렬을 동시에 사용합니다."""
    client, _, _ = authorized_user

    res1 = await client.post(
        "/v1/posts/", json={"title": "FastAPI 기초", "content": "기초 내용", "category_id": 1}
    )
    res2 = await client.post(
        "/v1/posts/", json={"title": "FastAPI 심화", "content": "심화 내용", "category_id": 1}
    )
    await client.post(
        "/v1/posts/", json={"title": "Django 입문", "content": "다른 프레임워크", "category_id": 1}
    )

    post_id_1 = res1.json()["data"]["post_id"]
    post_id_2 = res2.json()["data"]["post_id"]

    # "FastAPI" 검색 + 최신순 정렬
    res = await client.get("/v1/posts/", params={"search": "FastAPI", "sort": "latest"})
    assert res.status_code == 200

    data = res.json()["data"]
    posts = data["posts"]
    assert len(posts) == 2
    assert data["pagination"]["total_count"] == 2
    # 최신순이므로 심화가 먼저
    assert posts[0]["post_id"] == post_id_2
    assert posts[1]["post_id"] == post_id_1


@pytest.mark.asyncio
async def test_search_whitespace_only_returns_all(authorized_user):
    """공백만 있는 검색어는 전체 게시글을 반환합니다."""
    client, _, _ = authorized_user

    await client.post("/v1/posts/", json={"title": "테스트 게시글", "content": "내용", "category_id": 1})

    res = await client.get("/v1/posts/", params={"search": "   "})
    assert res.status_code == 200
    posts = res.json()["data"]["posts"]
    assert len(posts) >= 1


@pytest.mark.asyncio
async def test_search_fulltext_special_chars(authorized_user):
    """FULLTEXT 특수문자가 포함된 검색어가 에러 없이 동작합니다."""
    client, _, _ = authorized_user

    await client.post("/v1/posts/", json={"title": "특수문자 테스트", "content": "내용 내용", "category_id": 1})

    # 특수문자 포함 검색어
    for query in ['테스트+검색', '"테스트"', 'C++', '~테스트', '@테스트']:
        res = await client.get("/v1/posts/", params={"search": query})
        assert res.status_code == 200, f"검색어 '{query}'에서 에러 발생"
