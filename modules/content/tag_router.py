"""tag_router: 태그 관련 라우터 모듈."""

from fastapi import APIRouter, Body, Depends, Path, Query, Request, status

from core.dependencies.auth import get_optional_user, require_verified_email
from modules.content import tag_controller
from modules.content.tag_schemas import UpdateTagRequest
from modules.user.models import User

tag_router = APIRouter(prefix="/v1/tags", tags=["tags"])


@tag_router.get("/", status_code=status.HTTP_200_OK)
async def get_tags(request: Request, search: str = Query(default="")) -> dict:
    """태그 자동완성 검색. 인증 불필요."""
    return await tag_controller.get_tags(request, search=search)


@tag_router.get("/{tag_name}", status_code=status.HTTP_200_OK)
async def get_tag_detail_route(
    request: Request,
    tag_name: str = Path(),
    _current_user: User | None = Depends(get_optional_user),
) -> dict:
    """태그 상세 조회. 인증 선택."""
    return await tag_controller.get_tag_detail(request, tag_name)


@tag_router.put("/{tag_name}", status_code=status.HTTP_200_OK)
async def update_tag_route(
    request: Request,
    tag_name: str = Path(),
    data: UpdateTagRequest = Body(...),
    current_user: User = Depends(require_verified_email),
) -> dict:
    """태그 설명/본문 수정. 이메일 인증 + 신뢰 등급 1 이상 필요."""
    return await tag_controller.update_tag(request, tag_name, data, current_user)
