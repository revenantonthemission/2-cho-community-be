"""report_router: 신고 관련 라우터 모듈."""

from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, status

from core.dependencies.auth import require_admin, require_admin_or_internal, require_verified_email
from modules.admin import admin_controller, report_controller, suspension_controller
from modules.admin.report_schemas import CreateReportRequest, ResolveReportRequest
from modules.admin.suspension_schemas import SuspendUserRequest
from modules.user.models import User

report_router = APIRouter(tags=["reports"])


# ============ 사용자 신고 ============


@report_router.post("/v1/reports", status_code=status.HTTP_201_CREATED)
async def create_report(
    report_data: CreateReportRequest,
    request: Request,
    current_user: User = Depends(require_verified_email),
) -> dict:
    """콘텐츠를 신고합니다."""
    return await report_controller.create_report(report_data, current_user, request)


# ============ 관리자 신고 관리 ============


@report_router.get("/v1/admin/reports", status_code=status.HTTP_200_OK)
async def get_reports(
    request: Request,
    current_user: User = Depends(require_admin),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    report_status: Literal["pending", "resolved", "dismissed"] | None = Query(
        None, alias="status", description="필터: pending, resolved, dismissed"
    ),
) -> dict:
    """신고 목록을 조회합니다 (관리자 전용)."""
    return await report_controller.get_reports(offset, limit, request, report_status)


@report_router.patch("/v1/admin/reports/{report_id}", status_code=status.HTTP_200_OK)
async def resolve_report(
    report_id: int,
    report_data: ResolveReportRequest,
    request: Request,
    current_user: User = Depends(require_admin),
) -> dict:
    """신고를 처리합니다 (관리자 전용)."""
    return await report_controller.resolve_report(report_id, report_data, current_user, request)


@report_router.patch("/v1/admin/reports/{report_id}/reopen", status_code=status.HTTP_200_OK)
async def reopen_report(
    report_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
) -> dict:
    """처리된 신고를 다시 열어 재검토합니다 (관리자 전용)."""
    return await report_controller.reopen_report(report_id, current_user, request)


# ============ 관리자 사용자 관리 ============


@report_router.post(
    "/v1/admin/users/{user_id}/suspend",
    status_code=status.HTTP_200_OK,
)
async def suspend_user(
    user_id: int,
    suspend_data: SuspendUserRequest,
    request: Request,
    current_user: User = Depends(require_admin),
) -> dict:
    """사용자를 정지합니다 (관리자 전용)."""
    return await suspension_controller.suspend_user(user_id, suspend_data, current_user, request)


@report_router.delete(
    "/v1/admin/users/{user_id}/suspend",
    status_code=status.HTTP_200_OK,
)
async def unsuspend_user(
    user_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
) -> dict:
    """사용자 정지를 해제합니다 (관리자 전용)."""
    return await suspension_controller.unsuspend_user(user_id, current_user, request)


# ============ 관리자 대시보드 ============


@report_router.get("/v1/admin/dashboard", status_code=status.HTTP_200_OK)
async def get_dashboard(
    request: Request,
    current_user: User = Depends(require_admin),
) -> dict:
    """대시보드 통계를 조회합니다 (관리자 전용)."""
    return await admin_controller.get_dashboard(current_user, request)


@report_router.get("/v1/admin/users", status_code=status.HTTP_200_OK)
async def get_admin_users(
    request: Request,
    current_user: User = Depends(require_admin),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, description="닉네임/이메일 검색"),
) -> dict:
    """사용자 목록을 조회합니다 (관리자 전용)."""
    return await admin_controller.get_users(current_user, request, offset, limit, search)


# ============ 관리자 추천 피드 ============


@report_router.post("/v1/admin/feed/recompute", status_code=status.HTTP_200_OK)
async def recompute_feed_scores(
    request: Request,
    current_user: User | None = Depends(require_admin_or_internal),
) -> dict:
    """추천 피드 점수를 수동으로 재계산합니다 (관리자 또는 내부 호출).

    관리자 UI에서 수동 호출하거나 EventBridge 스케줄로 자동 호출합니다.
    """
    from modules.post.feed_service import FeedService

    result = await FeedService.recompute_all_scores()
    return {"status": "success", "data": result}


# ============ 내부 배치 작업 ============


@report_router.post("/v1/admin/cleanup/tokens", status_code=status.HTTP_200_OK)
async def cleanup_tokens(
    request: Request,
    current_user: User | None = Depends(require_admin_or_internal),
) -> dict:
    """만료된 토큰을 정리합니다 (관리자 또는 내부 호출)."""
    return await admin_controller.cleanup_tokens(request)
