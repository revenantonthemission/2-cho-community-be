"""Admin 도메인 -- 신고(Reports) 테스트."""

import pytest
from httpx import AsyncClient

from tests.conftest import (
    create_test_comment,
    create_test_post,
    create_verified_user,
)

# ---------------------------------------------------------------------------
# 신고 생성
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_report_for_post_returns_201(
    client: AsyncClient,
    fake,
    admin,
    regular_user,
):
    """게시글 신고 생성 시 201을 반환한다."""
    # Arrange — 일반 사용자가 게시글 작성
    post = await create_test_post(client, regular_user["headers"])
    reporter = await create_verified_user(client, fake)

    # Act
    res = await client.post(
        "/v1/reports",
        json={
            "target_type": "post",
            "target_id": post["post_id"],
            "reason": "spam",
            "description": "스팸 게시글입니다.",
        },
        headers=reporter["headers"],
    )

    # Assert
    assert res.status_code == 201
    data = res.json()
    assert data["code"] == "REPORT_CREATED"
    assert data["data"]["report_id"] > 0
    assert data["data"]["target_type"] == "post"
    assert data["data"]["reason"] == "spam"


@pytest.mark.asyncio
async def test_create_report_for_comment_returns_201(
    client: AsyncClient,
    fake,
    regular_user,
):
    """댓글 신고 생성 시 201을 반환한다."""
    # Arrange
    post = await create_test_post(client, regular_user["headers"])
    comment = await create_test_comment(
        client,
        regular_user["headers"],
        post["post_id"],
    )
    reporter = await create_verified_user(client, fake)

    # Act
    res = await client.post(
        "/v1/reports",
        json={
            "target_type": "comment",
            "target_id": comment["comment_id"],
            "reason": "abuse",
        },
        headers=reporter["headers"],
    )

    # Assert
    assert res.status_code == 201
    assert res.json()["data"]["target_type"] == "comment"


@pytest.mark.asyncio
async def test_report_own_content_returns_400(
    client: AsyncClient,
    regular_user,
):
    """자기 콘텐츠를 신고하면 400을 반환한다."""
    # Arrange
    post = await create_test_post(client, regular_user["headers"])

    # Act
    res = await client.post(
        "/v1/reports",
        json={
            "target_type": "post",
            "target_id": post["post_id"],
            "reason": "spam",
        },
        headers=regular_user["headers"],
    )

    # Assert
    assert res.status_code == 400
    assert res.json()["detail"]["error"] == "cannot_report_own_content"


@pytest.mark.asyncio
async def test_duplicate_report_returns_409(
    client: AsyncClient,
    fake,
    regular_user,
):
    """동일 대상에 중복 신고 시 409를 반환한다."""
    # Arrange
    post = await create_test_post(client, regular_user["headers"])
    reporter = await create_verified_user(client, fake)
    report_payload = {
        "target_type": "post",
        "target_id": post["post_id"],
        "reason": "spam",
    }

    # 첫 번째 신고
    first = await client.post(
        "/v1/reports",
        json=report_payload,
        headers=reporter["headers"],
    )
    assert first.status_code == 201

    # Act — 동일 대상 중복 신고 (사유가 달라도 중복)
    res = await client.post(
        "/v1/reports",
        json={**report_payload, "reason": "abuse"},
        headers=reporter["headers"],
    )

    # Assert
    assert res.status_code == 409


# ---------------------------------------------------------------------------
# 관리자 신고 목록 조회
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_list_reports(
    client: AsyncClient,
    fake,
    admin,
    regular_user,
):
    """관리자가 신고 목록을 조회할 수 있다."""
    # Arrange — 신고 1건 생성
    post = await create_test_post(client, regular_user["headers"])
    reporter = await create_verified_user(client, fake)
    await client.post(
        "/v1/reports",
        json={
            "target_type": "post",
            "target_id": post["post_id"],
            "reason": "inappropriate",
        },
        headers=reporter["headers"],
    )

    # Act
    res = await client.get("/v1/admin/reports", headers=admin["headers"])

    # Assert
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["pagination"]["total_count"] >= 1
    assert len(data["reports"]) >= 1


