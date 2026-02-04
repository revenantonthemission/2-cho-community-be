from fastapi import HTTPException, Request, UploadFile, status
from models.user_models import User
from schemas.post_schemas import CreatePostRequest, UpdatePostRequest
from schemas.common import create_response
from dependencies.request_context import get_request_timestamp
from utils.file_utils import save_upload_file
from core.config import settings
from services.post_service import PostService

# 이미지 저장 경로 (설정에서 로드)
IMAGE_UPLOAD_DIR = settings.IMAGE_UPLOAD_DIR


# ============ 게시글 관련 핸들러 ============


async def get_posts(
    offset: int,
    limit: int,
    request: Request,
) -> dict:
    """게시글 목록을 조회합니다."""
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

    # Service Layer 호출
    posts_data, total_count, has_more = await PostService.get_posts(offset, limit)

    return create_response(
        "POSTS_RETRIEVED",
        "게시글 목록 조회에 성공했습니다.",
        data={
            "posts": posts_data,
            "pagination": {
                "offset": offset,
                "limit": limit,
                "total_count": total_count,
                "has_more": has_more,
            },
        },
        timestamp=timestamp,
    )


async def get_post(
    post_id: int, request: Request, current_user: User | None = None
) -> dict:
    """게시글 상세 정보를 조회합니다."""
    timestamp = get_request_timestamp(request)

    if post_id < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_post_id",
                "timestamp": timestamp,
            },
        )

    # Service Layer 호출
    result_data = await PostService.get_post_detail(post_id, current_user, timestamp)

    return create_response(
        "POST_RETRIEVED",
        "게시글 조회에 성공했습니다.",
        data=result_data,
        timestamp=timestamp,
    )


async def create_post(
    post_data: CreatePostRequest,
    current_user: User,
    request: Request,
) -> dict:
    """새 게시글을 생성합니다."""
    timestamp = get_request_timestamp(request)

    # Service Layer 호출
    post_id = await PostService.create_post(current_user.id, post_data)

    return create_response(
        "POST_CREATED",
        "게시글이 생성되었습니다.",
        data={"post_id": post_id},
        timestamp=timestamp,
    )


async def update_post(
    post_id: int,
    post_data: UpdatePostRequest,
    current_user: User,
    request: Request,
) -> dict:
    """게시글을 수정합니다."""
    timestamp = get_request_timestamp(request)

    # Service Layer 호출
    updated_data = await PostService.update_post(
        post_id,
        current_user.id,
        post_data.title,
        post_data.content,
        post_data.image_url,
        timestamp,
    )

    return create_response(
        "POST_UPDATED",
        "게시글이 수정되었습니다.",
        data=updated_data,
        timestamp=timestamp,
    )


async def delete_post(
    post_id: int,
    current_user: User,
    request: Request,
) -> dict:
    """게시글을 삭제합니다."""
    timestamp = get_request_timestamp(request)

    # Service Layer 호출
    await PostService.delete_post(post_id, current_user.id, timestamp)

    return create_response(
        "POST_DELETED", "게시글이 삭제되었습니다.", timestamp=timestamp
    )


async def upload_image(
    file: UploadFile,
    current_user: User,
    request: Request,
) -> dict:
    """이미지를 업로드합니다."""
    timestamp = get_request_timestamp(request)

    try:
        url = await save_upload_file(file, IMAGE_UPLOAD_DIR)
    except HTTPException as e:
        if isinstance(e.detail, dict):
            e.detail["timestamp"] = timestamp
        raise e

    return create_response(
        "IMAGE_UPLOADED",
        "이미지가 업로드되었습니다.",
        data={"url": url},
        timestamp=timestamp,
    )
