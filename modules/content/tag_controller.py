"""tag_controller: 태그 관련 컨트롤러 모듈."""

from fastapi import HTTPException, Request, status

from core.dependencies.request_context import get_request_timestamp
from modules.content.tag_models import (
    get_tag_by_name,
    normalize_tag_name,
    search_tags,
    update_tag_description,
)
from modules.content.tag_schemas import UpdateTagRequest
from modules.reputation.models import get_user_trust_level
from modules.user.models import User
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


async def get_tag_detail(request: Request, tag_name: str) -> dict:
    """태그 상세 정보를 조회합니다."""
    timestamp = get_request_timestamp(request)
    normalized = normalize_tag_name(tag_name)

    tag = await get_tag_by_name(normalized)
    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "tag_not_found",
                "message": "태그를 찾을 수 없습니다.",
                "timestamp": timestamp,
            },
        )

    return create_response(
        "TAG_RETRIEVED",
        "태그 상세 조회에 성공했습니다.",
        data={"tag": tag},
        timestamp=timestamp,
    )


async def update_tag(
    request: Request,
    tag_name: str,
    data: UpdateTagRequest,
    current_user: User,
) -> dict:
    """태그 설명 및 본문을 수정합니다. 신뢰 등급 1 이상 필요."""
    timestamp = get_request_timestamp(request)

    # 신뢰 등급 확인
    trust_level = await get_user_trust_level(current_user.id)
    if trust_level < 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "insufficient_trust_level",
                "message": "태그를 수정하려면 신뢰 등급 1 이상이 필요합니다.",
                "timestamp": timestamp,
            },
        )

    normalized = normalize_tag_name(tag_name)

    # 태그 존재 확인
    tag = await get_tag_by_name(normalized)
    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "tag_not_found",
                "message": "태그를 찾을 수 없습니다.",
                "timestamp": timestamp,
            },
        )

    # 수정할 필드가 하나 이상 있어야 함
    if data.description is None and data.body is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "no_fields_to_update",
                "message": "수정할 필드를 하나 이상 입력해주세요.",
                "timestamp": timestamp,
            },
        )

    await update_tag_description(normalized, data.description, data.body, current_user.id)

    updated_tag = await get_tag_by_name(normalized)
    return create_response(
        "TAG_UPDATED",
        "태그가 수정되었습니다.",
        data={"tag": updated_tag},
        timestamp=timestamp,
    )
