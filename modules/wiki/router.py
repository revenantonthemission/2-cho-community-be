"""wiki_router: 위키 페이지 관련 라우터 모듈."""

from fastapi import APIRouter, Depends, Path, Query, Request, status

from core.dependencies.auth import get_optional_user, require_verified_email
from modules.user.models import User
from modules.wiki import controller as wiki_controller
from modules.wiki.schemas import CreateWikiPageRequest, UpdateWikiPageRequest

wiki_router = APIRouter(prefix="/v1/wiki", tags=["wiki"])
"""위키 페이지 관련 라우터 인스턴스."""


@wiki_router.get("/", status_code=status.HTTP_200_OK)
async def get_wiki_pages(
    request: Request,
    offset: int = Query(0, ge=0, description="시작 위치 (0부터 시작)"),
    limit: int = Query(10, ge=1, le=100, description="조회할 위키 페이지 수"),
    sort: str = Query("latest", description="정렬: latest, views, updated"),
    search: str | None = Query(None, max_length=100, description="검색어 (제목/본문)"),
    tag: str | None = Query(None, description="태그 이름 필터"),
    _current_user: User | None = Depends(get_optional_user),
) -> dict:
    """위키 페이지 목록을 조회합니다.

    Args:
        request: FastAPI Request 객체.
        offset: 시작 위치.
        limit: 조회할 위키 페이지 수.
        sort: 정렬 옵션.
        search: 검색어.
        tag: 태그 이름 필터.

    Returns:
        위키 페이지 목록과 페이지네이션 정보가 포함된 응답.
    """
    return await wiki_controller.get_wiki_pages(
        offset,
        limit,
        request,
        sort=sort,
        search=search,
        tag=tag,
    )


@wiki_router.post("/", status_code=status.HTTP_201_CREATED)
async def create_wiki_page(
    data: CreateWikiPageRequest,
    request: Request,
    current_user: User = Depends(require_verified_email),
) -> dict:
    """새 위키 페이지를 생성합니다.

    Args:
        data: 위키 페이지 생성 정보.
        request: FastAPI Request 객체.
        current_user: 현재 인증된 사용자.

    Returns:
        생성된 위키 페이지 ID와 슬러그가 포함된 응답.
    """
    return await wiki_controller.create_wiki_page(data, current_user, request)


@wiki_router.get("/tags/popular", status_code=status.HTTP_200_OK)
async def get_wiki_popular_tags(
    request: Request,
    limit: int = Query(10, ge=1, le=50, description="반환할 태그 수"),
    _current_user: User | None = Depends(get_optional_user),
) -> dict:
    """위키에서 가장 많이 사용된 인기 태그를 조회합니다."""
    return await wiki_controller.get_wiki_popular_tags(request, limit=limit)


# === 리비전 라우트 (/{slug} catch-all보다 먼저 등록) ===


@wiki_router.get("/{slug}/history", status_code=status.HTTP_200_OK)
async def get_wiki_history(
    request: Request,
    slug: str = Path(description="위키 페이지 슬러그"),
    offset: int = Query(0, ge=0, description="시작 위치"),
    limit: int = Query(20, ge=1, le=100, description="조회할 리비전 수"),
    _current_user: User | None = Depends(get_optional_user),
) -> dict:
    """위키 페이지의 리비전 히스토리를 조회합니다."""
    return await wiki_controller.get_revision_history(request, slug, offset, limit)


@wiki_router.get("/{slug}/revisions/{revision_number}", status_code=status.HTTP_200_OK)
async def get_wiki_revision(
    request: Request,
    slug: str = Path(description="위키 페이지 슬러그"),
    revision_number: int = Path(ge=1, description="리비전 번호"),
    _current_user: User | None = Depends(get_optional_user),
) -> dict:
    """위키 페이지의 특정 리비전을 조회합니다."""
    return await wiki_controller.get_revision_detail(request, slug, revision_number)


@wiki_router.get("/{slug}/diff", status_code=status.HTTP_200_OK)
async def get_wiki_diff(
    request: Request,
    slug: str = Path(description="위키 페이지 슬러그"),
    from_rev: int = Query(..., alias="from", ge=1, description="비교 시작 리비전"),
    to_rev: int = Query(..., alias="to", ge=1, description="비교 대상 리비전"),
    _current_user: User | None = Depends(get_optional_user),
) -> dict:
    """두 리비전 간 diff를 조회합니다."""
    return await wiki_controller.get_revision_diff(request, slug, from_rev, to_rev)


@wiki_router.post("/{slug}/rollback/{revision_number}", status_code=status.HTTP_200_OK)
async def rollback_wiki(
    request: Request,
    slug: str = Path(description="위키 페이지 슬러그"),
    revision_number: int = Path(ge=1, description="롤백 대상 리비전 번호"),
    current_user: User = Depends(require_verified_email),
) -> dict:
    """특정 리비전으로 위키 페이지를 롤백합니다."""
    return await wiki_controller.rollback_revision(request, slug, revision_number, current_user)


@wiki_router.get("/{slug}", status_code=status.HTTP_200_OK)
async def get_wiki_page(
    request: Request,
    slug: str = Path(description="위키 페이지 슬러그"),
    _current_user: User | None = Depends(get_optional_user),
) -> dict:
    """위키 페이지 상세 정보를 조회합니다.

    Args:
        request: FastAPI Request 객체.
        slug: 조회할 위키 페이지 슬러그.

    Returns:
        위키 페이지 상세 정보가 포함된 응답.
    """
    return await wiki_controller.get_wiki_page(slug, request)


@wiki_router.put("/{slug}", status_code=status.HTTP_200_OK)
async def update_wiki_page(
    data: UpdateWikiPageRequest,
    request: Request,
    slug: str = Path(description="위키 페이지 슬러그"),
    current_user: User = Depends(require_verified_email),
) -> dict:
    """위키 페이지를 수정합니다.

    Args:
        data: 수정할 위키 페이지 정보.
        request: FastAPI Request 객체.
        slug: 수정할 위키 페이지 슬러그.
        current_user: 현재 인증된 사용자.

    Returns:
        수정된 위키 페이지 정보가 포함된 응답.
    """
    return await wiki_controller.update_wiki_page(
        slug,
        data,
        current_user,
        request,
    )


@wiki_router.delete("/{slug}", status_code=status.HTTP_200_OK)
async def delete_wiki_page(
    request: Request,
    slug: str = Path(description="위키 페이지 슬러그"),
    current_user: User = Depends(require_verified_email),
) -> dict:
    """위키 페이지를 삭제합니다.

    Args:
        request: FastAPI Request 객체.
        slug: 삭제할 위키 페이지 슬러그.
        current_user: 현재 인증된 사용자.

    Returns:
        삭제 성공 응답.
    """
    return await wiki_controller.delete_wiki_page(slug, current_user, request)
