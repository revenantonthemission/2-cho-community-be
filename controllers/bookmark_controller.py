"""bookmark_controller: 북마크 관련 컨트롤러 모듈."""

from fastapi import Request

from dependencies.request_context import get_request_timestamp
from models.user_models import User
from schemas.common import create_response
from services.bookmark_service import BookmarkService


async def bookmark_post(
    post_id: int,
    current_user: User,
    request: Request,
) -> dict:
    """게시글을 북마크에 추가합니다.

    Args:
        post_id: 북마크할 게시글 ID.
        current_user: 현재 인증된 사용자 객체.
        request: FastAPI Request 객체.

    Returns:
        북마크 개수가 포함된 응답 딕셔너리.
    """
    timestamp = get_request_timestamp(request)
    result = await BookmarkService.add_bookmark(post_id, current_user.id, current_user.nickname, timestamp)
    return create_response(
        "BOOKMARK_ADDED",
        "북마크가 추가되었습니다.",
        data=result,
        timestamp=timestamp,
    )


async def unbookmark_post(
    post_id: int,
    current_user: User,
    request: Request,
) -> dict:
    """북마크를 해제합니다.

    Args:
        post_id: 북마크 해제할 게시글 ID.
        current_user: 현재 인증된 사용자 객체.
        request: FastAPI Request 객체.

    Returns:
        북마크 개수가 포함된 응답 딕셔너리.
    """
    timestamp = get_request_timestamp(request)
    result = await BookmarkService.remove_bookmark(post_id, current_user.id, timestamp)
    return create_response(
        "BOOKMARK_REMOVED",
        "북마크가 해제되었습니다.",
        data=result,
        timestamp=timestamp,
    )
