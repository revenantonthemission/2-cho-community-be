"""exceptions: API 에러 응답 생성 헬퍼 모듈.

자주 사용되는 HTTP 에러 응답을 표준화된 형식으로 생성합니다.
"""

from __future__ import annotations

import logging
from typing import Literal

from fastapi import HTTPException, status

from core.utils.error_codes import ErrorCode

logger = logging.getLogger(__name__)


def not_found_error(resource: ErrorCode | str, timestamp: str) -> HTTPException:
    """리소스를 찾을 수 없을 때 404 에러를 생성합니다.

    Args:
        resource: 리소스 이름 또는 ErrorCode (예: 'user', ErrorCode.USER_NOT_FOUND).
        timestamp: 요청 타임스탬프.

    Returns:
        HTTPException: 404 Not Found 예외.
    """
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "error": f"{resource}_not_found",
            "timestamp": timestamp,
        },
    )


def forbidden_error(action: ErrorCode | str, timestamp: str, message: str | None = None) -> HTTPException:
    """권한이 없을 때 403 에러를 생성합니다.

    Args:
        action: 수행하려는 동작 또는 ErrorCode (예: 'edit', 'delete').
        timestamp: 요청 타임스탬프.
        message: 사용자에게 표시할 메시지 (선택).

    Returns:
        HTTPException: 403 Forbidden 예외.
    """
    detail = {
        "error": f"not_authorized_to_{action}",
        "timestamp": timestamp,
    }
    if message:
        detail["message"] = message
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=detail,
    )


def bad_request_error(error_code: ErrorCode | str, timestamp: str, message: str | None = None) -> HTTPException:
    """잘못된 요청에 대한 400 에러를 생성합니다.

    Args:
        error_code: 에러 코드 또는 ErrorCode (예: ErrorCode.NO_CHANGES_PROVIDED).
        timestamp: 요청 타임스탬프.
        message: 사용자에게 표시할 메시지 (선택).

    Returns:
        HTTPException: 400 Bad Request 예외.
    """
    detail = {
        "error": error_code,
        "timestamp": timestamp,
    }
    if message:
        detail["message"] = message
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=detail,
    )


def conflict_error(error_code: ErrorCode | str, timestamp: str, message: str) -> HTTPException:
    """409 Conflict 에러 (중복 좋아요, 북마크, 팔로우 등)

    Args:
        error_code: 에러 코드 또는 ErrorCode.
        timestamp: 요청 타임스탬프.
        message: 사용자에게 표시할 메시지.

    Returns:
        HTTPException: 409 Conflict 예외.
    """
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"error": error_code, "message": message, "timestamp": timestamp},
    )


async def safe_notify(
    *,
    user_id: int,
    notification_type: Literal["comment", "like", "mention", "follow", "bookmark", "reply", "badge_earned", "level_up"],
    actor_id: int,
    actor_nickname: str,
    post_id: int | None = None,
    comment_id: int | None = None,
) -> None:
    """알림 생성 (실패해도 주 작업에 영향 없음)"""
    from modules.notification.models import create_notification

    try:
        await create_notification(
            user_id=user_id,
            notification_type=notification_type,
            actor_id=actor_id,
            actor_nickname=actor_nickname,
            post_id=post_id,
            comment_id=comment_id,
        )
    except Exception:
        logger.warning("알림 생성 실패", exc_info=True)
