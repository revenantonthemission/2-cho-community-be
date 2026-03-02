"""test_admin_reports: 관리자, 신고, 카테고리, 게시글 고정 테스트.

Phase 3 기능 검증:
- 관리자 권한 (게시글/댓글 삭제, 게시글 고정)
- 신고 (생성, 중복 방지, 자기 신고 방지, 관리자 처리)
- 카테고리 (목록 조회, 카테고리별 필터링)
- 게시글 고정 (목록 상단 표시)
"""

import pytest
from httpx import AsyncClient

from database.connection import get_connection


# ==========================================
# 헬퍼 함수
# ==========================================


async def _create_verified_user(client: AsyncClient, fake) -> tuple[str, dict]:
    """인증된 사용자를 생성하고 (access_token, user_info)를 반환합니다."""
    payload = {
        "email": fake.email(),
        "password": "Password123!",
        "nickname": fake.lexify(text="?????") + str(fake.random_int(10, 99)),
    }
    res = await client.post("/v1/users/", data=payload)
    assert res.status_code == 201

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
    data = login_res.json()["data"]
    return data["access_token"], data["user"]


async def _make_admin(user_id: int) -> None:
    """사용자를 관리자로 설정합니다."""
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE user SET role = 'admin' WHERE id = %s", (user_id,),
            )


def _auth(token: str) -> dict:
    """Bearer Token 인증 헤더를 반환합니다."""
    return {"Authorization": f"Bearer {token}"}


# ==========================================
# 1. 관리자 권한 테스트
# ==========================================


@pytest.mark.asyncio
async def test_admin_delete_others_post(client: AsyncClient, authorized_user, fake):
    """ADMIN-01: 관리자가 타인의 게시글을 삭제할 수 있다."""
    admin_cli, admin_info, _ = authorized_user
    await _make_admin(admin_info["id"])

    # 일반 사용자 생성 + 게시글 작성
    user_token, _ = await _create_verified_user(client, fake)
    post_res = await client.post(
        "/v1/posts/",
        json={"title": "User Post", "content": "Content", "category_id": 1},
        headers=_auth(user_token),
    )
    post_id = post_res.json()["data"]["post_id"]

    # 관리자가 삭제
    res = await admin_cli.delete(f"/v1/posts/{post_id}")
    assert res.status_code == 200

    # 삭제 확인
    detail_res = await client.get(f"/v1/posts/{post_id}")
    assert detail_res.status_code == 404


@pytest.mark.asyncio
async def test_admin_delete_others_comment(client: AsyncClient, authorized_user, fake):
    """ADMIN-02: 관리자가 타인의 댓글을 삭제할 수 있다."""
    admin_cli, admin_info, _ = authorized_user
    await _make_admin(admin_info["id"])

    # 일반 사용자 생성 + 게시글 + 댓글 작성
    user_token, _ = await _create_verified_user(client, fake)
    post_res = await client.post(
        "/v1/posts/",
        json={"title": "Post for Comment", "content": "Content", "category_id": 1},
        headers=_auth(user_token),
    )
    post_id = post_res.json()["data"]["post_id"]

    comment_res = await client.post(
        f"/v1/posts/{post_id}/comments",
        json={"content": "User Comment"},
        headers=_auth(user_token),
    )
    comment_id = comment_res.json()["data"]["comment_id"]

    # 관리자가 댓글 삭제
    res = await admin_cli.delete(f"/v1/posts/{post_id}/comments/{comment_id}")
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_admin_pin_unpin_post(client: AsyncClient, authorized_user):
    """ADMIN-03: 관리자가 게시글을 고정/해제할 수 있다."""
    admin_cli, admin_info, _ = authorized_user
    await _make_admin(admin_info["id"])

    # 게시글 작성
    create_res = await admin_cli.post(
        "/v1/posts/",
        json={"title": "Pin Test Post", "content": "Content", "category_id": 1},
    )
    assert create_res.status_code == 201
    post_id = create_res.json()["data"]["post_id"]

    # 고정
    pin_res = await admin_cli.patch(f"/v1/posts/{post_id}/pin")
    assert pin_res.status_code == 200
    assert pin_res.json()["code"] == "POST_PINNED"

    # 해제
    unpin_res = await admin_cli.delete(f"/v1/posts/{post_id}/pin")
    assert unpin_res.status_code == 200
    assert unpin_res.json()["code"] == "POST_UNPINNED"


@pytest.mark.asyncio
async def test_normal_user_admin_api_403(client: AsyncClient, authorized_user):
    """ADMIN-04: 일반 사용자가 관리자 API에 접근하면 403."""
    cli, _, _ = authorized_user

    # 관리자 전용 신고 목록 조회
    res = await cli.get("/v1/admin/reports")
    assert res.status_code == 403
    assert res.json()["detail"]["error"] == "admin_required"

    # 게시글 고정 시도
    create_res = await cli.post(
        "/v1/posts/",
        json={"title": "Test Post", "content": "Content", "category_id": 1},
    )
    post_id = create_res.json()["data"]["post_id"]

    pin_res = await cli.patch(f"/v1/posts/{post_id}/pin")
    assert pin_res.status_code == 403


