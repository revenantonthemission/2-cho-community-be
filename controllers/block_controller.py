"""block_controller: 사용자 차단 관련 컨트롤러 모듈."""

from fastapi import HTTPException, Request, status
from pymysql.err import IntegrityError

from models import block_models
from models.user_models import User, get_user_by_id
from schemas.common import create_response
from dependencies.request_context import get_request_timestamp
from utils.formatters import format_datetime


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

    # 자기 자신 차단 방지
    if target_user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "cannot_block_self",
                "message": "자기 자신을 차단할 수 없습니다.",
                "timestamp": timestamp,
            },
        )

    # 대상 사용자 존재 확인
    target = await get_user_by_id(target_user_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "user_not_found", "timestamp": timestamp},
        )

    try:
        await block_models.add_block(current_user.id, target_user_id)
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "already_blocked",
                "message": "이미 차단한 사용자입니다.",
                "timestamp": timestamp,
            },
        )

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

    removed = await block_models.remove_block(current_user.id, target_user_id)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "block_not_found",
                "message": "차단하지 않은 사용자입니다.",
                "timestamp": timestamp,
            },
        )

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

    blocks, total_count = await block_models.get_my_blocks(
        current_user.id, offset, limit
    )
    has_more = offset + limit < total_count

    for block in blocks:
        block["created_at"] = format_datetime(block["created_at"])

    return create_response(
        "MY_BLOCKS_LOADED",
        "차단 목록을 조회했습니다.",
        data={
            "blocks": blocks,
            "pagination": {"total_count": total_count, "has_more": has_more},
        },
        timestamp=timestamp,
    )
