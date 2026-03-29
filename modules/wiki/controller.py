"""wiki_controller: 위키 페이지 관련 컨트롤러."""

from fastapi import HTTPException, Request, status

from core.database.connection import transactional
from core.dependencies.request_context import get_request_timestamp
from core.utils.pagination import validate_pagination
from modules.user.models import User
from modules.wiki.diff_engine import compute_diff
from modules.wiki.models import (
    ALLOWED_SORT_OPTIONS,
    get_popular_wiki_tags,
    get_wiki_page_by_slug,
)
from modules.wiki.revision_models import (
    create_revision,
    get_current_revision_number,
    get_next_revision_number,
    get_revision,
    get_revisions,
    get_revisions_count,
)
from modules.wiki.schemas import CreateWikiPageRequest, UpdateWikiPageRequest
from modules.wiki.service import WikiService
from schemas.common import create_response


async def get_wiki_pages(
    offset: int,
    limit: int,
    request: Request,
    sort: str = "latest",
    search: str | None = None,
    tag: str | None = None,
) -> dict:
    """위키 페이지 목록을 조회합니다."""
    timestamp = get_request_timestamp(request)

    # 음수 offset은 유효하지 않으므로 Service 호출 전에 빠르게 거절
    validate_pagination(offset, limit, timestamp)

    # 공백만 있는 검색어는 None으로 정규화
    if search is not None:
        search = search.strip() or None

    # 잘못된 정렬값은 400 에러 대신 기본값으로 폴백 — 파라미터 오타에 관용적으로 대응
    if sort not in ALLOWED_SORT_OPTIONS:
        sort = "latest"

    result = await WikiService.get_wiki_pages(
        offset=offset,
        limit=limit,
        sort=sort,
        search=search,
        tag=tag,
    )

    return create_response(
        "WIKI_PAGES_RETRIEVED",
        "위키 페이지 목록 조회에 성공했습니다.",
        data=result,
        timestamp=timestamp,
    )


async def get_wiki_popular_tags(request: Request, limit: int = 10) -> dict:
    """위키에서 가장 많이 사용된 태그를 조회합니다."""
    timestamp = get_request_timestamp(request)
    # 집계 쿼리가 단순하여 Service 계층 없이 Model을 직접 호출
    tags = await get_popular_wiki_tags(limit=limit)
    return create_response(
        "WIKI_TAGS_RETRIEVED",
        "위키 인기 태그 조회에 성공했습니다.",
        data={"tags": tags},
        timestamp=timestamp,
    )


async def get_wiki_page(
    slug: str,
    request: Request,
) -> dict:
    """위키 페이지 상세 정보를 조회합니다."""
    timestamp = get_request_timestamp(request)

    # slug는 URL-friendly 식별자 — ID 대신 사용해 북마크 가능한 고정 URL 유지
    result = await WikiService.get_wiki_page(slug, timestamp)

    return create_response(
        "WIKI_PAGE_RETRIEVED",
        "위키 페이지 조회에 성공했습니다.",
        data={"wiki_page": result},
        timestamp=timestamp,
    )


async def create_wiki_page(
    data: CreateWikiPageRequest,
    current_user: User,
    request: Request,
) -> dict:
    """새 위키 페이지를 생성합니다."""
    timestamp = get_request_timestamp(request)

    wiki_page_id = await WikiService.create_wiki_page(
        current_user.id,
        data,
        timestamp,
    )

    # slug를 응답에 포함 — 생성 직후 클라이언트가 /wiki/{slug}로 바로 이동할 수 있도록
    return create_response(
        "WIKI_PAGE_CREATED",
        "위키 페이지가 생성되었습니다.",
        data={"wiki_page_id": wiki_page_id, "slug": data.slug},
        timestamp=timestamp,
    )


async def update_wiki_page(
    slug: str,
    data: UpdateWikiPageRequest,
    current_user: User,
    request: Request,
) -> dict:
    """위키 페이지를 수정합니다."""
    timestamp = get_request_timestamp(request)

    result = await WikiService.update_wiki_page(
        slug,
        current_user.id,
        data,
        timestamp,
    )

    return create_response(
        "WIKI_PAGE_UPDATED",
        "위키 페이지가 수정되었습니다.",
        data={"wiki_page": result},
        timestamp=timestamp,
    )


async def delete_wiki_page(
    slug: str,
    current_user: User,
    request: Request,
) -> dict:
    """위키 페이지를 삭제합니다."""
    timestamp = get_request_timestamp(request)

    # 관리자는 타인의 위키 페이지도 삭제 가능 — 품질 관리 및 규정 위반 콘텐츠 제거 목적
    await WikiService.delete_wiki_page(
        slug,
        current_user.id,
        is_admin=current_user.is_admin,
        timestamp=timestamp,
    )

    return create_response(
        "WIKI_PAGE_DELETED",
        "위키 페이지가 삭제되었습니다.",
        timestamp=timestamp,
    )


# === 리비전 관련 핸들러 ===


