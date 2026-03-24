"""suspension_controller: 계정 정지 관련 컨트롤러."""

from fastapi import Request

from core.dependencies.request_context import get_request_timestamp
from modules.admin.suspension_schemas import SuspendUserRequest
from modules.admin.suspension_service import SuspensionService
from modules.user.models import User
from schemas.common import create_response


async def suspend_user(
    user_id: int,
    suspend_data: SuspendUserRequest,
    current_user: User,
    request: Request,
) -> dict:
    """사용자를 정지합니다 (관리자 전용)."""
    timestamp = get_request_timestamp(request)

    data = await SuspensionService.suspend_user(
        user_id=user_id,
        duration_days=suspend_data.duration_days,
        reason=suspend_data.reason,
        admin_user_id=current_user.id,
        timestamp=timestamp,
    )

    return create_response(
        "USER_SUSPENDED",
        "사용자가 정지되었습니다.",
        data=data,
        timestamp=timestamp,
    )


async def unsuspend_user(
    user_id: int,
    current_user: User,
    request: Request,
) -> dict:
    """사용자 정지를 해제합니다 (관리자 전용)."""
    timestamp = get_request_timestamp(request)

    await SuspensionService.unsuspend_user(
        user_id=user_id,
        timestamp=timestamp,
    )

    return create_response(
        "USER_UNSUSPENDED",
        "사용자 정지가 해제되었습니다.",
        data={"user_id": user_id},
        timestamp=timestamp,
    )
