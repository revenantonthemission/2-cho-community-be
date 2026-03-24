"""comment_like_controller: 댓글 좋아요 관련 컨트롤러 모듈."""

from fastapi import Request

from core.dependencies.request_context import get_request_timestamp
from modules.post.comment_like_service import CommentLikeService
from modules.user.models import User
from schemas.common import create_response


async def like_comment(
    post_id: int,
    comment_id: int,
    current_user: User,
    request: Request,
) -> dict:
    """댓글에 좋아요를 추가합니다."""
    timestamp = get_request_timestamp(request)

    result = await CommentLikeService.like_comment(
        post_id=post_id,
        comment_id=comment_id,
        user_id=current_user.id,
        actor_nickname=current_user.nickname,
        timestamp=timestamp,
    )

    return create_response(
        "COMMENT_LIKE_ADDED",
        "댓글 좋아요가 추가되었습니다.",
        data=result,
        timestamp=timestamp,
    )


async def unlike_comment(
    post_id: int,
    comment_id: int,
    current_user: User,
    request: Request,
) -> dict:
    """댓글 좋아요를 취소합니다."""
    timestamp = get_request_timestamp(request)

    result = await CommentLikeService.unlike_comment(
        post_id=post_id,
        comment_id=comment_id,
        user_id=current_user.id,
        timestamp=timestamp,
    )

    return create_response(
        "COMMENT_LIKE_REMOVED",
        "댓글 좋아요가 취소되었습니다.",
        data=result,
        timestamp=timestamp,
    )
