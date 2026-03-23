"""admin_controller: 관리자 대시보드 컨트롤러 모듈."""

import logging

from fastapi import Request

from dependencies.request_context import get_request_timestamp
from models import admin_models
from models.user_models import User
from schemas.common import create_response

logger = logging.getLogger(__name__)


async def get_dashboard(current_user: User, request: Request) -> dict:
    """대시보드 통계를 조회합니다."""
    timestamp = get_request_timestamp(request)

    summary = await admin_models.get_dashboard_summary()
    # 최근 30일 통계 — 관리자 대시보드의 트렌드 차트 기간과 동기화
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

    # search가 None이면 전체 조회 — 모델에서 LIKE 조건을 선택적으로 적용
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


async def cleanup_tokens(request: Request) -> dict:
    """만료된 토큰을 정리합니다 (관리자 또는 내부 호출).

    Refresh Token과 이메일 인증 토큰을 일괄 삭제합니다.
    EventBridge 스케줄로 주기적으로 호출합니다.
    """
    # 지연 import — 이 엔드포인트는 스케줄러에서만 호출되므로 모듈 레벨 의존성을 줄임
    from models.token_models import cleanup_expired_tokens
    from models.verification_models import cleanup_expired_verification_tokens

    # Refresh Token과 이메일 인증 토큰을 분리 실행 — 한쪽 실패가 다른쪽에 영향 없도록
    refresh_deleted = await cleanup_expired_tokens()
    verification_deleted = await cleanup_expired_verification_tokens()

    logger.info(
        "토큰 정리 완료: refresh=%d, verification=%d",
        refresh_deleted,
        verification_deleted,
    )

    # create_response 대신 단순 dict 반환 — 내부 호출용 엔드포인트이므로 표준 래퍼 불필요
    return {
        "status": "success",
        "data": {
            "refresh_tokens_deleted": refresh_deleted,
            "verification_tokens_deleted": verification_deleted,
        },
    }
