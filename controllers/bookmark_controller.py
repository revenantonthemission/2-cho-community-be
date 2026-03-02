"""bookmark_controller: 북마크 관련 컨트롤러 모듈."""

from fastapi import HTTPException, Request, status
from pymysql.err import IntegrityError

from models import post_models, bookmark_models
from models.user_models import User
from schemas.common import create_response
from dependencies.request_context import get_request_timestamp


async def bookmark_post(
    post_id: int,
    current_user: User,
    request: Request,
) -> dict:
    """게시글을 북마크에 추가합니다.

    Raises:
        HTTPException: 게시글 없으면 404, 이미 북마크했으면 409.
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

    try:
        await bookmark_models.add_bookmark(post_id, current_user.id)
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "already_bookmarked",
                "message": "이미 북마크한 게시글입니다.",
                "timestamp": timestamp,
            },
        )

    return create_response(
        "BOOKMARK_ADDED",
        "북마크가 추가되었습니다.",
        data={
            "bookmarks_count": await bookmark_models.get_post_bookmarks_count(
                post_id
            )
        },
        timestamp=timestamp,
    )


async def unbookmark_post(
    post_id: int,
    current_user: User,
    request: Request,
) -> dict:
    """북마크를 해제합니다.

    Raises:
        HTTPException: 게시글 없으면 404, 북마크 안했으면 404.
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

    removed = await bookmark_models.remove_bookmark(post_id, current_user.id)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "bookmark_not_found",
                "message": "북마크하지 않은 게시글입니다.",
                "timestamp": timestamp,
            },
        )

    return create_response(
        "BOOKMARK_REMOVED",
        "북마크가 해제되었습니다.",
        data={
            "bookmarks_count": await bookmark_models.get_post_bookmarks_count(
                post_id
            )
        },
        timestamp=timestamp,
    )
