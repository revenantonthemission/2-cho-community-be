"""tag_router: 태그 관련 라우터 모듈."""

from fastapi import APIRouter, Query, Request, status

from controllers import tag_controller

tag_router = APIRouter(prefix="/v1/tags", tags=["tags"])


@tag_router.get("/", status_code=status.HTTP_200_OK)
async def get_tags(request: Request, search: str = Query(default="")) -> dict:
    """태그 자동완성 검색. 인증 불필요."""
    return await tag_controller.get_tags(request, search=search)
