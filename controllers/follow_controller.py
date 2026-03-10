"""follow_controller: 사용자 팔로우 관련 컨트롤러 모듈."""

from fastapi import Request

from models.user_models import User
from schemas.common import create_response
from dependencies.request_context import get_request_timestamp
from services.follow_service import FollowService


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

    await FollowService.follow(
        user_id=current_user.id,
        target_id=target_user_id,
        actor_nickname=current_user.nickname,
        timestamp=timestamp,
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

    await FollowService.unfollow(
        user_id=current_user.id,
        target_id=target_user_id,
        timestamp=timestamp,
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

    data = await FollowService.get_following(
        user_id=current_user.id,
        offset=offset,
        limit=limit,
    )

    return create_response(
        "MY_FOLLOWING_LOADED",
        "팔로잉 목록을 조회했습니다.",
        data=data,
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

    data = await FollowService.get_followers(
        user_id=current_user.id,
        offset=offset,
        limit=limit,
    )

    return create_response(
        "MY_FOLLOWERS_LOADED",
        "팔로워 목록을 조회했습니다.",
        data=data,
        timestamp=timestamp,
    )