async def get_revision_history(
    request: Request,
    slug: str,
    offset: int,
    limit: int,
) -> dict:
    """위키 페이지의 리비전 히스토리를 조회합니다."""
    timestamp = get_request_timestamp(request)

    page = await get_wiki_page_by_slug(slug)
    if not page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "wiki_page_not_found",
                "message": "위키 페이지를 찾을 수 없습니다.",
                "timestamp": timestamp,
            },
        )

    validate_pagination(offset, limit, timestamp)

    page_id = page["wiki_page_id"]
    revisions = await get_revisions(page_id, offset, limit)
    total = await get_revisions_count(page_id)

    return create_response(
        "WIKI_REVISIONS_RETRIEVED",
        "위키 리비전 목록 조회에 성공했습니다.",
        data={
            "revisions": revisions,
            "total": total,
            "offset": offset,
            "limit": limit,
        },
        timestamp=timestamp,
    )


async def get_revision_detail(
    request: Request,
    slug: str,
    revision_number: int,
) -> dict:
    """위키 페이지의 특정 리비전을 조회합니다."""
    timestamp = get_request_timestamp(request)

    page = await get_wiki_page_by_slug(slug)
    if not page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "wiki_page_not_found",
                "message": "위키 페이지를 찾을 수 없습니다.",
                "timestamp": timestamp,
            },
        )

    page_id = page["wiki_page_id"]
    revision = await get_revision(page_id, revision_number)
    if not revision:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "revision_not_found",
                "message": "해당 리비전을 찾을 수 없습니다.",
                "timestamp": timestamp,
            },
        )

    # 현재 최신 리비전인지 표시 — FE에서 "현재 버전" 뱃지 렌더링에 사용
    current_rev = await get_current_revision_number(page_id)
    revision["is_current"] = revision_number == current_rev

    return create_response(
        "WIKI_REVISION_RETRIEVED",
        "위키 리비전 조회에 성공했습니다.",
        data={"revision": revision},
        timestamp=timestamp,
    )


async def get_revision_diff(
    request: Request,
    slug: str,
    from_rev: int,
    to_rev: int,
) -> dict:
    """두 리비전 간 diff를 반환합니다."""
    timestamp = get_request_timestamp(request)

    if from_rev >= to_rev:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_revision_range",
                "message": "from은 to보다 작아야 합니다.",
                "timestamp": timestamp,
            },
        )

    page = await get_wiki_page_by_slug(slug)
    if not page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "wiki_page_not_found",
                "message": "위키 페이지를 찾을 수 없습니다.",
                "timestamp": timestamp,
            },
        )

    page_id = page["wiki_page_id"]

    old_revision = await get_revision(page_id, from_rev)
    if not old_revision:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "revision_not_found",
                "message": f"리비전 {from_rev}을(를) 찾을 수 없습니다.",
                "timestamp": timestamp,
            },
        )

    new_revision = await get_revision(page_id, to_rev)
    if not new_revision:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "revision_not_found",
                "message": f"리비전 {to_rev}을(를) 찾을 수 없습니다.",
                "timestamp": timestamp,
            },
        )

    changes = compute_diff(old_revision["content"], new_revision["content"])

    return create_response(
        "WIKI_DIFF_RETRIEVED",
        "위키 리비전 diff 조회에 성공했습니다.",
        data={
            "from_revision": from_rev,
            "to_revision": to_rev,
            "from_title": old_revision["title"],
            "to_title": new_revision["title"],
            "changes": changes,
        },
        timestamp=timestamp,
    )


async def rollback_revision(
    request: Request,
    slug: str,
    revision_number: int,
    current_user: User,
) -> dict:
    """특정 리비전으로 위키 페이지를 롤백합니다."""
    timestamp = get_request_timestamp(request)

    page = await get_wiki_page_by_slug(slug)
    if not page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "wiki_page_not_found",
                "message": "위키 페이지를 찾을 수 없습니다.",
                "timestamp": timestamp,
            },
        )

    page_id = page["wiki_page_id"]

    target_revision = await get_revision(page_id, revision_number)
    if not target_revision:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "revision_not_found",
                "message": "해당 리비전을 찾을 수 없습니다.",
                "timestamp": timestamp,
            },
        )

    async with transactional() as cursor:
        # 위키 페이지를 대상 리비전의 내용으로 복원
        await cursor.execute(
            "UPDATE wiki_page SET title = %s, content = %s, last_edited_by = %s, "
            "updated_at = CURRENT_TIMESTAMP WHERE id = %s AND deleted_at IS NULL",
            (target_revision["title"], target_revision["content"], current_user.id, page_id),
        )

        # 롤백 리비전 레코드 생성
        new_rev_number = await get_next_revision_number(cursor, page_id)
        await create_revision(
            cursor,
            wiki_page_id=page_id,
            revision_number=new_rev_number,
            title=target_revision["title"],
            content=target_revision["content"],
            edit_summary=f"리비전 {revision_number}(으)로 롤백",
            editor_id=current_user.id,
        )

    return create_response(
        "WIKI_REVISION_ROLLED_BACK",
        "위키 페이지가 롤백되었습니다.",
        data={"new_revision_number": new_rev_number},
        timestamp=timestamp,
    )
