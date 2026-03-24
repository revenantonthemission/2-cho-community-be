"""wiki_service: 위키 페이지 관련 비즈니스 로직."""

from core.utils.exceptions import bad_request_error, forbidden_error, not_found_error
from modules.content import tag_models
from modules.wiki import models as wiki_models
from modules.wiki.schemas import CreateWikiPageRequest, UpdateWikiPageRequest


class WikiService:
    """위키 페이지 관리 서비스."""

    @staticmethod
    async def get_wiki_pages(
        offset: int,
        limit: int,
        sort: str = "latest",
        search: str | None = None,
        tag: str | None = None,
    ) -> dict:
        """위키 페이지 목록을 조회합니다.

        Args:
            offset: 시작 위치.
            limit: 조회할 개수.
            sort: 정렬 옵션.
            search: 검색어.
            tag: 태그 이름 필터.

        Returns:
            위키 페이지 목록과 페이지네이션 정보.
        """
        wiki_pages = await wiki_models.get_wiki_pages(
            offset=offset,
            limit=limit,
            sort=sort,
            search=search,
            tag=tag,
        )
        total_count = await wiki_models.get_wiki_pages_count(
            search=search,
            tag=tag,
        )
        has_more = offset + limit < total_count

        # 태그 벌크 조회
        page_ids = [p["wiki_page_id"] for p in wiki_pages]
        tags_map = await wiki_models.get_wiki_pages_tags(page_ids)
        for page in wiki_pages:
            page["tags"] = tags_map.get(page["wiki_page_id"], [])

        return {
            "wiki_pages": wiki_pages,
            "pagination": {
                "offset": offset,
                "limit": limit,
                "total_count": total_count,
                "has_more": has_more,
            },
        }

    @staticmethod
    async def get_wiki_page(slug: str, timestamp: str) -> dict:
        """위키 페이지 상세 정보를 조회합니다.

        Args:
            slug: 페이지 슬러그.
            timestamp: 요청 타임스탬프.

        Returns:
            위키 페이지 상세 정보.
        """
        page = await wiki_models.get_wiki_page_by_slug(slug)
        if not page:
            raise not_found_error("wiki_page", timestamp)

        # 조회수 증가
        await wiki_models.increment_views(page["wiki_page_id"])
        page["views_count"] += 1

        # 태그 조회
        page["tags"] = await wiki_models.get_wiki_page_tags(page["wiki_page_id"])

        return page

    @staticmethod
    async def create_wiki_page(
        user_id: int,
        data: CreateWikiPageRequest,
        timestamp: str,
    ) -> int:
        """위키 페이지를 생성합니다.

        Args:
            user_id: 작성자 ID.
            data: 페이지 생성 데이터.
            timestamp: 요청 타임스탬프.

        Returns:
            생성된 위키 페이지 ID.
        """
        # 슬러그 중복 검사
        if await wiki_models.slug_exists(data.slug):
            raise bad_request_error(
                "SLUG_DUPLICATE",
                timestamp,
                "이미 사용 중인 슬러그입니다.",
            )

        wiki_page_id = await wiki_models.create_wiki_page(
            title=data.title,
            slug=data.slug,
            content=data.content,
            author_id=user_id,
        )

        # 태그 처리
        if data.tags:
            normalized = [tag_models.normalize_tag_name(t) for t in data.tags]
            normalized = [t for t in normalized if t]
            if normalized:
                tag_ids = await tag_models.get_or_create_tags(normalized)
                await wiki_models.save_wiki_page_tags(wiki_page_id, tag_ids)

        return wiki_page_id

    @staticmethod
    async def update_wiki_page(
        slug: str,
        user_id: int,
        data: UpdateWikiPageRequest,
        timestamp: str,
    ) -> dict:
        """위키 페이지를 수정합니다. 누구나 편집 가능 (위키 특성).

        Args:
            slug: 수정할 페이지 슬러그.
            user_id: 편집자 ID.
            data: 수정 데이터.
            timestamp: 요청 타임스탬프.

        Returns:
            수정된 위키 페이지 정보.
        """
        page = await wiki_models.get_wiki_page_by_slug(slug)
        if not page:
            raise not_found_error("wiki_page", timestamp)

        wiki_page_id = page["wiki_page_id"]

        # 내용 수정 (title, content 중 하나라도 있으면 업데이트)
        if data.title is not None or data.content is not None:
            await wiki_models.update_wiki_page(
                wiki_page_id=wiki_page_id,
                editor_id=user_id,
                title=data.title,
                content=data.content,
            )

        # 태그 수정
        if data.tags is not None:
            normalized = [tag_models.normalize_tag_name(t) for t in data.tags]
            normalized = [t for t in normalized if t]
            if normalized:
                tag_ids = await tag_models.get_or_create_tags(normalized)
                await wiki_models.save_wiki_page_tags(wiki_page_id, tag_ids)
            else:
                # 빈 태그 목록: 기존 태그 모두 제거
                await wiki_models.save_wiki_page_tags(wiki_page_id, [])

        # 수정된 페이지 다시 조회
        updated = await wiki_models.get_wiki_page_by_slug(slug)
        assert updated is not None  # 위에서 존재 확인 완료
        updated["tags"] = await wiki_models.get_wiki_page_tags(wiki_page_id)

        return updated

    @staticmethod
    async def delete_wiki_page(
        slug: str,
        user_id: int,
        is_admin: bool,
        timestamp: str,
    ) -> None:
        """위키 페이지를 삭제합니다.

        Args:
            slug: 삭제할 페이지 슬러그.
            user_id: 요청자 ID.
            is_admin: 관리자 여부.
            timestamp: 요청 타임스탬프.
        """
        page = await wiki_models.get_wiki_page_by_slug(slug)
        if not page:
            raise not_found_error("wiki_page", timestamp)

        # 권한 확인: 작성자 본인 또는 관리자
        if not is_admin and page["author_id"] != user_id:
            raise forbidden_error(
                "delete",
                timestamp,
                "위키 페이지 작성자 또는 관리자만 삭제할 수 있습니다.",
            )

        await wiki_models.delete_wiki_page(page["wiki_page_id"])
