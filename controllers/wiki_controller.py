"""wiki_controller: 위키 페이지 관련 컨트롤러."""

from fastapi import HTTPException, Request, status

from dependencies.request_context import get_request_timestamp
from models.wiki_models import ALLOWED_SORT_OPTIONS
from models.user_models import User
from schemas.common import create_response
from schemas.wiki_schemas import CreateWikiPageRequest, UpdateWikiPageRequest
from services.wiki_service import WikiService


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

    result = await WikiService.get_wiki_pages(
        offset=offset, limit=limit, sort=sort,
        search=search, tag=tag,
    )

    return create_response(
        "WIKI_PAGES_RETRIEVED",
        "위키 페이지 목록 조회에 성공했습니다.",
        data=result,
        timestamp=timestamp,
    )


async def get_wiki_page(
    slug: str,
    request: Request,
) -> dict:
    """위키 페이지 상세 정보를 조회합니다."""
    timestamp = get_request_timestamp(request)

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
        current_user.id, data, timestamp,
    )

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
        slug, current_user.id, data, timestamp,
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

    await WikiService.delete_wiki_page(
        slug, current_user.id,
        is_admin=current_user.is_admin, timestamp=timestamp,
    )

    return create_response(
        "WIKI_PAGE_DELETED",
        "위키 페이지가 삭제되었습니다.",
        timestamp=timestamp,
    )
