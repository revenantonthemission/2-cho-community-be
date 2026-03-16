"""package_controller: 패키지 관련 컨트롤러."""

from fastapi import HTTPException, Request, status
from pymysql.err import IntegrityError

from dependencies.request_context import get_request_timestamp
from models.package_models import ALLOWED_SORT_OPTIONS
from models.package_review_models import ALLOWED_REVIEW_SORT_OPTIONS
from models.user_models import User
from schemas.common import create_response
from schemas.package_schemas import (
    CreatePackageRequest,
    CreateReviewRequest,
    UpdatePackageRequest,
    UpdateReviewRequest,
)
from services.package_service import PackageService


# ============ 패키지 관련 핸들러 ============


async def get_packages(
    offset: int,
    limit: int,
    request: Request,
    sort: str = "latest",
    category: str | None = None,
    search: str | None = None,
) -> dict:
    """패키지 목록을 조회합니다."""
    timestamp = get_request_timestamp(request)

    if offset < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_offset",
                "message": "시작 위치는 0 이상이어야 합니다.",
                "timestamp": timestamp,
            },
        )

    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_limit",
                "message": "페이지 크기는 1~100 사이여야 합니다.",
                "timestamp": timestamp,
            },
        )

    # 공백만 있는 검색어는 None으로 정규화
    if search is not None:
        search = search.strip() or None

    # 유효하지 않은 정렬 옵션은 기본값으로 대체
    if sort not in ALLOWED_SORT_OPTIONS:
        sort = "latest"

    result = await PackageService.get_packages(
        offset=offset, limit=limit, sort=sort,
        category=category, search=search,
    )

    return create_response(
        "PACKAGES_RETRIEVED",
        "패키지 목록 조회에 성공했습니다.",
        data=result,
        timestamp=timestamp,
    )


async def get_package(
    package_id: int,
    request: Request,
) -> dict:
    """패키지 상세 정보를 조회합니다."""
    timestamp = get_request_timestamp(request)

    result = await PackageService.get_package(package_id, timestamp)

    return create_response(
        "PACKAGE_RETRIEVED",
        "패키지 조회에 성공했습니다.",
        data=result,
        timestamp=timestamp,
    )


async def create_package(
    data: CreatePackageRequest,
    current_user: User,
    request: Request,
) -> dict:
    """새 패키지를 등록합니다."""
    timestamp = get_request_timestamp(request)

    package_id = await PackageService.create_package(
        current_user.id, data, timestamp,
    )

    return create_response(
        "PACKAGE_CREATED",
        "패키지가 등록되었습니다.",
        data={"package_id": package_id},
        timestamp=timestamp,
    )


async def update_package(
    package_id: int,
    data: UpdatePackageRequest,
    current_user: User,
    request: Request,
) -> dict:
    """패키지 정보를 수정합니다."""
    timestamp = get_request_timestamp(request)

    result = await PackageService.update_package(
        package_id, current_user.id, data, timestamp,
        is_admin=current_user.is_admin,
    )

    return create_response(
        "PACKAGE_UPDATED",
        "패키지가 수정되었습니다.",
        data=result,
        timestamp=timestamp,
    )


# ============ 리뷰 관련 핸들러 ============


async def get_reviews(
    package_id: int,
    offset: int,
    limit: int,
    request: Request,
    sort: str = "latest",
) -> dict:
    """패키지 리뷰 목록을 조회합니다."""
    timestamp = get_request_timestamp(request)

    if offset < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_offset",
                "message": "시작 위치는 0 이상이어야 합니다.",
                "timestamp": timestamp,
            },
        )

    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_limit",
                "message": "페이지 크기는 1~100 사이여야 합니다.",
                "timestamp": timestamp,
            },
        )

    if sort not in ALLOWED_REVIEW_SORT_OPTIONS:
        sort = "latest"

    result = await PackageService.get_reviews(
        package_id, offset, limit, sort=sort, timestamp=timestamp,
    )

    return create_response(
        "REVIEWS_RETRIEVED",
        "리뷰 목록 조회에 성공했습니다.",
        data=result,
        timestamp=timestamp,
    )


async def create_review(
    package_id: int,
    data: CreateReviewRequest,
    current_user: User,
    request: Request,
) -> dict:
    """패키지 리뷰를 작성합니다.

    IntegrityError(중복 리뷰)를 409로 변환합니다.
    """
    timestamp = get_request_timestamp(request)

    try:
        review_id = await PackageService.create_review(
            package_id, current_user.id, data, timestamp,
        )
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "REVIEW_ALREADY_EXISTS",
                "message": "이미 이 패키지에 리뷰를 작성했습니다.",
                "timestamp": timestamp,
            },
        )

    return create_response(
        "REVIEW_CREATED",
        "리뷰가 작성되었습니다.",
        data={"review_id": review_id},
        timestamp=timestamp,
    )


async def update_review(
    package_id: int,
    review_id: int,
    data: UpdateReviewRequest,
    current_user: User,
    request: Request,
) -> dict:
    """리뷰를 수정합니다."""
    timestamp = get_request_timestamp(request)

    result = await PackageService.update_review(
        package_id, review_id, current_user.id, data, timestamp,
    )

    return create_response(
        "REVIEW_UPDATED",
        "리뷰가 수정되었습니다.",
        data=result,
        timestamp=timestamp,
    )


async def delete_review(
    package_id: int,
    review_id: int,
    current_user: User,
    request: Request,
) -> dict:
    """리뷰를 삭제합니다."""
    timestamp = get_request_timestamp(request)

    await PackageService.delete_review(
        package_id, review_id, current_user.id,
        is_admin=current_user.is_admin, timestamp=timestamp,
    )

    return create_response(
        "REVIEW_DELETED",
        "리뷰가 삭제되었습니다.",
        timestamp=timestamp,
    )
