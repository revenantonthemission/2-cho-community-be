"""follow_controller: 사용자 팔로우 관련 컨트롤러 모듈."""

from fastapi import Request

from dependencies.request_context import get_request_timestamp
from models.user_models import User
from schemas.common import create_response
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

    # actor_nickname을 전달해 팔로우 알림 생성 시 닉네임을 별도 조회하지 않도록
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

    # 팔로우 관계가 없으면 404 — 멱등성 대신 명시적 오류로 클라이언트 버그를 조기에 노출
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


async def get_user_following(
    user_id: int,
    request: Request,
    offset: int = 0,
    limit: int = 10,
) -> dict:
    """특정 사용자의 팔로잉 목록을 조회합니다."""
    timestamp = get_request_timestamp(request)

    # 타인의 팔로잉 목록도 공개 — 프로필 페이지에서 소셜 그래프 탐색 지원
    data = await FollowService.get_following(
        user_id=user_id,
        offset=offset,
        limit=limit,
    )

    return create_response(
        "USER_FOLLOWING_LOADED",
        "팔로잉 목록을 조회했습니다.",
        data=data,
        timestamp=timestamp,
    )


async def get_user_followers(
    user_id: int,
    request: Request,
    offset: int = 0,
    limit: int = 10,
) -> dict:
    """특정 사용자의 팔로워 목록을 조회합니다."""
    timestamp = get_request_timestamp(request)

    # 타인의 팔로워 목록도 공개 — 팔로우 관계는 소셜 기능의 핵심 정보
    data = await FollowService.get_followers(
        user_id=user_id,
        offset=offset,
        limit=limit,
    )

    return create_response(
        "USER_FOLLOWERS_LOADED",
        "팔로워 목록을 조회했습니다.",
        data=data,
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

    # get_user_following과 동일 서비스 메서드 재사용 — current_user.id를 명시적으로 전달
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

    # 나를 팔로우한 사람 목록 — 알림 후 확인 흐름에서 주로 사용
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
