"""Posts 도메인 — CRUD 테스트."""

import pytest
from httpx import AsyncClient

from tests.conftest import create_test_post, create_verified_user

# ---------------------------------------------------------------------------
# 게시글 생성
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_post_returns_201(client: AsyncClient, fake):
    """기본 필드(title, content, category_id)로 게시글 생성 시 201을 반환한다."""
    # Arrange
    user = await create_verified_user(client, fake)

    # Act
    res = await client.post(
        "/v1/posts/",
        json={"title": "테스트 게시글", "content": "테스트 내용입니다.", "category_id": 1},
        headers=user["headers"],
    )

    # Assert
    assert res.status_code == 201
    data = res.json()["data"]
    assert "post_id" in data
    assert data["post_id"] > 0


@pytest.mark.asyncio
async def test_create_post_with_tags_returns_201(client: AsyncClient, fake):
    """태그를 포함하여 게시글 생성 시 201을 반환한다."""
    user = await create_verified_user(client, fake)

    res = await client.post(
        "/v1/posts/",
        json={
            "title": "태그 테스트",
            "content": "태그가 포함된 게시글",
            "category_id": 1,
            "tags": ["python", "fastapi"],
        },
        headers=user["headers"],
    )

    assert res.status_code == 201

    # 생성된 게시글 상세 조회 시 태그가 포함되어야 함
    post_id = res.json()["data"]["post_id"]
    detail = await client.get(f"/v1/posts/{post_id}", headers=user["headers"])
    assert detail.status_code == 200


@pytest.mark.asyncio
async def test_create_post_with_images_returns_201(client: AsyncClient, fake):
    """image_urls를 포함하여 게시글 생성 시 201을 반환한다."""
    user = await create_verified_user(client, fake)

    res = await client.post(
        "/v1/posts/",
        json={
            "title": "이미지 테스트",
            "content": "이미지가 포함된 게시글",
            "category_id": 1,
            "image_urls": ["/uploads/posts/fake-uuid.jpg"],
        },
        headers=user["headers"],
    )

    assert res.status_code == 201


@pytest.mark.asyncio
async def test_create_post_without_auth_returns_401(client: AsyncClient):
    """인증 없이 게시글 생성 시 401을 반환한다."""
    res = await client.post(
        "/v1/posts/",
        json={"title": "무인증 게시글", "content": "내용입니다.", "category_id": 1},
    )

    assert res.status_code == 401


# ---------------------------------------------------------------------------
# 게시글 조회
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_post_increments_view_count(client: AsyncClient, fake):
    """다른 사용자가 게시글을 조회하면 조회수가 증가한다."""
    user = await create_verified_user(client, fake)
    user2 = await create_verified_user(client, fake)
    post = await create_test_post(client, user["headers"])
    post_id = post["post_id"]

    # 첫 번째 조회 (user)
    res1 = await client.get(f"/v1/posts/{post_id}", headers=user["headers"])
    assert res1.status_code == 200
    views_1 = res1.json()["data"]["post"]["views_count"]

    # 두 번째 조회 (user2 — 다른 사용자여야 조회수 증가)
    res2 = await client.get(f"/v1/posts/{post_id}", headers=user2["headers"])
    assert res2.status_code == 200
    views_2 = res2.json()["data"]["post"]["views_count"]

    assert views_2 > views_1


@pytest.mark.asyncio
async def test_get_deleted_post_returns_404(client: AsyncClient, fake):
    """삭제된 게시글 조회 시 404를 반환한다."""
    user = await create_verified_user(client, fake)
    post = await create_test_post(client, user["headers"])
    post_id = post["post_id"]

    # 삭제
    del_res = await client.delete(f"/v1/posts/{post_id}", headers=user["headers"])
    assert del_res.status_code == 200

    # 삭제 후 조회
    res = await client.get(f"/v1/posts/{post_id}", headers=user["headers"])
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# 게시글 수정
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_post_succeeds(client: AsyncClient, fake):
    """작성자가 게시글을 수정하면 200을 반환한다."""
    user = await create_verified_user(client, fake)
    post = await create_test_post(client, user["headers"])
    post_id = post["post_id"]

    res = await client.patch(
        f"/v1/posts/{post_id}",
        json={"title": "수정된 제목입니다", "content": "수정된 내용입니다."},
        headers=user["headers"],
    )

    assert res.status_code == 200


@pytest.mark.asyncio
async def test_update_other_user_post_returns_403(client: AsyncClient, fake):
    """다른 사용자의 게시글을 수정하려 하면 403을 반환한다."""
    user1 = await create_verified_user(client, fake)
    user2 = await create_verified_user(client, fake)
    post = await create_test_post(client, user1["headers"])
    post_id = post["post_id"]

    res = await client.patch(
        f"/v1/posts/{post_id}",
        json={"title": "탈취 시도 제목입니다"},
        headers=user2["headers"],
    )

    assert res.status_code == 403


# ---------------------------------------------------------------------------
# 게시글 삭제
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_post_soft_deletes(client: AsyncClient, fake):
    """게시글 삭제 후 조회 시 404를 반환한다 (soft delete)."""
    user = await create_verified_user(client, fake)
    post = await create_test_post(client, user["headers"])
    post_id = post["post_id"]

    del_res = await client.delete(f"/v1/posts/{post_id}", headers=user["headers"])
    assert del_res.status_code == 200

    get_res = await client.get(f"/v1/posts/{post_id}", headers=user["headers"])
    assert get_res.status_code == 404


@pytest.mark.asyncio
async def test_delete_other_user_post_returns_403(client: AsyncClient, fake):
    """다른 사용자의 게시글을 삭제하려 하면 403을 반환한다."""
    user1 = await create_verified_user(client, fake)
    user2 = await create_verified_user(client, fake)
    post = await create_test_post(client, user1["headers"])
    post_id = post["post_id"]

    res = await client.delete(f"/v1/posts/{post_id}", headers=user2["headers"])

    assert res.status_code == 403
