"""reputation_router: 평판 시스템 API 라우터 모듈."""

from fastapi import APIRouter, Path, Query, Request, status

from modules.reputation import controller as reputation_controller

reputation_router = APIRouter(tags=["reputation"])
"""평판 시스템 관련 라우터 인스턴스."""


@reputation_router.get("/v1/users/{user_id}/reputation/", status_code=status.HTTP_200_OK)
async def get_user_reputation(
    request: Request,
    user_id: int = Path(description="조회할 사용자 ID"),
) -> dict:
    """사용자 평판 요약 정보(점수, 신뢰 등급, 배지 수)를 조회합니다.

    Args:
        request: FastAPI Request 객체.
        user_id: 조회할 사용자 ID.

    Returns:
        사용자 평판 요약 정보가 포함된 응답.
    """
    return await reputation_controller.get_user_reputation(user_id, request)


@reputation_router.get("/v1/users/{user_id}/reputation/history/", status_code=status.HTTP_200_OK)
async def get_user_reputation_history(
    request: Request,
    user_id: int = Path(description="조회할 사용자 ID"),
    offset: int = Query(0, ge=0, description="시작 위치 (0부터 시작)"),
    limit: int = Query(20, ge=1, le=100, description="조회할 이벤트 수"),
) -> dict:
    """사용자의 평판 이벤트 히스토리를 최신순으로 조회합니다.

    Args:
        request: FastAPI Request 객체.
        user_id: 조회할 사용자 ID.
        offset: 시작 위치.
        limit: 조회할 이벤트 수.

    Returns:
        평판 이벤트 목록과 총 개수가 포함된 응답.
    """
    return await reputation_controller.get_user_reputation_history(user_id, offset, limit, request)


@reputation_router.get("/v1/users/{user_id}/badges/", status_code=status.HTTP_200_OK)
async def get_user_badges(
    request: Request,
    user_id: int = Path(description="조회할 사용자 ID"),
) -> dict:
    """사용자가 획득한 배지 목록을 조회합니다.

    Args:
        request: FastAPI Request 객체.
        user_id: 조회할 사용자 ID.

    Returns:
        사용자 배지 목록이 포함된 응답.
    """
    return await reputation_controller.get_user_badges(user_id, request)


@reputation_router.get("/v1/badges/", status_code=status.HTTP_200_OK)
async def get_all_badges(
    request: Request,
) -> dict:
    """모든 배지 정의 목록을 조회합니다.

    Args:
        request: FastAPI Request 객체.

    Returns:
        배지 정의 목록이 포함된 응답.
    """
    return await reputation_controller.get_all_badges(request)


@reputation_router.get("/v1/trust-levels/", status_code=status.HTTP_200_OK)
async def get_trust_levels(
    request: Request,
) -> dict:
    """신뢰 등급 정의 목록을 조회합니다.

    Args:
        request: FastAPI Request 객체.

    Returns:
        신뢰 등급 목록이 포함된 응답.
    """
    return await reputation_controller.get_trust_levels(request)
