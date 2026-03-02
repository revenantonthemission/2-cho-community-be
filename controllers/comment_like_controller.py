"""comment_like_controller: 댓글 좋아요 관련 컨트롤러 모듈."""

import logging

from fastapi import HTTPException, Request, status
from pymysql.err import IntegrityError

from models import post_models, comment_like_models
from models.comment_models import get_comment_by_id
from models.user_models import User
from schemas.common import create_response
from dependencies.request_context import get_request_timestamp

logger = logging.getLogger(__name__)


async def like_comment(
    post_id: int,
    comment_id: int,
    current_user: User,
    request: Request,
) -> dict:
    """댓글에 좋아요를 추가합니다.

    Raises:
        HTTPException: 게시글/댓글 없으면 404, 이미 좋아요했으면 409.
    """
    timestamp = get_request_timestamp(request)

    # 게시글 존재 확인
    post = await post_models.get_post_by_id(post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "post_not_found", "timestamp": timestamp},
        )

    # 댓글 존재 + 해당 게시글 소속 확인
    comment = await get_comment_by_id(comment_id)
    if not comment or comment.post_id != post_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "comment_not_found", "timestamp": timestamp},
        )

    try:
        await comment_like_models.add_comment_like(comment_id, current_user.id)
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "already_liked_comment",
                "message": "이미 좋아요를 누른 댓글입니다.",
                "timestamp": timestamp,
            },
        )

    # 알림 생성 (실패해도 좋아요에 영향 없음)
    try:
        from models import notification_models

        if comment.author_id and comment.author_id != current_user.id:
            await notification_models.create_notification(
                user_id=comment.author_id,
                notification_type="like",
                post_id=post_id,
                actor_id=current_user.id,
                comment_id=comment_id,
            )
    except Exception:
        logger.warning("댓글 좋아요 알림 생성 실패", exc_info=True)

    return create_response(
        "COMMENT_LIKE_ADDED",
        "댓글 좋아요가 추가되었습니다.",
        data={
            "likes_count": await comment_like_models.get_comment_likes_count(
                comment_id
            )
        },
        timestamp=timestamp,
    )


async def unlike_comment(
    post_id: int,
    comment_id: int,
    current_user: User,
    request: Request,
) -> dict:
    """댓글 좋아요를 취소합니다.

    Raises:
        HTTPException: 게시글/댓글 없으면 404, 좋아요 안했으면 404.
    """
    timestamp = get_request_timestamp(request)

    post = await post_models.get_post_by_id(post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "post_not_found", "timestamp": timestamp},
        )

    comment = await get_comment_by_id(comment_id)
    if not comment or comment.post_id != post_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "comment_not_found", "timestamp": timestamp},
        )

    removed = await comment_like_models.remove_comment_like(
        comment_id, current_user.id
    )
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "comment_like_not_found",
                "message": "좋아요를 누르지 않은 댓글입니다.",
                "timestamp": timestamp,
            },
        )

    return create_response(
        "COMMENT_LIKE_REMOVED",
        "댓글 좋아요가 취소되었습니다.",
        data={
            "likes_count": await comment_like_models.get_comment_likes_count(
                comment_id
            )
        },
        timestamp=timestamp,
    )