# ==========================================
# 2. 신고 테스트
# ==========================================


@pytest.mark.asyncio
async def test_report_create(client: AsyncClient, authorized_user, fake):
    """REPORT-01: 신고 생성 (201)."""
    cli, _, _ = authorized_user

    # 다른 사용자의 게시글 생성
    other_token, _ = await _create_verified_user(client, fake)
    post_res = await client.post(
        "/v1/posts/",
        json={"title": "Bad Post", "content": "Bad Content", "category_id": 1},
        headers=_auth(other_token),
    )
    post_id = post_res.json()["data"]["post_id"]

    # 신고
    report_res = await cli.post("/v1/reports", json={
        "target_type": "post",
        "target_id": post_id,
        "reason": "spam",
        "description": "스팸 게시글입니다.",
    })
    assert report_res.status_code == 201
    assert report_res.json()["code"] == "REPORT_CREATED"
    assert report_res.json()["data"]["report_id"] > 0


@pytest.mark.asyncio
async def test_report_duplicate_409(client: AsyncClient, authorized_user, fake):
    """REPORT-02: 중복 신고 시 409."""
    cli, _, _ = authorized_user

    other_token, _ = await _create_verified_user(client, fake)
    post_res = await client.post(
        "/v1/posts/",
        json={"title": "Dup Report", "content": "Content", "category_id": 1},
        headers=_auth(other_token),
    )
    post_id = post_res.json()["data"]["post_id"]

    # 첫 번째 신고
    first_res = await cli.post("/v1/reports", json={
        "target_type": "post",
        "target_id": post_id,
        "reason": "spam",
    })
    assert first_res.status_code == 201

    # 두 번째 신고 (중복 — 사유가 달라도 같은 대상이면 중복)
    dup_res = await cli.post("/v1/reports", json={
        "target_type": "post",
        "target_id": post_id,
        "reason": "abuse",
    })
    assert dup_res.status_code == 409


@pytest.mark.asyncio
async def test_report_own_content_400(client: AsyncClient, authorized_user):
    """REPORT-03: 자기 콘텐츠 신고 시 400."""
    cli, _, _ = authorized_user

    # 자기 게시글 작성
    create_res = await cli.post(
        "/v1/posts/",
        json={"title": "My Post", "content": "Content", "category_id": 1},
    )
    post_id = create_res.json()["data"]["post_id"]

    # 자기 게시글 신고
    report_res = await cli.post("/v1/reports", json={
        "target_type": "post",
        "target_id": post_id,
        "reason": "spam",
    })
    assert report_res.status_code == 400
    assert report_res.json()["detail"]["error"] == "cannot_report_own_content"


@pytest.mark.asyncio
async def test_admin_reports_list_with_filter(
    client: AsyncClient, authorized_user, fake,
):
    """REPORT-04: 관리자 신고 목록 조회 (status 필터)."""
    admin_cli, admin_info, _ = authorized_user
    await _make_admin(admin_info["id"])

    # 다른 사용자의 게시글 + 신고 생성
    other_token, _ = await _create_verified_user(client, fake)
    post_res = await client.post(
        "/v1/posts/",
        json={"title": "Reported Post", "content": "Content", "category_id": 1},
        headers=_auth(other_token),
    )
    post_id = post_res.json()["data"]["post_id"]

    await admin_cli.post("/v1/reports", json={
        "target_type": "post",
        "target_id": post_id,
        "reason": "abuse",
    })

    # 전체 목록 조회
    list_res = await admin_cli.get("/v1/admin/reports")
    assert list_res.status_code == 200
    assert list_res.json()["data"]["pagination"]["total_count"] >= 1

    # pending 필터
    pending_res = await admin_cli.get("/v1/admin/reports?status=pending")
    assert pending_res.status_code == 200
    assert pending_res.json()["data"]["pagination"]["total_count"] >= 1

    # resolved 필터 (아직 처리된 신고 없음)
    resolved_res = await admin_cli.get("/v1/admin/reports?status=resolved")
    assert resolved_res.status_code == 200
    assert resolved_res.json()["data"]["pagination"]["total_count"] == 0


@pytest.mark.asyncio
async def test_admin_resolve_report_deletes_target(
    client: AsyncClient, authorized_user, fake,
):
    """REPORT-05: 관리자가 신고를 처리(resolved)하면 대상이 삭제된다."""
    admin_cli, admin_info, _ = authorized_user
    await _make_admin(admin_info["id"])

    # 다른 사용자 + 게시글
    other_token, _ = await _create_verified_user(client, fake)
    post_res = await client.post(
        "/v1/posts/",
        json={"title": "To Delete", "content": "Content", "category_id": 1},
        headers=_auth(other_token),
    )
    post_id = post_res.json()["data"]["post_id"]

    # 관리자가 신고
    report_res = await admin_cli.post("/v1/reports", json={
        "target_type": "post",
        "target_id": post_id,
        "reason": "inappropriate",
    })
    report_id = report_res.json()["data"]["report_id"]

    # 관리자가 처리 (resolved → 대상 삭제)
    resolve_res = await admin_cli.patch(
        f"/v1/admin/reports/{report_id}",
        json={"status": "resolved"},
    )
    assert resolve_res.status_code == 200
    assert resolve_res.json()["data"]["status"] == "resolved"

    # 게시글이 삭제되었는지 확인
    detail_res = await client.get(f"/v1/posts/{post_id}")
    assert detail_res.status_code == 404


