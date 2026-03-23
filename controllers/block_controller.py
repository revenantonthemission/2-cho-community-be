"""block_controller: 사용자 차단 관련 컨트롤러 모듈."""

from fastapi import Request

from dependencies.request_context import get_request_timestamp
from models.user_models import User
from schemas.common import create_response
from services.block_service import BlockService


async def block_user(
    target_user_id: int,
    current_user: User,
    request: Request,
) -> dict:
    """사용자를 차단합니다.

    Raises:
        HTTPException: 자기 차단(400), 대상 없음(404), 이미 차단(409).
    """
    timestamp = get_request_timestamp(request)

    # 차단 시 기존 팔로우 관계도 서비스 레이어에서 자동 해제
    await BlockService.block_user(current_user.id, target_user_id, timestamp)

    return create_response(
        "USER_BLOCKED",
        "사용자를 차단했습니다.",
        timestamp=timestamp,
    )


async def unblock_user(
    target_user_id: int,
    current_user: User,
    request: Request,
) -> dict:
    """사용자 차단을 해제합니다.

    Raises:
        HTTPException: 차단하지 않은 경우 404.
    """
    timestamp = get_request_timestamp(request)

    # 차단 해제만 수행 — 팔로우 관계는 자동 복원하지 않음 (사용자가 직접 다시 팔로우해야 함)
    await BlockService.unblock_user(current_user.id, target_user_id, timestamp)

    return create_response(
        "USER_UNBLOCKED",
        "차단이 해제되었습니다.",
        timestamp=timestamp,
    )


async def get_my_blocks(
    current_user: User,
    request: Request,
    offset: int = 0,
    limit: int = 10,
) -> dict:
    """차단 목록을 조회합니다."""
    timestamp = get_request_timestamp(request)

    # 차단 목록은 본인만 조회 가능 — current_user.id로 격리
    data = await BlockService.get_blocked_users(current_user.id, offset, limit)

    return create_response(
        "MY_BLOCKS_LOADED",
        "차단 목록을 조회했습니다.",
        data=data,
        timestamp=timestamp,
    )
