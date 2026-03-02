"""notification_router: 알림 API 라우터."""

from fastapi import APIRouter, Depends, Query, Request

from controllers import notification_controller
from dependencies.auth import get_current_user
from models.user_models import User

router = APIRouter(prefix="/v1/notifications", tags=["notifications"])


@router.get("/")
async def get_notifications(
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
):
    return await notification_controller.get_notifications(
        current_user, request, offset, limit
    )


@router.get("/unread-count")
async def get_unread_count(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    return await notification_controller.get_unread_count(current_user, request)


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
    return await notification_controller.mark_as_read(
        notification_id, current_user, request
    )


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    return await notification_controller.delete_notification(
        notification_id, current_user, request
    )
