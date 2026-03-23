"""activity_controller: 내 활동 관련 컨트롤러."""

from fastapi import Request

from dependencies.request_context import get_request_timestamp
from models import activity_models
from models.user_models import User
from schemas.common import create_response


async def get_my_posts(current_user: User, request: Request, offset: int = 0, limit: int = 10) -> dict:
    """내가 쓴 글 목록을 조회합니다."""
    timestamp = get_request_timestamp(request)

    posts, total_count = await activity_models.get_my_posts(current_user.id, offset, limit)
    # soft delete된 게시글은 모델 레이어에서 자동 제외 — 활동 내역에도 삭제된 글은 노출하지 않음
    has_more = offset + limit < total_count

    return create_response(
        "MY_POSTS_LOADED",
        "내가 쓴 글 목록을 조회했습니다.",
        data={
            "posts": posts,
            "pagination": {"total_count": total_count, "has_more": has_more},
        },
        timestamp=timestamp,
    )


async def get_my_comments(current_user: User, request: Request, offset: int = 0, limit: int = 10) -> dict:
    """내가 쓴 댓글 목록을 조회합니다."""
    timestamp = get_request_timestamp(request)

    comments, total_count = await activity_models.get_my_comments(current_user.id, offset, limit)
    # 댓글이 달린 게시글이 삭제되어도 댓글 자체는 표시 — 모델에서 JOIN 방식으로 결정
    has_more = offset + limit < total_count

    return create_response(
        "MY_COMMENTS_LOADED",
        "내가 쓴 댓글 목록을 조회했습니다.",
        data={
            "comments": comments,
            "pagination": {"total_count": total_count, "has_more": has_more},
        },
        timestamp=timestamp,
    )


async def get_my_likes(current_user: User, request: Request, offset: int = 0, limit: int = 10) -> dict:
    """좋아요한 글 목록을 조회합니다."""
    timestamp = get_request_timestamp(request)

    posts, total_count = await activity_models.get_my_likes(current_user.id, offset, limit)
    # 좋아요한 게시글이 삭제된 경우 목록에서 자동 제외 — 모델에서 soft delete 조건 적용
    has_more = offset + limit < total_count

    return create_response(
        "MY_LIKES_LOADED",
        "좋아요한 글 목록을 조회했습니다.",
        data={
            "posts": posts,
            "pagination": {"total_count": total_count, "has_more": has_more},
        },
        timestamp=timestamp,
    )


async def get_my_bookmarks(current_user: User, request: Request, offset: int = 0, limit: int = 10) -> dict:
    """북마크한 글 목록을 조회합니다."""
    timestamp = get_request_timestamp(request)

    posts, total_count = await activity_models.get_my_bookmarks(current_user.id, offset, limit)
    # 북마크한 게시글이 삭제된 경우 목록에서 자동 제외 — 모델에서 soft delete 조건 적용
    has_more = offset + limit < total_count

    return create_response(
        "MY_BOOKMARKS_LOADED",
        "북마크한 글 목록을 조회했습니다.",
        data={
            "posts": posts,
            "pagination": {"total_count": total_count, "has_more": has_more},
        },
        timestamp=timestamp,
    )
