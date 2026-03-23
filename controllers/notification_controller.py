"""notification_controller: 알림 관련 컨트롤러."""

from fastapi import Request
from fastapi.responses import JSONResponse, Response

from dependencies.request_context import get_request_timestamp
from models import notification_models
from models.user_models import User
from schemas.common import create_response
from utils.exceptions import not_found_error


async def get_notifications(current_user: User, request: Request, offset: int = 0, limit: int = 20) -> dict:
    """내 알림 목록을 조회합니다."""
    timestamp = get_request_timestamp(request)
    notifications, total_count = await notification_models.get_notifications(current_user.id, offset, limit)
    has_more = offset + limit < total_count
    return create_response(
        "NOTIFICATIONS_LOADED",
        "알림 목록을 조회했습니다.",
        data={
            "notifications": notifications,
            "pagination": {"total_count": total_count, "has_more": has_more},
        },
        timestamp=timestamp,
    )


async def get_unread_count(current_user: User, request: Request) -> JSONResponse | Response:
    """읽지 않은 알림 수 + 최신 알림 1건을 조회합니다.

    ETag 기반 캐싱: unread_count와 latest.notification_id로 ETag 생성.
    변경 없으면 304 Not Modified 반환하여 응답 크기 절감.
    """
    result = await notification_models.get_unread_count_with_latest(current_user.id)

    # ETag: count + 최신 알림 ID 조합
    latest_id = result["latest"]["notification_id"] if result["latest"] else 0
    etag = f'W/"{current_user.id}-{result["unread_count"]}-{latest_id}"'

    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304)

    timestamp = get_request_timestamp(request)
    body = create_response(
        "UNREAD_COUNT",
        "읽지 않은 알림 수를 조회했습니다.",
        data=result,
        timestamp=timestamp,
    )
    return JSONResponse(
        content=body,
        headers={"ETag": etag, "Cache-Control": "no-cache"},
    )


async def mark_as_read(notification_id: int, current_user: User, request: Request) -> dict:
    """알림을 읽음 처리합니다."""
    timestamp = get_request_timestamp(request)
    success = await notification_models.mark_as_read(notification_id, current_user.id)
    if not success:
        raise not_found_error("notification", timestamp)
    return create_response(
        "NOTIFICATION_READ",
        "알림을 읽음 처리했습니다.",
        timestamp=timestamp,
    )


async def mark_all_as_read(current_user: User, request: Request) -> dict:
    """모든 알림을 읽음 처리합니다."""
    timestamp = get_request_timestamp(request)
    count = await notification_models.mark_all_as_read(current_user.id)
    return create_response(
        "ALL_NOTIFICATIONS_READ",
        f"{count}개의 알림을 읽음 처리했습니다.",
        timestamp=timestamp,
    )


async def delete_notification(notification_id: int, current_user: User, request: Request) -> dict:
    """알림을 삭제합니다."""
    timestamp = get_request_timestamp(request)
    success = await notification_models.delete_notification(notification_id, current_user.id)
    if not success:
        raise not_found_error("notification", timestamp)
    return create_response(
        "NOTIFICATION_DELETED",
        "알림을 삭제했습니다.",
        timestamp=timestamp,
    )
