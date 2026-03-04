"""suspension_controller: 계정 정지 관련 컨트롤러."""

from fastapi import HTTPException, Request, status

from dependencies.request_context import get_request_timestamp
from models import user_models, suspension_models
from models.user_models import User
from schemas.common import create_response
from schemas.suspension_schemas import SuspendUserRequest
from utils.formatters import format_datetime


async def suspend_user(
    user_id: int,
    suspend_data: SuspendUserRequest,
    current_user: User,
    request: Request,
) -> dict:
    """사용자를 정지합니다 (관리자 전용)."""
    timestamp = get_request_timestamp(request)

    # 자기 자신 정지 방지
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "cannot_suspend_self",
                "message": "자기 자신을 정지할 수 없습니다.",
                "timestamp": timestamp,
            },
        )

    target_user = await user_models.get_user_by_id(user_id)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "user_not_found",
                "message": "사용자를 찾을 수 없습니다.",
                "timestamp": timestamp,
            },
        )

    # 다른 관리자 정지 방지
    if target_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "cannot_suspend_admin",
                "message": "관리자를 정지할 수 없습니다.",
                "timestamp": timestamp,
            },
        )

    success = await suspension_models.suspend_user(
        user_id=user_id,
        duration_days=suspend_data.duration_days,
        reason=suspend_data.reason,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "user_not_found",
                "message": "사용자를 찾을 수 없습니다.",
                "timestamp": timestamp,
            },
        )

    # 정지 후 사용자 정보 재조회
    updated_user = await user_models.get_user_by_id(user_id)

    return create_response(
        "USER_SUSPENDED",
        "사용자가 정지되었습니다.",
        data={
            "user_id": user_id,
            "suspended_until": format_datetime(updated_user.suspended_until) if updated_user else None,
            "suspended_reason": suspend_data.reason,
            "duration_days": suspend_data.duration_days,
        },
        timestamp=timestamp,
    )


async def unsuspend_user(
    user_id: int,
    current_user: User,
    request: Request,
) -> dict:
    """사용자 정지를 해제합니다 (관리자 전용)."""
    timestamp = get_request_timestamp(request)

    target_user = await user_models.get_user_by_id(user_id)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "user_not_found",
                "message": "사용자를 찾을 수 없습니다.",
                "timestamp": timestamp,
            },
        )

    # 정지 상태가 아닌 사용자는 해제 불필요
    if not target_user.is_suspended:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "user_not_suspended",
                "message": "정지 상태가 아닌 사용자입니다.",
                "timestamp": timestamp,
            },
        )

    success = await suspension_models.unsuspend_user(user_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "user_not_found",
                "message": "사용자를 찾을 수 없습니다.",
                "timestamp": timestamp,
            },
        )

    return create_response(
        "USER_UNSUSPENDED",
        "사용자 정지가 해제되었습니다.",
        data={"user_id": user_id},
        timestamp=timestamp,
    )
