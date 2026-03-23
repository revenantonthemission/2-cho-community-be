"""like_controller: 좋아요 관련 컨트롤러 모듈."""

from fastapi import Request

from dependencies.request_context import get_request_timestamp
from models.user_models import User
from schemas.common import create_response
from services.like_service import LikeService


async def like_post(
    post_id: int,
    current_user: User,
    request: Request,
) -> dict:
    """게시글에 좋아요를 추가합니다.

    Args:
        post_id: 좋아요할 게시글 ID.
        current_user: 현재 인증된 사용자 객체.
        request: FastAPI Request 객체.

    Returns:
        좋아요 개수가 포함된 응답 딕셔너리.
    """
    timestamp = get_request_timestamp(request)
    result = await LikeService.like_post(post_id, current_user.id, current_user.nickname, timestamp)
    return create_response(
        "LIKE_ADDED",
        "좋아요가 추가되었습니다.",
        data=result,
        timestamp=timestamp,
    )


async def unlike_post(
    post_id: int,
    current_user: User,
    request: Request,
) -> dict:
    """좋아요를 취소합니다.

    Args:
        post_id: 좋아요 취소할 게시글 ID.
        current_user: 현재 인증된 사용자 객체.
        request: FastAPI Request 객체.

    Returns:
        좋아요 개수가 포함된 응답 딕셔너리.
    """
    timestamp = get_request_timestamp(request)
    result = await LikeService.unlike_post(post_id, current_user.id, timestamp)
    return create_response(
        "LIKE_REMOVED",
        "좋아요가 취소되었습니다.",
        data=result,
        timestamp=timestamp,
    )