@pytest.mark.asyncio
async def test_non_admin_list_reports_returns_403(
    client: AsyncClient,
    regular_user,
):
    """일반 사용자가 신고 목록을 조회하면 403을 반환한다."""
    # Act
    res = await client.get(
        "/v1/admin/reports",
        headers=regular_user["headers"],
    )

    # Assert
    assert res.status_code == 403
    assert res.json()["detail"]["error"] == "admin_required"


# ---------------------------------------------------------------------------
# 관리자 신고 처리
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_resolve_report_deletes_target(
    client: AsyncClient,
    fake,
    admin,
    regular_user,
):
    """관리자가 신고를 resolved 처리하면 대상 콘텐츠가 삭제된다."""
    # Arrange
    post = await create_test_post(client, regular_user["headers"])
    reporter = await create_verified_user(client, fake)
    report_res = await client.post(
        "/v1/reports",
        json={
            "target_type": "post",
            "target_id": post["post_id"],
            "reason": "spam",
        },
        headers=reporter["headers"],
    )
    report_id = report_res.json()["data"]["report_id"]

    # Act
    res = await client.patch(
        f"/v1/admin/reports/{report_id}",
        json={"status": "resolved"},
        headers=admin["headers"],
    )

    # Assert
    assert res.status_code == 200
    assert res.json()["data"]["status"] == "resolved"

    # 대상 게시글이 삭제(soft delete)되었는지 확인
    detail = await client.get(f"/v1/posts/{post['post_id']}")
    assert detail.status_code == 404


@pytest.mark.asyncio
async def test_admin_resolve_report_with_suspension(
    client: AsyncClient,
    fake,
    admin,
    regular_user,
):
    """관리자가 신고 resolved 처리 시 작성자를 정지할 수 있다."""
    # Arrange
    post = await create_test_post(client, regular_user["headers"])
    reporter = await create_verified_user(client, fake)
    report_res = await client.post(
        "/v1/reports",
        json={
            "target_type": "post",
            "target_id": post["post_id"],
            "reason": "abuse",
        },
        headers=reporter["headers"],
    )
    report_id = report_res.json()["data"]["report_id"]

    # Act
    res = await client.patch(
        f"/v1/admin/reports/{report_id}",
        json={"status": "resolved", "suspend_days": 30},
        headers=admin["headers"],
    )

    # Assert — 신고 처리 성공
    assert res.status_code == 200

    # 작성자가 정지되었는지 DB에서 확인
    from database.connection import get_connection

    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT suspended_until, suspended_reason FROM user WHERE id = %s",
            (regular_user["user_id"],),
        )
        row = await cur.fetchone()
        assert row[0] is not None  # suspended_until 설정됨
        assert "신고 처리" in row[1]  # 사유에 신고 처리 문구 포함


@pytest.mark.asyncio
async def test_admin_dismiss_report(
    client: AsyncClient,
    fake,
    admin,
    regular_user,
):
    """관리자가 신고를 dismissed 처리하면 대상 콘텐츠가 유지된다."""
    # Arrange
    post = await create_test_post(client, regular_user["headers"])
    reporter = await create_verified_user(client, fake)
    report_res = await client.post(
        "/v1/reports",
        json={
            "target_type": "post",
            "target_id": post["post_id"],
            "reason": "other",
            "description": "실수로 신고",
        },
        headers=reporter["headers"],
    )
    report_id = report_res.json()["data"]["report_id"]

    # Act
    res = await client.patch(
        f"/v1/admin/reports/{report_id}",
        json={"status": "dismissed"},
        headers=admin["headers"],
    )

    # Assert
    assert res.status_code == 200
    assert res.json()["data"]["status"] == "dismissed"

    # 대상 게시글이 유지되는지 확인
    detail = await client.get(f"/v1/posts/{post['post_id']}")
    assert detail.status_code == 200
