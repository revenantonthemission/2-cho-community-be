"""follow_controller: 사용자 팔로우 관련 컨트롤러 모듈."""

from fastapi import HTTPException, Request, status
from pymysql.err import IntegrityError

from models import follow_models
from models.user_models import User, get_user_by_id
from schemas.common import create_response
from dependencies.request_context import get_request_timestamp
from utils.formatters import format_datetime


async def follow_user(
    target_user_id: int,
    current_user: User,
    request: Request,
) -> dict:
    """사용자를 팔로우합니다.

    Raises:
        HTTPException: 자기 팔로우(400), 대상 없음(404), 이미 팔로우(409).
    """
    timestamp = get_request_timestamp(request)

    if target_user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "cannot_follow_self",
                "message": "자기 자신을 팔로우할 수 없습니다.",
                "timestamp": timestamp,
            },
        )

    target = await get_user_by_id(target_user_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "user_not_found", "timestamp": timestamp},
        )

    try:
        await follow_models.add_follow(current_user.id, target_user_id)
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "already_following",
                "message": "이미 팔로우한 사용자입니다.",
                "timestamp": timestamp,
            },
        )

    return create_response(
        "USER_FOLLOWED",
        "사용자를 팔로우했습니다.",
        timestamp=timestamp,
    )


async def unfollow_user(
    target_user_id: int,
    current_user: User,
    request: Request,
) -> dict:
    """팔로우를 해제합니다.

    Raises:
        HTTPException: 팔로우하지 않은 경우 404.
    """
    timestamp = get_request_timestamp(request)

    removed = await follow_models.remove_follow(current_user.id, target_user_id)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "follow_not_found",
                "message": "팔로우하지 않은 사용자입니다.",
                "timestamp": timestamp,
            },
        )

    return create_response(
        "USER_UNFOLLOWED",
        "팔로우가 해제되었습니다.",
        timestamp=timestamp,
    )


async def get_my_following(
    current_user: User,
    request: Request,
    offset: int = 0,
    limit: int = 10,
) -> dict:
    """팔로잉 목록을 조회합니다."""
    timestamp = get_request_timestamp(request)

    following, total_count = await follow_models.get_my_following(
        current_user.id, offset, limit
    )
    has_more = offset + limit < total_count

    for item in following:
        item["created_at"] = format_datetime(item["created_at"])

    return create_response(
        "MY_FOLLOWING_LOADED",
        "팔로잉 목록을 조회했습니다.",
        data={
            "following": following,
            "pagination": {"total_count": total_count, "has_more": has_more},
        },
        timestamp=timestamp,
    )


async def get_my_followers(
    current_user: User,
    request: Request,
    offset: int = 0,
    limit: int = 10,
) -> dict:
    """팔로워 목록을 조회합니다."""
    timestamp = get_request_timestamp(request)

    followers, total_count = await follow_models.get_my_followers(
        current_user.id, offset, limit
    )
    has_more = offset + limit < total_count

    for item in followers:
        item["created_at"] = format_datetime(item["created_at"])

    return create_response(
        "MY_FOLLOWERS_LOADED",
        "팔로워 목록을 조회했습니다.",
        data={
            "followers": followers,
            "pagination": {"total_count": total_count, "has_more": has_more},
        },
        timestamp=timestamp,
    )
