"""wiki_service: 위키 페이지 관련 비즈니스 로직."""

import logging

from core.database.connection import transactional
from core.utils.exceptions import bad_request_error, conflict_error, forbidden_error, not_found_error
from modules.content import tag_models
from modules.wiki import models as wiki_models
from modules.wiki.revision_models import create_revision as create_rev
from modules.wiki.revision_models import get_next_revision_number
from modules.wiki.schemas import CreateWikiPageRequest, UpdateWikiPageRequest

logger = logging.getLogger(__name__)


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
        # 슬러그 중복 검사 (빠른 사전 검증)
        if await wiki_models.slug_exists(data.slug):
            raise bad_request_error(
                "SLUG_DUPLICATE",
                timestamp,
                "이미 사용 중인 슬러그입니다.",
            )

        # UNIQUE 제약으로 동시 생성 시에도 정합성 보장 (TOCTOU 방어)
        try:
            wiki_page_id = await wiki_models.create_wiki_page(
                title=data.title,
                slug=data.slug,
                content=data.content,
                author_id=user_id,
            )
        except Exception as e:
            if "Duplicate entry" in str(e):
                raise conflict_error("wiki_slug", timestamp, "이미 사용 중인 슬러그입니다.") from e
            raise

        # 초기 리비전 생성
        async with transactional() as cursor:
            rev_num = await get_next_revision_number(cursor, wiki_page_id)
            await create_rev(
                cursor,
                wiki_page_id,
                rev_num,
                data.title,
                data.content,
                data.edit_summary,
                user_id,
            )

        # 태그 처리
        if data.tags:
            normalized = [tag_models.normalize_tag_name(t) for t in data.tags]
            normalized = [t for t in normalized if t]
            if normalized:
                tag_ids = await tag_models.get_or_create_tags(normalized)
                await wiki_models.save_wiki_page_tags(wiki_page_id, tag_ids)

        # 평판 포인트 부여 (best-effort)
        try:
            from modules.reputation.service import ReputationService

            await ReputationService.award_points(
                user_id=user_id,
                event_type="wiki_created",
                points=20,
                source_type="wiki",
                source_id=wiki_page_id,
            )
        except Exception:
            logger.warning("평판 포인트 부여 실패 (create_wiki_page)", exc_info=True)

        return wiki_page_id

    @staticmethod
    async def update_wiki_page(
        slug: str,
        user_id: int,
        data: UpdateWikiPageRequest,
        timestamp: str,
    ) -> dict:
        """위키 페이지를 수정합니다. 누구나 편집 가능 (위키 특성).

        단일 트랜잭션 + SELECT FOR UPDATE로 동시 편집 시 lost update를 방지합니다.

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

        # 단일 트랜잭션: 페이지 잠금 → 수정 → 리비전 생성
        async with transactional() as cursor:
            # SELECT FOR UPDATE로 행 잠금 — 동시 편집 직렬화
            await cursor.execute(
                "SELECT id FROM wiki_page WHERE id = %s AND deleted_at IS NULL FOR UPDATE",
                (wiki_page_id,),
            )
            locked = await cursor.fetchone()
            if not locked:
                raise not_found_error("wiki_page", timestamp)

            # 내용 수정 (title, content 중 하나라도 있으면 업데이트)
            if data.title is not None or data.content is not None:
                updates = ["last_edited_by = %s"]
                params: list = [user_id]
                if data.title is not None:
                    updates.append("title = %s")
                    params.append(data.title)
                if data.content is not None:
                    updates.append("content = %s")
                    params.append(data.content)
                params.append(wiki_page_id)
                await cursor.execute(
                    f"UPDATE wiki_page SET {', '.join(updates)} WHERE id = %s AND deleted_at IS NULL",  # noqa: S608
                    params,
                )

            # 수정 후 최신 상태 조회 (같은 트랜잭션 내에서)
            await cursor.execute(
                "SELECT title, content FROM wiki_page WHERE id = %s",
                (wiki_page_id,),
            )
            current = await cursor.fetchone()

            # 리비전 생성 (동일 트랜잭션)
            rev_num = await get_next_revision_number(cursor, wiki_page_id)
            await create_rev(
                cursor,
                wiki_page_id,
                rev_num,
                current["title"],
                current["content"],
                data.edit_summary,
                user_id,
            )

        # 태그 수정 (트랜잭션 밖 — 태그는 lost update 위험 없음)
        if data.tags is not None:
            normalized = [tag_models.normalize_tag_name(t) for t in data.tags]
            normalized = [t for t in normalized if t]
            if normalized:
                tag_ids = await tag_models.get_or_create_tags(normalized)
                await wiki_models.save_wiki_page_tags(wiki_page_id, tag_ids)
            else:
                await wiki_models.save_wiki_page_tags(wiki_page_id, [])

        # 수정된 페이지 최종 조회 (트랜잭션 커밋 후)
        updated = await wiki_models.get_wiki_page_by_slug(slug)
        assert updated is not None
        updated["tags"] = await wiki_models.get_wiki_page_tags(wiki_page_id)

        # 평판 포인트 부여: 원저자가 아닌 편집자만 (best-effort)
        if user_id != page["author_id"]:
            try:
                from modules.reputation.service import ReputationService

                await ReputationService.award_points(
                    user_id=user_id,
                    event_type="wiki_edited",
                    points=10,
                    source_type="wiki",
                    source_id=wiki_page_id,
                )
            except Exception:
                logger.warning("평판 포인트 부여 실패 (update_wiki_page)", exc_info=True)

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
