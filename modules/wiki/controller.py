"""wiki_controller: 위키 페이지 관련 컨트롤러."""

from fastapi import Request

from core.dependencies.request_context import get_request_timestamp
from core.utils.pagination import validate_pagination
from modules.user.models import User
from modules.wiki.models import ALLOWED_SORT_OPTIONS, get_popular_wiki_tags
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
