"""package_router: 패키지 관련 라우터 모듈."""

from fastapi import APIRouter, Depends, Path, Query, Request, status

from controllers import package_controller
from dependencies.auth import get_optional_user, require_verified_email
from models.user_models import User
from schemas.package_schemas import (
    CreatePackageRequest,
    CreateReviewRequest,
    UpdatePackageRequest,
    UpdateReviewRequest,
)

package_router = APIRouter(prefix="/v1/packages", tags=["packages"])
"""패키지 관련 라우터 인스턴스."""


# ============ 패키지 라우터 ============


@package_router.get("/", status_code=status.HTTP_200_OK)
async def get_packages(
    request: Request,
    offset: int = Query(0, ge=0, description="시작 위치 (0부터 시작)"),
    limit: int = Query(10, ge=1, le=100, description="조회할 패키지 수"),
    sort: str = Query("latest", description="정렬: latest, name, rating, reviews"),
    category: str | None = Query(None, description="카테고리 필터"),
    search: str | None = Query(None, max_length=100, description="검색어 (패키지명/설명)"),
    _current_user: User | None = Depends(get_optional_user),
) -> dict:
    """패키지 목록을 조회합니다.

    Args:
        request: FastAPI Request 객체.
        offset: 시작 위치.
        limit: 조회할 패키지 수.
        sort: 정렬 옵션.
        category: 카테고리 필터.
        search: 검색어.

    Returns:
        패키지 목록과 페이지네이션 정보가 포함된 응답.
    """
    return await package_controller.get_packages(
        offset,
        limit,
        request,
        sort=sort,
        category=category,
        search=search,
    )


@package_router.get("/{package_id}", status_code=status.HTTP_200_OK)
async def get_package(
    request: Request,
    package_id: int = Path(ge=1, description="패키지 ID"),
    _current_user: User | None = Depends(get_optional_user),
) -> dict:
    """패키지 상세 정보를 조회합니다.

    Args:
        request: FastAPI Request 객체.
        package_id: 조회할 패키지 ID.

    Returns:
        패키지 상세 정보가 포함된 응답.
    """
    return await package_controller.get_package(package_id, request)


@package_router.post("/", status_code=status.HTTP_201_CREATED)
async def create_package(
    data: CreatePackageRequest,
    request: Request,
    current_user: User = Depends(require_verified_email),
) -> dict:
    """새 패키지를 등록합니다.

    Args:
        data: 패키지 등록 정보.
        request: FastAPI Request 객체.
        current_user: 현재 인증된 사용자.

    Returns:
        생성된 패키지 ID가 포함된 응답.
    """
    return await package_controller.create_package(data, current_user, request)


@package_router.put("/{package_id}", status_code=status.HTTP_200_OK)
async def update_package(
    data: UpdatePackageRequest,
    request: Request,
    package_id: int = Path(ge=1, description="패키지 ID"),
    current_user: User = Depends(require_verified_email),
) -> dict:
    """패키지 정보를 수정합니다.

    Args:
        data: 수정할 패키지 정보.
        request: FastAPI Request 객체.
        package_id: 수정할 패키지 ID.
        current_user: 현재 인증된 사용자.

    Returns:
        수정된 패키지 정보가 포함된 응답.
    """
    return await package_controller.update_package(
        package_id,
        data,
        current_user,
        request,
    )


# ============ 리뷰 라우터 ============


@package_router.get("/{package_id}/reviews", status_code=status.HTTP_200_OK)
async def get_reviews(
    request: Request,
    package_id: int = Path(ge=1, description="패키지 ID"),
    offset: int = Query(0, ge=0, description="시작 위치"),
    limit: int = Query(10, ge=1, le=100, description="조회할 리뷰 수"),
    sort: str = Query("latest", description="정렬: latest, oldest, highest, lowest"),
    _current_user: User | None = Depends(get_optional_user),
) -> dict:
    """패키지 리뷰 목록을 조회합니다.

    Args:
        request: FastAPI Request 객체.
        package_id: 패키지 ID.
        offset: 시작 위치.
        limit: 조회할 리뷰 수.
        sort: 정렬 옵션.

    Returns:
        리뷰 목록과 페이지네이션 정보가 포함된 응답.
    """
    return await package_controller.get_reviews(
        package_id,
        offset,
        limit,
        request,
        sort=sort,
    )


@package_router.post(
    "/{package_id}/reviews",
    status_code=status.HTTP_201_CREATED,
)
async def create_review(
    data: CreateReviewRequest,
    request: Request,
    package_id: int = Path(ge=1, description="패키지 ID"),
    current_user: User = Depends(require_verified_email),
) -> dict:
    """패키지 리뷰를 작성합니다.

    Args:
        data: 리뷰 작성 정보.
        request: FastAPI Request 객체.
        package_id: 패키지 ID.
        current_user: 현재 인증된 사용자.

    Returns:
        생성된 리뷰 ID가 포함된 응답.
    """
    return await package_controller.create_review(
        package_id,
        data,
        current_user,
        request,
    )


@package_router.put(
    "/{package_id}/reviews/{review_id}",
    status_code=status.HTTP_200_OK,
)
async def update_review(
    data: UpdateReviewRequest,
    request: Request,
    package_id: int = Path(ge=1, description="패키지 ID"),
    review_id: int = Path(ge=1, description="리뷰 ID"),
    current_user: User = Depends(require_verified_email),
) -> dict:
    """리뷰를 수정합니다.

    Args:
        data: 수정할 리뷰 정보.
        request: FastAPI Request 객체.
        package_id: 패키지 ID.
        review_id: 수정할 리뷰 ID.
        current_user: 현재 인증된 사용자.

    Returns:
        수정된 리뷰 정보가 포함된 응답.
    """
    return await package_controller.update_review(
        package_id,
        review_id,
        data,
        current_user,
        request,
    )


@package_router.delete(
    "/{package_id}/reviews/{review_id}",
    status_code=status.HTTP_200_OK,
)
async def delete_review(
    request: Request,
    package_id: int = Path(ge=1, description="패키지 ID"),
    review_id: int = Path(ge=1, description="리뷰 ID"),
    current_user: User = Depends(require_verified_email),
) -> dict:
    """리뷰를 삭제합니다.

    Args:
        request: FastAPI Request 객체.
        package_id: 패키지 ID.
        review_id: 삭제할 리뷰 ID.
        current_user: 현재 인증된 사용자.

    Returns:
        삭제 성공 응답.
    """
    return await package_controller.delete_review(
        package_id,
        review_id,
        current_user,
        request,
    )
