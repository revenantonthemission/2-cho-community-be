"""report_router: 신고 관련 라우터 모듈."""

from fastapi import APIRouter, Depends, Query, Request, status
from controllers import report_controller
from dependencies.auth import require_verified_email, require_admin
from models.user_models import User
from schemas.report_schemas import CreateReportRequest, ResolveReportRequest

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
    report_status: str | None = Query(None, alias="status", description="필터: pending, resolved, dismissed"),
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
    return await report_controller.resolve_report(
        report_id, report_data, current_user, request
    )
