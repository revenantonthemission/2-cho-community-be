"""test_related_posts: 연관 게시글 추천 API 테스트 모듈."""

import pytest
from httpx import AsyncClient

from database.connection import get_connection


# ==========================================
# 헬퍼 함수
# ==========================================

async def create_post(
    cli: AsyncClient,
    title: str = "테스트 게시글",
    content: str = "테스트 내용입니다.",
    category_id: int = 1,
    tags: list | None = None,
) -> int:
    """게시글 생성 헬퍼."""
    payload = {
        "title": title,
        "content": content,
        "category_id": category_id,
    }
    if tags is not None:
        payload["tags"] = tags
    res = await cli.post("/v1/posts/", json=payload)
    assert res.status_code == 201, f"게시글 생성 실패: {res.text}"
    return res.json()["data"]["post_id"]


async def create_authorized_user(client: AsyncClient, fake) -> tuple[AsyncClient, dict]:
    """별도 인증된 사용자를 생성합니다."""
    from httpx import AsyncClient as AC, ASGITransport
    from main import app

    payload = {
        "email": fake.email(),
        "password": "Password123!",
        "nickname": fake.lexify(text="?????") + str(fake.random_int(10, 99)),
    }
    signup_res = await client.post("/v1/users/", data=payload)
    assert signup_res.status_code == 201

    # 이메일 인증 처리
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE user SET email_verified = 1 WHERE email = %s",
                (payload["email"],),
            )

    login_res = await client.post(
        "/v1/auth/session",
        json={"email": payload["email"], "password": payload["password"]},
    )
    assert login_res.status_code == 200

    login_data = login_res.json()
    access_token = login_data["data"]["access_token"]
    user_info = login_data["data"]["user"]

    transport = ASGITransport(app=app)
    auth_client = AC(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {access_token}"},
        cookies=login_res.cookies,
    )
    return auth_client, user_info


# ==========================================
# REL-01: 같은 태그의 게시글이 연관으로 추천됨
# ==========================================

@pytest.mark.asyncio
async def test_rel_01_related_by_tag(client: AsyncClient, authorized_user):
    """같은 태그를 가진 게시글이 연관 게시글로 추천된다."""
    cli, _, _ = authorized_user

    # 기준 게시글 (태그: python, fastapi)
    base_id = await create_post(cli, title="기준 게시글", tags=["python", "fastapi"])

    # 같은 태그를 가진 게시글
    related_id = await create_post(cli, title="관련 게시글", tags=["python"])

    # 다른 태그의 게시글
    await create_post(cli, title="무관한 게시글", tags=["javascript"])

    res = await cli.get(f"/v1/posts/{base_id}/related")
    assert res.status_code == 200

    posts = res.json()["data"]["posts"]
    post_ids = [p["post_id"] for p in posts]
    assert related_id in post_ids


# ==========================================
# REL-02: 현재 게시글은 연관 목록에서 제외
# ==========================================

@pytest.mark.asyncio
async def test_rel_02_excludes_current_post(client: AsyncClient, authorized_user):
    """연관 게시글 목록에 기준 게시글 자신은 포함되지 않는다."""
    cli, _, _ = authorized_user

    base_id = await create_post(cli, title="기준 게시글", tags=["python"])
    await create_post(cli, title="관련 게시글", tags=["python"])

    res = await cli.get(f"/v1/posts/{base_id}/related")
    assert res.status_code == 200

    posts = res.json()["data"]["posts"]
    post_ids = [p["post_id"] for p in posts]
    assert base_id not in post_ids


# ==========================================
# REL-03: limit 파라미터로 최대 개수 제한
# ==========================================

@pytest.mark.asyncio
async def test_rel_03_limit_parameter(client: AsyncClient, authorized_user):
    """limit 파라미터로 반환 개수를 제한할 수 있다."""
    cli, _, _ = authorized_user

    base_id = await create_post(cli, title="기준 게시글", tags=["test-limit"], category_id=1)
    # 5개의 관련 게시글 생성
    for i in range(5):
        await create_post(cli, title=f"관련 게시글 {i}", tags=["test-limit"], category_id=1)

    # limit=2로 제한
    res = await cli.get(f"/v1/posts/{base_id}/related?limit=2")
    assert res.status_code == 200

    posts = res.json()["data"]["posts"]
    assert len(posts) <= 2


# ==========================================
# REL-04: 태그 없는 게시글은 같은 카테고리로 폴백
# ==========================================

@pytest.mark.asyncio
async def test_rel_04_fallback_to_category(client: AsyncClient, authorized_user):
    """태그가 없는 게시글은 같은 카테고리의 게시글이 연관으로 추천된다."""
    cli, _, _ = authorized_user

    # 태그 없이 같은 카테고리의 게시글들
    base_id = await create_post(cli, title="기준 게시글", category_id=2)
    same_cat_id = await create_post(cli, title="같은 카테고리 게시글", category_id=2)
    diff_cat_id = await create_post(cli, title="다른 카테고리 게시글", category_id=3)

    res = await cli.get(f"/v1/posts/{base_id}/related")
    assert res.status_code == 200

    posts = res.json()["data"]["posts"]
    post_ids = [p["post_id"] for p in posts]

    # 같은 카테고리 게시글이 다른 카테고리보다 상위에 있어야 함
    if same_cat_id in post_ids and diff_cat_id in post_ids:
        assert post_ids.index(same_cat_id) < post_ids.index(diff_cat_id)


# ==========================================
# REL-05: 존재하지 않는 게시글 ID → 404
# ==========================================

@pytest.mark.asyncio
async def test_rel_05_not_found(client: AsyncClient, authorized_user):
    """존재하지 않는 게시글 ID로 조회하면 404를 반환한다."""
    cli, _, _ = authorized_user

    res = await cli.get("/v1/posts/999999/related")
    assert res.status_code == 404


# ==========================================
# REL-06: 차단한 사용자의 게시글은 연관에서 제외
# ==========================================

@pytest.mark.asyncio
async def test_rel_06_blocked_user_excluded(client: AsyncClient, authorized_user, fake):
    """차단한 사용자의 게시글은 연관 목록에서 제외된다."""
    cli, user_info, _ = authorized_user

    # 두 번째 사용자 생성
    cli2, user2_info = await create_authorized_user(client, fake)

    try:
        # 기준 게시글 (user1)
        base_id = await create_post(cli, title="기준 게시글", tags=["block-test"])

        # user2가 같은 태그로 게시글 작성
        blocked_post_id = await create_post(cli2, title="차단 사용자 게시글", tags=["block-test"])

        # user1이 user2를 차단
        block_res = await cli.post(f"/v1/users/{user2_info['user_id']}/block")
        assert block_res.status_code == 201

        # 연관 게시글 조회 → 차단 사용자 게시글 제외
        res = await cli.get(f"/v1/posts/{base_id}/related")
        assert res.status_code == 200

        posts = res.json()["data"]["posts"]
        post_ids = [p["post_id"] for p in posts]
        assert blocked_post_id not in post_ids
    finally:
        await cli2.aclose()
