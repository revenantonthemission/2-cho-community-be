"""report_controller: 신고 관련 컨트롤러 모듈."""

from fastapi import Request
from pymysql.err import IntegrityError

from core.dependencies.request_context import get_request_timestamp
from core.utils.error_codes import ErrorCode
from core.utils.exceptions import conflict_error
from core.utils.pagination import validate_pagination
from modules.admin.report_schemas import CreateReportRequest, ResolveReportRequest
from modules.admin.report_service import ReportService
from modules.user.models import User
from schemas.common import create_response


async def create_report(
    report_data: CreateReportRequest,
    current_user: User,
    request: Request,
) -> dict:
    """신고를 생성합니다."""
    timestamp = get_request_timestamp(request)

    # IntegrityError는 DB 유니크 제약(reporter+target) 위반 — 사전 체크 대신 예외로 처리해 레이스 컨디션 방지
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
        # 보안: from None으로 원본 예외를 억제 — DB 내부 정보를 응답에 노출하지 않기 위해
        raise conflict_error(ErrorCode.REPORT_ALREADY_EXISTS, timestamp, "이미 신고한 콘텐츠입니다.") from None

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

    # 페이지네이션 파라미터를 컨트롤러에서 직접 검증 — 서비스 레이어에 무효값이 도달하기 전에 차단
    # limit 상한(100)은 한 번에 지나치게 많은 신고를 로드해 관리자 UI가 느려지는 것을 방지
    validate_pagination(offset, limit, timestamp)

    reports_data, total_count, has_more = await ReportService.get_reports(
        status=report_status,
        offset=offset,
        limit=limit,
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

    # admin_id 기록 — 누가 처리했는지 감사 추적을 위해 신고 레코드에 저장
    result = await ReportService.resolve_report(
        report_id=report_id,
        admin_id=current_user.id,
        new_status=report_data.status,
        timestamp=timestamp,
        # suspend_days가 None이면 정지 없이 콘텐츠만 삭제, 값이 있으면 해당 기간 계정 정지
        suspend_days=report_data.suspend_days,
    )

    return create_response(
        "REPORT_RESOLVED",
        "신고가 처리되었습니다.",
        data=result,
        timestamp=timestamp,
    )


async def reopen_report(
    report_id: int,
    current_user: User,
    request: Request,
) -> dict:
    """처리된 신고를 다시 열어 재검토합니다 (관리자 전용)."""
    timestamp = get_request_timestamp(request)

    result = await ReportService.reopen_report(
        report_id=report_id,
        timestamp=timestamp,
    )

    return create_response(
        "REPORT_REOPENED",
        "신고가 다시 열렸습니다.",
        data=result,
        timestamp=timestamp,
    )
