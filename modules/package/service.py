"""package_service: 패키지 관련 비즈니스 로직."""

from core.utils.exceptions import bad_request_error, forbidden_error, not_found_error
from core.utils.formatters import format_datetime
from modules.package import models as package_models
from modules.package import review_models as package_review_models
from modules.package.schemas import (
    CreatePackageRequest,
    CreateReviewRequest,
    UpdatePackageRequest,
    UpdateReviewRequest,
)


class PackageService:
    """패키지 관리 서비스."""

    @staticmethod
    async def get_packages(
        offset: int,
        limit: int,
        sort: str = "latest",
        category: str | None = None,
        search: str | None = None,
    ) -> dict:
        """패키지 목록을 조회합니다.

        Args:
            offset: 시작 위치.
            limit: 조회할 개수.
            sort: 정렬 옵션.
            category: 카테고리 필터.
            search: 검색어.

        Returns:
            패키지 목록과 페이지네이션 정보.
        """
        packages = await package_models.get_packages_with_stats(
            offset=offset,
            limit=limit,
            sort=sort,
            category=category,
            search=search,
        )
        total_count = await package_models.get_packages_count(
            category=category,
            search=search,
        )
        has_more = offset + limit < total_count

        return {
            "packages": packages,
            "pagination": {
                "offset": offset,
                "limit": limit,
                "total_count": total_count,
                "has_more": has_more,
            },
        }

    @staticmethod
    async def get_package(package_id: int, timestamp: str) -> dict:
        """패키지 상세 정보를 조회합니다.

        Args:
            package_id: 패키지 ID.
            timestamp: 요청 타임스탬프.

        Returns:
            패키지 상세 정보.
        """
        package = await package_models.get_package_by_id(package_id)
        if not package:
            raise not_found_error("package", timestamp)

        # 리뷰 통계
        reviews_count = await package_review_models.get_reviews_count(package_id)

        return {
            "package_id": package.id,
            "name": package.name,
            "display_name": package.display_name,
            "description": package.description,
            "homepage_url": package.homepage_url,
            "category": package.category,
            "package_manager": package.package_manager,
            "created_by": package.created_by,
            "created_at": format_datetime(package.created_at),
            "updated_at": format_datetime(package.updated_at),
            "reviews_count": reviews_count,
        }

    @staticmethod
    async def create_package(
        user_id: int,
        data: CreatePackageRequest,
        timestamp: str,
    ) -> int:
        """패키지를 등록합니다.

        Args:
            user_id: 등록자 ID.
            data: 패키지 등록 데이터.
            timestamp: 요청 타임스탬프.

        Returns:
            생성된 패키지 ID.
        """
        # 이름 중복 검사
        existing = await package_models.get_package_by_name(data.name)
        if existing:
            raise bad_request_error(
                "PACKAGE_NAME_DUPLICATE",
                timestamp,
                "이미 등록된 패키지 이름입니다.",
            )

        return await package_models.create_package(
            name=data.name,
            display_name=data.display_name,
            description=data.description,
            homepage_url=data.homepage_url,
            category=data.category,
            package_manager=data.package_manager,
            created_by=user_id,
        )

    @staticmethod
    async def update_package(
        package_id: int,
        user_id: int,
        data: UpdatePackageRequest,
        timestamp: str,
        is_admin: bool = False,
    ) -> dict:
        """패키지 정보를 수정합니다.

        Args:
            package_id: 수정할 패키지 ID.
            user_id: 요청자 ID.
            data: 수정 데이터.
            timestamp: 요청 타임스탬프.
            is_admin: 관리자 여부.

        Returns:
            수정된 패키지 정보.
        """
        package = await package_models.get_package_by_id(package_id)
        if not package:
            raise not_found_error("package", timestamp)

        # 권한 확인: 등록자 본인 또는 관리자
        if not is_admin and package.created_by != user_id:
            raise forbidden_error(
                "update",
                timestamp,
                "패키지 등록자 또는 관리자만 수정할 수 있습니다.",
            )

        update_fields = data.model_dump(exclude_none=True)
        if not update_fields:
            raise bad_request_error(
                "NO_CHANGES_PROVIDED",
                timestamp,
                "수정할 내용이 없습니다.",
            )

        await package_models.update_package(package_id, **update_fields)

        # 수정된 패키지 다시 조회
        updated = await package_models.get_package_by_id(package_id)
        assert updated is not None  # 위에서 존재 확인 완료

        return {
            "package_id": updated.id,
            "name": updated.name,
            "display_name": updated.display_name,
            "description": updated.description,
            "homepage_url": updated.homepage_url,
            "category": updated.category,
            "package_manager": updated.package_manager,
            "updated_at": format_datetime(updated.updated_at),
        }

    @staticmethod
    async def create_review(
        package_id: int,
        user_id: int,
        data: CreateReviewRequest,
        timestamp: str,
    ) -> int:
        """패키지 리뷰를 작성합니다.

        IntegrityError(중복 리뷰)는 컨트롤러에서 처리합니다.

        Args:
            package_id: 패키지 ID.
            user_id: 작성자 ID.
            data: 리뷰 작성 데이터.
            timestamp: 요청 타임스탬프.

        Returns:
            생성된 리뷰 ID.
        """
        # 패키지 존재 확인
        package = await package_models.get_package_by_id(package_id)
        if not package:
            raise not_found_error("package", timestamp)

        return await package_review_models.create_review(
            package_id=package_id,
            user_id=user_id,
            rating=data.rating,
            title=data.title,
            content=data.content,
        )

    @staticmethod
    async def get_reviews(
        package_id: int,
        offset: int,
        limit: int,
        sort: str = "latest",
        timestamp: str = "",
    ) -> dict:
        """패키지의 리뷰 목록을 조회합니다.

        Args:
            package_id: 패키지 ID.
            offset: 시작 위치.
            limit: 조회할 개수.
            sort: 정렬 옵션.
            timestamp: 요청 타임스탬프.

        Returns:
            리뷰 목록과 페이지네이션 정보.
        """
        # 패키지 존재 확인
        package = await package_models.get_package_by_id(package_id)
        if not package:
            raise not_found_error("package", timestamp)

        reviews = await package_review_models.get_reviews_by_package(
            package_id=package_id,
            offset=offset,
            limit=limit,
            sort=sort,
        )
        total_count = await package_review_models.get_reviews_count(package_id)
        has_more = offset + limit < total_count

        return {
            "reviews": reviews,
            "pagination": {
                "offset": offset,
                "limit": limit,
                "total_count": total_count,
                "has_more": has_more,
            },
        }

    @staticmethod
    async def update_review(
        package_id: int,
        review_id: int,
        user_id: int,
        data: UpdateReviewRequest,
        timestamp: str,
    ) -> dict:
        """리뷰를 수정합니다.

        Args:
            package_id: 패키지 ID.
            review_id: 수정할 리뷰 ID.
            user_id: 요청자 ID.
            data: 수정 데이터.
            timestamp: 요청 타임스탬프.

        Returns:
            수정된 리뷰 정보.
        """
        review = await package_review_models.get_review_by_id(review_id)
        if not review or review["package_id"] != package_id:
            raise not_found_error("review", timestamp)

        # 권한 확인: 작성자 본인만 수정 가능
        if review["author"]["user_id"] != user_id:
            raise forbidden_error(
                "update",
                timestamp,
                "리뷰 작성자만 수정할 수 있습니다.",
            )

        update_fields = data.model_dump(exclude_none=True)
        if not update_fields:
            raise bad_request_error(
                "NO_CHANGES_PROVIDED",
                timestamp,
                "수정할 내용이 없습니다.",
            )

        await package_review_models.update_review(
            review_id,
            rating=data.rating,
            title=data.title,
            content=data.content,
        )

        # 수정된 리뷰 다시 조회
        updated = await package_review_models.get_review_by_id(review_id)
        assert updated is not None  # 위에서 존재 확인 완료

        return updated

    @staticmethod
    async def delete_review(
        package_id: int,
        review_id: int,
        user_id: int,
        is_admin: bool,
        timestamp: str,
    ) -> None:
        """리뷰를 삭제합니다.

        Args:
            package_id: 패키지 ID.
            review_id: 삭제할 리뷰 ID.
            user_id: 요청자 ID.
            is_admin: 관리자 여부.
            timestamp: 요청 타임스탬프.
        """
        review = await package_review_models.get_review_by_id(review_id)
        if not review or review["package_id"] != package_id:
            raise not_found_error("review", timestamp)

        # 권한 확인: 작성자 본인 또는 관리자
        if not is_admin and review["author"]["user_id"] != user_id:
            raise forbidden_error(
                "delete",
                timestamp,
                "리뷰 작성자 또는 관리자만 삭제할 수 있습니다.",
            )

        await package_review_models.delete_review(review_id)
