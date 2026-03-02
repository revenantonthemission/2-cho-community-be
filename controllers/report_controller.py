"""report_controller: 신고 관련 컨트롤러 모듈."""

from fastapi import HTTPException, Request, status
from pymysql.err import IntegrityError

from models.user_models import User
from schemas.report_schemas import CreateReportRequest, ResolveReportRequest
from schemas.common import create_response
from dependencies.request_context import get_request_timestamp
from services.report_service import ReportService
from utils.exceptions import conflict_error


async def create_report(
    report_data: CreateReportRequest,
    current_user: User,
    request: Request,
) -> dict:
    """신고를 생성합니다."""
    timestamp = get_request_timestamp(request)

    try:
        result = await ReportService.create_report(
            reporter_id=current_user.id,
            target_type=report_data.target_type,
            target_id=report_data.target_id,
            reason=report_data.reason,
            description=report_data.description,
            timestamp=timestamp,
        )
    except IntegrityError:
        raise conflict_error("report", timestamp, "이미 신고한 콘텐츠입니다.")

    return create_response(
        "REPORT_CREATED",
        "신고가 접수되었습니다.",
        data=result,
        timestamp=timestamp,
    )


async def get_reports(
    offset: int,
    limit: int,
    request: Request,
    report_status: str | None = None,
) -> dict:
    """신고 목록을 조회합니다 (관리자 전용)."""
    timestamp = get_request_timestamp(request)

    if offset < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_offset", "timestamp": timestamp},
        )

    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_limit", "timestamp": timestamp},
        )

    reports_data, total_count, has_more = await ReportService.get_reports(
        status=report_status, offset=offset, limit=limit,
    )

    return create_response(
        "REPORTS_RETRIEVED",
        "신고 목록 조회에 성공했습니다.",
        data={
            "reports": reports_data,
            "pagination": {
                "offset": offset,
                "limit": limit,
                "total_count": total_count,
                "has_more": has_more,
            },
        },
        timestamp=timestamp,
    )


async def resolve_report(
    report_id: int,
    report_data: ResolveReportRequest,
    current_user: User,
    request: Request,
) -> dict:
    """신고를 처리합니다 (관리자 전용)."""
    timestamp = get_request_timestamp(request)

    result = await ReportService.resolve_report(
        report_id=report_id,
        admin_id=current_user.id,
        new_status=report_data.status,
        timestamp=timestamp,
    )

    return create_response(
        "REPORT_RESOLVED",
        "신고가 처리되었습니다.",
        data=result,
        timestamp=timestamp,
    )
