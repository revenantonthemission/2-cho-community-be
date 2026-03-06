"""tag_controller: 태그 관련 컨트롤러 모듈."""

from fastapi import Request
from models.tag_models import search_tags
from dependencies.request_context import get_request_timestamp
from schemas.common import create_response


async def get_tags(request: Request, search: str = "") -> dict:
    """태그 검색 (자동완성)."""
    timestamp = get_request_timestamp(request)
    tags = await search_tags(search) if search else []
    return create_response(
        "TAGS_RETRIEVED",
        "태그 목록 조회에 성공했습니다.",
        data={"tags": tags},
        timestamp=timestamp,
    )
