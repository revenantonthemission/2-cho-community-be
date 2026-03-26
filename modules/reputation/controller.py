"""reputation_controller: 평판 시스템 요청 처리."""

from fastapi import Request

from core.dependencies.request_context import get_request_timestamp
from core.utils.pagination import validate_pagination
from modules.reputation import models as rep_models
from schemas.common import create_response


async def get_user_reputation(user_id: int, request: Request) -> dict:
    """사용자 평판 요약 정보를 조회합니다."""
    timestamp = get_request_timestamp(request)
    summary = await rep_models.get_user_reputation_summary(user_id)

    # 존재하지 않는 사용자는 기본값 반환
    if summary is None:
        data = {
            "user_id": user_id,
            "reputation_score": 0,
            "trust_level": 0,
            "trust_level_name": None,
            "trust_level_description": None,
            "min_reputation": 0,
            "badge_count": 0,
        }
    else:
        data = dict(summary)

    return create_response(
        "REPUTATION_RETRIEVED",
        "평판 정보 조회에 성공했습니다.",
        data=data,
        timestamp=timestamp,
    )


async def get_user_reputation_history(
    user_id: int,
    offset: int,
    limit: int,
    request: Request,
) -> dict:
    """사용자의 평판 이벤트 히스토리를 조회합니다."""
    timestamp = get_request_timestamp(request)
    validate_pagination(offset, limit, timestamp)

    events = await rep_models.get_reputation_history(user_id, offset=offset, limit=limit)
    total = await rep_models.get_reputation_history_count(user_id)

    # datetime 직렬화를 위해 각 이벤트를 dict로 변환
    serialized = [
        {
            **event,
            "created_at": event["created_at"].strftime("%Y-%m-%dT%H:%M:%SZ")
            if hasattr(event.get("created_at"), "strftime")
            else event.get("created_at"),
        }
        for event in events
    ]

    return create_response(
        "REPUTATION_HISTORY_RETRIEVED",
        "평판 히스토리 조회에 성공했습니다.",
        data={"events": serialized, "total": total},
        timestamp=timestamp,
    )


async def get_user_badges(user_id: int, request: Request) -> dict:
    """사용자가 획득한 배지 목록을 조회합니다."""
    timestamp = get_request_timestamp(request)
    badges = await rep_models.get_user_badges(user_id)

    # datetime 직렬화
    serialized = [
        {
            **badge,
            "earned_at": badge["earned_at"].strftime("%Y-%m-%dT%H:%M:%SZ")
            if hasattr(badge.get("earned_at"), "strftime")
            else badge.get("earned_at"),
        }
        for badge in badges
    ]

    return create_response(
        "BADGES_RETRIEVED",
        "사용자 배지 목록 조회에 성공했습니다.",
        data={"badges": serialized},
        timestamp=timestamp,
    )


async def get_all_badges(request: Request) -> dict:
    """모든 배지 정의를 조회합니다."""
    timestamp = get_request_timestamp(request)
    badges = await rep_models.get_all_badge_definitions()

    # datetime 직렬화 (created_at 포함)
    serialized = [
        {
            **badge,
            "created_at": badge["created_at"].strftime("%Y-%m-%dT%H:%M:%SZ")
            if badge.get("created_at") and hasattr(badge.get("created_at"), "strftime")
            else badge.get("created_at"),
        }
        for badge in badges
    ]

    return create_response(
        "BADGE_DEFINITIONS_RETRIEVED",
        "배지 정의 목록 조회에 성공했습니다.",
        data={"badges": serialized},
        timestamp=timestamp,
    )


async def get_trust_levels(request: Request) -> dict:
    """신뢰 등급 정의 목록을 조회합니다."""
    timestamp = get_request_timestamp(request)
    levels = await rep_models.get_trust_level_definitions()

    return create_response(
        "TRUST_LEVELS_RETRIEVED",
        "신뢰 등급 목록 조회에 성공했습니다.",
        data={"levels": list(levels)},
        timestamp=timestamp,
    )
