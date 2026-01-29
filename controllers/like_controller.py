"""like_controller: 좋아요 관련 컨트롤러 모듈."""

from fastapi import HTTPException, Request, status
from models import post_models, like_models
from models.user_models import User
from dependencies.request_context import get_request_timestamp


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

    Raises:
        HTTPException: 게시글 없으면 404, 이미 좋아요했으면 409.
    """
    timestamp = get_request_timestamp(request)

    post = await post_models.get_post_by_id(post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "post_not_found",
                "timestamp": timestamp,
            },
        )

    # 이미 좋아요를 눌렀는지 확인
    existing_like = await like_models.get_like(post_id, current_user.id)
    if existing_like:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "already_liked",
                "message": "이미 좋아요를 누른 게시글입니다.",
                "timestamp": timestamp,
            },
        )

    await like_models.add_like(post_id, current_user.id)

    return {
        "code": "LIKE_ADDED",
        "message": "좋아요가 추가되었습니다.",
        "data": {
            "likes_count": await like_models.get_post_likes_count(post_id),
        },
        "errors": [],
        "timestamp": timestamp,
    }


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

    Raises:
        HTTPException: 게시글 없으면 404, 좋아요 안했으면 404.
    """
    timestamp = get_request_timestamp(request)

    post = await post_models.get_post_by_id(post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "post_not_found",
                "timestamp": timestamp,
            },
        )

    # 좋아요를 눌렀는지 확인
    existing_like = await like_models.get_like(post_id, current_user.id)
    if not existing_like:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "like_not_found",
                "message": "좋아요를 누르지 않은 게시글입니다.",
                "timestamp": timestamp,
            },
        )

    await like_models.remove_like(post_id, current_user.id)

    return {
        "code": "LIKE_REMOVED",
        "message": "좋아요가 취소되었습니다.",
        "data": {
            "likes_count": await like_models.get_post_likes_count(post_id),
        },
        "errors": [],
        "timestamp": timestamp,
    }
