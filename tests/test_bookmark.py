"""test_bookmark: 북마크 기능 테스트."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_bookmark_add(client: AsyncClient, authorized_user):
    """북마크 추가 (201)."""
    cli, _, _ = authorized_user

    # 게시글 생성
    post_res = await cli.post(
        "/v1/posts/",
        json={"title": "북마크 테스트", "content": "내용입니다", "category_id": 1},
    )
    assert post_res.status_code == 201
    post_id = post_res.json()["data"]["post_id"]

    # 북마크 추가
    res = await cli.post(f"/v1/posts/{post_id}/bookmark")
    assert res.status_code == 201
    assert res.json()["code"] == "BOOKMARK_ADDED"
    assert res.json()["data"]["bookmarks_count"] == 1


@pytest.mark.asyncio
async def test_bookmark_duplicate(client: AsyncClient, authorized_user):
    """중복 북마크 (409)."""
    cli, _, _ = authorized_user

    post_res = await cli.post(
        "/v1/posts/",
        json={"title": "중복 북마크 테스트", "content": "내용입니다", "category_id": 1},
    )
    post_id = post_res.json()["data"]["post_id"]

    await cli.post(f"/v1/posts/{post_id}/bookmark")
    res = await cli.post(f"/v1/posts/{post_id}/bookmark")
    assert res.status_code == 409
    assert res.json()["detail"]["error"] == "already_bookmarked"


@pytest.mark.asyncio
async def test_bookmark_remove(client: AsyncClient, authorized_user):
    """북마크 해제 (200)."""
    cli, _, _ = authorized_user

    post_res = await cli.post(
        "/v1/posts/",
        json={"title": "해제 테스트", "content": "내용입니다", "category_id": 1},
    )
    post_id = post_res.json()["data"]["post_id"]

    await cli.post(f"/v1/posts/{post_id}/bookmark")
    res = await cli.delete(f"/v1/posts/{post_id}/bookmark")
    assert res.status_code == 200
    assert res.json()["code"] == "BOOKMARK_REMOVED"
    assert res.json()["data"]["bookmarks_count"] == 0


@pytest.mark.asyncio
async def test_bookmark_remove_not_bookmarked(client: AsyncClient, authorized_user):
    """북마크하지 않은 게시글 해제 시도 (404)."""
    cli, _, _ = authorized_user

    post_res = await cli.post(
        "/v1/posts/",
        json={"title": "미북마크 해제", "content": "내용입니다", "category_id": 1},
    )
    post_id = post_res.json()["data"]["post_id"]

    res = await cli.delete(f"/v1/posts/{post_id}/bookmark")
    assert res.status_code == 404
    assert res.json()["detail"]["error"] == "bookmark_not_found"


@pytest.mark.asyncio
async def test_bookmark_nonexistent_post(client: AsyncClient, authorized_user):
    """존재하지 않는 게시글 북마크 (404)."""
    cli, _, _ = authorized_user

    res = await cli.post("/v1/posts/99999/bookmark")
    assert res.status_code == 404
    assert res.json()["detail"]["error"] == "post_not_found"


@pytest.mark.asyncio
async def test_bookmark_unauthorized(client: AsyncClient):
    """미인증 사용자 북마크 (401)."""
    res = await client.post("/v1/posts/1/bookmark")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_bookmark_unverified_email(client: AsyncClient, unverified_user, authorized_user):
    """이메일 미인증 사용자 북마크 (403)."""
    unverified_cli, _, _ = unverified_user
    cli, _, _ = authorized_user

    post_res = await cli.post(
        "/v1/posts/",
        json={"title": "미인증 북마크", "content": "내용입니다", "category_id": 1},
    )
    post_id = post_res.json()["data"]["post_id"]

    res = await unverified_cli.post(f"/v1/posts/{post_id}/bookmark")
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_my_bookmarks_list(client: AsyncClient, authorized_user):
    """내 북마크 목록 조회 + 페이지네이션."""
    cli, _, _ = authorized_user

    # 게시글 3개 생성 & 북마크
    post_ids = []
    for i in range(3):
        post_res = await cli.post(
            "/v1/posts/",
            json={"title": f"북마크 목록 {i}", "content": "내용입니다", "category_id": 1},
        )
        pid = post_res.json()["data"]["post_id"]
        post_ids.append(pid)
        await cli.post(f"/v1/posts/{pid}/bookmark")

    # 전체 조회
    res = await cli.get("/v1/users/me/bookmarks")
    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data["posts"]) == 3
    assert data["pagination"]["total_count"] == 3

    # 페이지네이션
    res2 = await cli.get("/v1/users/me/bookmarks?offset=0&limit=2")
    assert res2.status_code == 200
    data2 = res2.json()["data"]
    assert len(data2["posts"]) == 2
    assert data2["pagination"]["has_more"] is True


@pytest.mark.asyncio
async def test_post_detail_bookmark_count(client: AsyncClient, authorized_user):
    """게시글 상세에서 bookmarks_count 확인."""
    cli, _, _ = authorized_user

    post_res = await cli.post(
        "/v1/posts/",
        json={"title": "상세 북마크", "content": "내용입니다", "category_id": 1},
    )
    post_id = post_res.json()["data"]["post_id"]

    # 북마크 전
    detail_res = await cli.get(f"/v1/posts/{post_id}")
    assert detail_res.status_code == 200
    assert detail_res.json()["data"]["post"]["bookmarks_count"] == 0

    # 북마크 후
    await cli.post(f"/v1/posts/{post_id}/bookmark")
    detail_res2 = await cli.get(f"/v1/posts/{post_id}")
    assert detail_res2.json()["data"]["post"]["bookmarks_count"] == 1

    # is_bookmarked 확인
    assert detail_res2.json()["data"]["post"]["is_bookmarked"] is True
