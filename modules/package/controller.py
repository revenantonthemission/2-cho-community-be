"""package_controller: 패키지 관련 컨트롤러."""

from fastapi import HTTPException, Request, status
from pymysql.err import IntegrityError

from core.dependencies.request_context import get_request_timestamp
from core.utils.pagination import validate_pagination
from modules.package.models import ALLOWED_SORT_OPTIONS
from modules.package.review_models import ALLOWED_REVIEW_SORT_OPTIONS
from modules.package.schemas import (
    CreatePackageRequest,
    CreateReviewRequest,
    UpdatePackageRequest,
    UpdateReviewRequest,
)
from modules.package.service import PackageService
from modules.user.models import User
from schemas.common import create_response

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

    # 음수 offset은 DB 레벨에서도 거부되지만 명확한 에러 메시지를 위해 Controller에서 먼저 검사
    # 상한선(100)을 두어 단일 요청으로 과도한 데이터를 조회하는 것을 방지
    validate_pagination(offset, limit, timestamp)

    # 공백만 있는 검색어는 None으로 정규화
    if search is not None:
        search = search.strip() or None

    # 유효하지 않은 정렬 옵션은 기본값으로 폴백 — 400 에러 대신 관용적 처리로 UX 저해 방지
    if sort not in ALLOWED_SORT_OPTIONS:
        sort = "latest"

    result = await PackageService.get_packages(
        offset=offset,
        limit=limit,
        sort=sort,
        category=category,
        search=search,
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
        current_user.id,
        data,
        timestamp,
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

    # is_admin을 전달해 Service에서 작성자 본인 외 관리자도 수정 가능하도록 분기
    result = await PackageService.update_package(
        package_id,
        current_user.id,
        data,
        timestamp,
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

    validate_pagination(offset, limit, timestamp)

    # 리뷰 정렬 옵션은 패키지 목록과 별도로 관리 — 리뷰에는 '평점순' 등 추가 옵션이 있을 수 있음
    if sort not in ALLOWED_REVIEW_SORT_OPTIONS:
        sort = "latest"

    result = await PackageService.get_reviews(
        package_id,
        offset,
        limit,
        sort=sort,
        timestamp=timestamp,
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

    # IntegrityError는 DB의 unique 제약 위반 — 동일 사용자의 중복 리뷰를 409로 변환
    # from None으로 원인 체인을 숨겨 내부 DB 오류 정보가 응답에 노출되지 않도록 함
    try:
        review_id = await PackageService.create_review(
            package_id,
            current_user.id,
            data,
            timestamp,
        )
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "REVIEW_ALREADY_EXISTS",
                "message": "이미 이 패키지에 리뷰를 작성했습니다.",
                "timestamp": timestamp,
            },
        ) from None

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
        package_id,
        review_id,
        current_user.id,
        data,
        timestamp,
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

    # 관리자는 타인의 리뷰도 삭제 가능 — 부적절한 리뷰 제거를 위한 관리 기능
    await PackageService.delete_review(
        package_id,
        review_id,
        current_user.id,
        is_admin=current_user.is_admin,
        timestamp=timestamp,
    )

    return create_response(
        "REVIEW_DELETED",
        "리뷰가 삭제되었습니다.",
        timestamp=timestamp,
    )
