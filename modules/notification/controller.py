"""notification_controller: 알림 관련 컨트롤러."""

from fastapi import Request
from fastapi.responses import JSONResponse, Response

from core.dependencies.request_context import get_request_timestamp
from core.utils.exceptions import not_found_error
from modules.notification import models as notification_models
from modules.user.models import User
from schemas.common import create_response


async def get_notifications(current_user: User, request: Request, offset: int = 0, limit: int = 20) -> dict:
    """내 알림 목록을 조회합니다."""
    timestamp = get_request_timestamp(request)
    notifications, total_count = await notification_models.get_notifications(current_user.id, offset, limit)
    # has_more: FE가 "더 보기" 버튼 렌더링 여부를 결정하기 위해 사용
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
    # ETag에 user_id 포함 — 공유 캐시에서 다른 사용자의 응답이 섞이는 것을 방지
    latest_id = result["latest"]["notification_id"] if result["latest"] else 0
    etag = f'W/"{current_user.id}-{result["unread_count"]}-{latest_id}"'

    # 변경 없으면 304 — 폴링 주기가 짧을 때 불필요한 응답 페이로드 전송 방지
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304)

    timestamp = get_request_timestamp(request)
    body = create_response(
        "UNREAD_COUNT",
        "읽지 않은 알림 수를 조회했습니다.",
        data=result,
        timestamp=timestamp,
    )
    # Cache-Control: no-cache — 캐시 저장은 허용하되 반드시 ETag 검증 후 사용하도록
    return JSONResponse(
        content=body,
        headers={"ETag": etag, "Cache-Control": "no-cache"},
    )


async def mark_as_read(notification_id: int, current_user: User, request: Request) -> dict:
    """알림을 읽음 처리합니다."""
    timestamp = get_request_timestamp(request)
    # user_id 조건 포함 — 타인의 알림을 읽음 처리하려는 시도를 404로 차단
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
    # 처리된 수를 응답에 포함 — 클라이언트가 뱃지 카운터를 즉시 0으로 리셋할 수 있도록
    count = await notification_models.mark_all_as_read(current_user.id)
    return create_response(
        "ALL_NOTIFICATIONS_READ",
        f"{count}개의 알림을 읽음 처리했습니다.",
        timestamp=timestamp,
    )


async def delete_notification(notification_id: int, current_user: User, request: Request) -> dict:
    """알림을 삭제합니다."""
    timestamp = get_request_timestamp(request)
    # user_id 조건 포함 — 타인의 알림을 삭제하려는 시도를 404로 차단 (권한 오류 대신 존재하지 않는 것처럼 처리)
    success = await notification_models.delete_notification(notification_id, current_user.id)
    if not success:
        raise not_found_error("notification", timestamp)
    return create_response(
        "NOTIFICATION_DELETED",
        "알림을 삭제했습니다.",
        timestamp=timestamp,
    )
