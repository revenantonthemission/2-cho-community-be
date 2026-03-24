"""notification_router: 알림 API 라우터."""

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from core.dependencies.auth import get_current_user
from core.dependencies.request_context import get_request_timestamp
from modules.notification import controller as notification_controller
from modules.notification.setting_models import (
    get_notification_settings,
    update_notification_settings,
)
from modules.user.models import User
from schemas.common import create_response

router = APIRouter(prefix="/v1/notifications", tags=["notifications"])


class NotificationSettingsRequest(BaseModel):
    """알림 설정 요청 모델."""

    comment: bool | None = None
    like: bool | None = None
    mention: bool | None = None
    follow: bool | None = None
    bookmark: bool | None = None


@router.get("/")
async def get_notifications(
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
):
    return await notification_controller.get_notifications(current_user, request, offset, limit)


@router.get("/unread-count")
async def get_unread_count(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    return await notification_controller.get_unread_count(current_user, request)


@router.get("/settings")
async def get_settings(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """알림 유형별 설정 조회."""
    settings = await get_notification_settings(current_user.id)
    return create_response(
        "QUERY_SUCCESS",
        "알림 설정을 조회했습니다.",
        data={"settings": settings},
        timestamp=get_request_timestamp(request),
    )


@router.patch("/settings")
async def update_settings(
    body: NotificationSettingsRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """알림 유형별 설정 변경."""
    changes = {k: v for k, v in body.model_dump().items() if v is not None}
    updated = await update_notification_settings(current_user.id, changes)
    return create_response(
        "SETTINGS_UPDATED",
        "알림 설정이 변경되었습니다.",
        data={"settings": updated},
        timestamp=get_request_timestamp(request),
    )


# 정적 경로를 동적 경로보다 먼저 등록 (FastAPI 라우트 순서)
@router.patch("/read-all")
async def mark_all_as_read(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    return await notification_controller.mark_all_as_read(current_user, request)


@router.patch("/{notification_id}/read")
async def mark_as_read(
    notification_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    return await notification_controller.mark_as_read(notification_id, current_user, request)


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    return await notification_controller.delete_notification(notification_id, current_user, request)
