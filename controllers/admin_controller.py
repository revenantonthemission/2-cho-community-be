"""admin_controller: 관리자 대시보드 컨트롤러 모듈."""

from fastapi import Request

from models import admin_models
from models.user_models import User
from schemas.common import create_response
from dependencies.request_context import get_request_timestamp


async def get_dashboard(current_user: User, request: Request) -> dict:
    """대시보드 통계를 조회합니다."""
    timestamp = get_request_timestamp(request)

    summary = await admin_models.get_dashboard_summary()
    daily_stats = await admin_models.get_daily_stats(days=30)

    return create_response(
        "DASHBOARD_LOADED",
        "대시보드 통계를 조회했습니다.",
        data={"summary": summary, "daily_stats": daily_stats},
        timestamp=timestamp,
    )


async def get_users(
    current_user: User,
    request: Request,
    offset: int = 0,
    limit: int = 20,
    search: str | None = None,
) -> dict:
    """사용자 목록을 조회합니다."""
    timestamp = get_request_timestamp(request)

    users, total_count = await admin_models.get_users_list(offset, limit, search)
    has_more = offset + limit < total_count

    return create_response(
        "USERS_LOADED",
        "사용자 목록을 조회했습니다.",
        data={
            "users": users,
            "pagination": {"total_count": total_count, "has_more": has_more},
        },
        timestamp=timestamp,
    )
