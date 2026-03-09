"""팔로잉 피드 API 테스트.

GET /v1/posts?following=true 쿼리 파라미터로
팔로우한 사용자의 게시글만 조회하는 기능을 검증합니다.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from main import app
from database.connection import get_connection


# ── 헬퍼 함수 ──


async def create_verified_user(client: AsyncClient, email: str, nickname: str) -> tuple:
    """회원가입 + 이메일 인증 + 로그인 후 인증된 클라이언트를 반환합니다."""
    payload = {"email": email, "password": "Password123!", "nickname": nickname}
    res = await client.post("/v1/users/", data=payload)
    assert res.status_code == 201

    # 이메일 인증 완료
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE user SET email_verified = 1 WHERE email = %s",
                (email,),
            )

    # 로그인
    login_res = await client.post(
        "/v1/auth/session",
        json={"email": email, "password": "Password123!"},
    )
    assert login_res.status_code == 200

    login_data = login_res.json()
    access_token = login_data["data"]["access_token"]
    user_info = login_data["data"]["user"]

    transport = ASGITransport(app=app)
    auth_client = AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {access_token}"},
        cookies=login_res.cookies,
    )

    return auth_client, user_info


async def create_post(cli: AsyncClient, title: str, category_id: int = 1) -> int:
    """게시글을 생성하고 post_id를 반환합니다."""
    res = await cli.post(
        "/v1/posts/",
        json={"title": title, "content": f"내용: {title}", "category_id": category_id},
    )
    assert res.status_code == 201
    return res.json()["data"]["post_id"]


# ── 테스트 ──


@pytest.mark.asyncio
async def test_following_feed_returns_only_followed_users_posts(client):
    """팔로우한 사용자의 게시글만 반환되는지 확인합니다."""
    # 3명의 사용자 생성
    cli_a, user_a = await create_verified_user(client, "usera@test.com", "useraaaaa")
    cli_b, user_b = await create_verified_user(client, "userb@test.com", "userbbbbb")
    cli_c, user_c = await create_verified_user(client, "userc@test.com", "userccccc")

    async with cli_a, cli_b, cli_c:
        # B와 C가 각각 게시글 작성
        post_b = await create_post(cli_b, "B의 게시글")
        post_c = await create_post(cli_c, "C의 게시글")

        # A가 B만 팔로우
        res = await cli_a.post(f"/v1/users/{user_b['user_id']}/follow")
        assert res.status_code == 201

        # A가 팔로잉 피드 조회
        res = await cli_a.get("/v1/posts/", params={"following": "true"})
        assert res.status_code == 200

        posts = res.json()["data"]["posts"]
        post_ids = [p["post_id"] for p in posts]

        # B의 게시글만 포함, C의 게시글은 미포함
        assert post_b in post_ids
        assert post_c not in post_ids


@pytest.mark.asyncio
async def test_following_feed_empty_when_no_following(client):
    """팔로잉 0명이면 빈 배열을 반환합니다."""
    cli_a, user_a = await create_verified_user(client, "lonely@test.com", "lonelyyyy")

    async with cli_a:
        # 다른 사용자가 게시글 작성
        cli_b, user_b = await create_verified_user(client, "other@test.com", "otheruser")
        async with cli_b:
            await create_post(cli_b, "다른 사용자의 글")

        # 팔로잉 0명인 상태로 피드 조회
        res = await cli_a.get("/v1/posts/", params={"following": "true"})
        assert res.status_code == 200

        data = res.json()["data"]
        assert data["posts"] == []
        assert data["pagination"]["total_count"] == 0
        assert data["pagination"]["has_more"] is False


@pytest.mark.asyncio
async def test_following_feed_ignored_when_not_logged_in(client):
    """비로그인 시 following=true는 무시되고 전체 피드를 반환합니다."""
    # 게시글 작성용 사용자
    cli_a, user_a = await create_verified_user(client, "writer@test.com", "writerrr1")
    async with cli_a:
        await create_post(cli_a, "공개 게시글")

    # 비로그인 클라이언트로 following=true 요청
    res = await client.get("/v1/posts/", params={"following": "true"})
    assert res.status_code == 200

    posts = res.json()["data"]["posts"]
    # 비로그인이므로 전체 피드 반환 (게시글이 있어야 함)
    assert len(posts) >= 1


@pytest.mark.asyncio
async def test_following_feed_with_sort(client):
    """팔로잉 피드 + 정렬 조합이 동작하는지 확인합니다."""
    cli_a, user_a = await create_verified_user(client, "sorta@test.com", "sortaaaaa")
    cli_b, user_b = await create_verified_user(client, "sortb@test.com", "sortbbbbb")

    async with cli_a, cli_b:
        # B가 여러 게시글 작성
        await create_post(cli_b, "첫 번째 글")
        await create_post(cli_b, "두 번째 글")

        # A가 B를 팔로우
        res = await cli_a.post(f"/v1/users/{user_b['user_id']}/follow")
        assert res.status_code == 201

        # 최신순 정렬과 함께 팔로잉 피드 조회
        res = await cli_a.get(
            "/v1/posts/", params={"following": "true", "sort": "latest"}
        )
        assert res.status_code == 200

        posts = res.json()["data"]["posts"]
        assert len(posts) == 2
        # 최신순: 두 번째 글이 먼저
        assert posts[0]["title"] == "두 번째 글"
        assert posts[1]["title"] == "첫 번째 글"


@pytest.mark.asyncio
async def test_following_feed_with_category_filter(client):
    """팔로잉 피드 + 카테고리 필터 조합이 동작하는지 확인합니다."""
    cli_a, user_a = await create_verified_user(client, "cata@test.com", "cataaaaa1")
    cli_b, user_b = await create_verified_user(client, "catb@test.com", "catbbbbb1")

    async with cli_a, cli_b:
        # B가 카테고리 1, 2에 게시글 작성
        post_cat1 = await create_post(cli_b, "자유게시판 글", category_id=1)
        post_cat2 = await create_post(cli_b, "질문답변 글", category_id=2)

        # A가 B를 팔로우
        res = await cli_a.post(f"/v1/users/{user_b['user_id']}/follow")
        assert res.status_code == 201

        # 카테고리 1로 필터링
        res = await cli_a.get(
            "/v1/posts/", params={"following": "true", "category_id": 1}
        )
        assert res.status_code == 200

        posts = res.json()["data"]["posts"]
        post_ids = [p["post_id"] for p in posts]
        assert post_cat1 in post_ids
        assert post_cat2 not in post_ids