@pytest.mark.asyncio
async def test_admin_dismiss_report_preserves_target(
    client: AsyncClient, authorized_user, fake,
):
    """REPORT-06: 관리자가 신고를 기각(dismissed)하면 대상이 유지된다."""
    admin_cli, admin_info, _ = authorized_user
    await _make_admin(admin_info["id"])

    # 다른 사용자 + 게시글
    other_token, _ = await _create_verified_user(client, fake)
    post_res = await client.post(
        "/v1/posts/",
        json={"title": "Keep This", "content": "Content", "category_id": 1},
        headers=_auth(other_token),
    )
    post_id = post_res.json()["data"]["post_id"]

    # 관리자가 신고
    report_res = await admin_cli.post("/v1/reports", json={
        "target_type": "post",
        "target_id": post_id,
        "reason": "other",
        "description": "실수로 신고",
    })
    report_id = report_res.json()["data"]["report_id"]

    # 관리자가 기각 (dismissed → 대상 유지)
    dismiss_res = await admin_cli.patch(
        f"/v1/admin/reports/{report_id}",
        json={"status": "dismissed"},
    )
    assert dismiss_res.status_code == 200
    assert dismiss_res.json()["data"]["status"] == "dismissed"

    # 게시글이 유지되는지 확인
    detail_res = await client.get(f"/v1/posts/{post_id}")
    assert detail_res.status_code == 200


# ==========================================
# 3. 카테고리 테스트
# ==========================================


@pytest.mark.asyncio
async def test_category_list(client: AsyncClient):
    """CAT-01: 카테고리 목록 조회 (인증 불필요)."""
    res = await client.get("/v1/categories/")
    assert res.status_code == 200

    categories = res.json()["data"]["categories"]
    assert len(categories) == 4

    # sort_order 순서대로 반환
    slugs = [c["slug"] for c in categories]
    assert slugs == ["free", "qna", "info", "notice"]


@pytest.mark.asyncio
async def test_category_filtered_posts(client: AsyncClient, authorized_user):
    """CAT-02: 카테고리별 게시글 생성 및 조회."""
    cli, _, _ = authorized_user

    # 자유게시판(1)에 게시글
    await cli.post(
        "/v1/posts/",
        json={"title": "Free Board Post", "content": "Content", "category_id": 1},
    )
    # 질문답변(2)에 게시글
    await cli.post(
        "/v1/posts/",
        json={"title": "QnA Post", "content": "Question", "category_id": 2},
    )

    # 카테고리 2(질문답변)로 필터
    res = await client.get("/v1/posts/?offset=0&limit=10&category_id=2")
    assert res.status_code == 200
    posts = res.json()["data"]["posts"]

    # 질문답변 게시글만 나와야 함
    assert len(posts) >= 1
    assert all(p["category_name"] == "질문답변" for p in posts)

    # 자유게시판 게시글이 포함되지 않아야 함
    assert all(p["category_id"] != 1 for p in posts)


# ==========================================
# 4. 게시글 고정 테스트
# ==========================================


@pytest.mark.asyncio
async def test_pinned_post_appears_first(client: AsyncClient, authorized_user):
    """PIN-01: 고정 게시글이 목록 상단에 표시된다."""
    admin_cli, admin_info, _ = authorized_user
    await _make_admin(admin_info["id"])

    # 여러 게시글 작성 (첫 번째 → 두 번째 → 세 번째 순서)
    first_res = await admin_cli.post(
        "/v1/posts/",
        json={"title": "First Post", "content": "Content", "category_id": 1},
    )
    first_id = first_res.json()["data"]["post_id"]

    await admin_cli.post(
        "/v1/posts/",
        json={"title": "Second Post", "content": "Content", "category_id": 1},
    )

    await admin_cli.post(
        "/v1/posts/",
        json={"title": "Third Post", "content": "Content", "category_id": 1},
    )

    # latest 정렬 → 고정 전에는 Third가 최상단
    list_before = await client.get("/v1/posts/?offset=0&limit=10")
    posts_before = list_before.json()["data"]["posts"]
    assert posts_before[0]["post_id"] != first_id

    # 첫 번째 게시글 고정
    pin_res = await admin_cli.patch(f"/v1/posts/{first_id}/pin")
    assert pin_res.status_code == 200

    # 고정 후 → First가 최상단
    list_after = await client.get("/v1/posts/?offset=0&limit=10")
    posts_after = list_after.json()["data"]["posts"]
    assert posts_after[0]["post_id"] == first_id
    assert posts_after[0]["is_pinned"] is True
