"""post_controller: 게시글, 댓글, 좋아요 관련 컨트롤러 모듈.

게시글 CRUD, 이미지 업로드, 좋아요, 댓글 기능을 제공합니다.
"""

import datetime
from fastapi import HTTPException, Request, UploadFile, status
from models import post_models
from models.user_models import User
from schemas.post_schemas import CreatePostRequest, UpdatePostRequest
from dependencies.request_context import get_request_timestamp
from utils.formatters import format_datetime
from utils.file_utils import save_upload_file

# 이미지 저장 경로
IMAGE_UPLOAD_DIR = "assets/posts"


# ============ 게시글 관련 핸들러 ============


async def get_posts(
    offset: int,
    limit: int,
    request: Request,
) -> dict:
    """게시글 목록을 조회합니다.

    페이지네이션을 적용하여 게시글 목록을 반환합니다.

    Args:
        offset: 시작 위치 (0부터 시작).
        limit: 조회할 게시글 수 (1~100).
        request: FastAPI Request 객체.

    Returns:
        게시글 목록과 페이지네이션 정보가 포함된 응답 딕셔너리.

    Raises:
        HTTPException: 잘못된 offset/limit 값이면 400.
    """
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

    # 최적화된 쿼리 사용 (N+1 문제 해결)
    posts_data = await post_models.get_posts_with_details(offset, limit)
    total_count = await post_models.get_total_posts_count()
    has_more = offset + limit < total_count

    # 날짜 포맷팅 및 내용 요약
    for post in posts_data:
        post["created_at"] = format_datetime(post["created_at"])
        post["updated_at"] = format_datetime(post.get("updated_at"))

        # 내용 요약 (Truncation)
        content = post["content"]
        if len(content) > 200:
            post["content"] = content[:200] + "..."

    return {
        "code": "POSTS_RETRIEVED",
        "message": "게시글 목록 조회에 성공했습니다.",
        "data": {
            "posts": posts_data,
            "pagination": {
                "offset": offset,
                "limit": limit,
                "total_count": total_count,
                "has_more": has_more,
            },
        },
        "errors": [],
        "timestamp": timestamp,
    }


async def get_post(
    post_id: int, request: Request, current_user: User | None = None
) -> dict:
    """게시글 상세 정보를 조회합니다.

    게시글 내용과 댓글 목록을 함께 반환합니다.
    로그인한 사용자의 경우 조회수가 증가합니다 (하루 한 번).

    Args:
        post_id: 조회할 게시글 ID.
        request: FastAPI Request 객체.
        current_user: 현재 인증된 사용자 (선택적).

    Returns:
        게시글 상세 정보와 댓글 목록이 포함된 응답 딕셔너리.

    Raises:
        HTTPException: 잘못된 ID면 400, 게시글이 없으면 404.
    """
    timestamp = get_request_timestamp(request)

    if post_id < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_post_id",
                "timestamp": timestamp,
            },
        )

    # 최적화된 쿼리 사용
    post_data = await post_models.get_post_with_details(post_id)
    if not post_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "post_not_found",
                "timestamp": timestamp,
            },
        )

    # 로그인한 사용자인 경우 조회수 증가 (하루 한 번)
    # 참고: post_data['author']는 딕셔너리 형태이며, 작성자 ID는 post_data['author']['id']에 있습니다.

    if current_user:
        # 조회수 증가 시도 (이미 오늘 조회했다면 False 반환)
        # 성공적으로 증가했다면, 로컬 데이터도 업데이트하여 사용자에게 최신 조회수 표시
        if await post_models.increment_view_count(post_id, current_user.id):
            post_data["views_count"] += 1

    comments_data = await post_models.get_comments_with_author(post_id)

    # 날짜 포맷팅
    post_data["created_at"] = format_datetime(post_data["created_at"])
    post_data["updated_at"] = format_datetime(post_data.get("updated_at"))

    for comment in comments_data:
        comment["created_at"] = format_datetime(comment["created_at"])
        comment["updated_at"] = format_datetime(comment.get("updated_at"))

    return {
        "code": "POST_RETRIEVED",
        "message": "게시글 조회에 성공했습니다.",
        "data": {
            "post": post_data,
            "comments": comments_data,
        },
        "errors": [],
        "timestamp": timestamp,
    }


async def create_post(
    post_data: CreatePostRequest,
    current_user: User,
    request: Request,
) -> dict:
    """새 게시글을 생성합니다.

    Args:
        post_data: 게시글 생성 정보 (제목, 내용, 이미지 URL).
        current_user: 현재 인증된 사용자 객체.
        request: FastAPI Request 객체.

    Returns:
        생성된 게시글 ID가 포함된 응답 딕셔너리.
    """
    timestamp = get_request_timestamp(request)

    post = await post_models.create_post(
        author_id=current_user.id,
        title=post_data.title,
        content=post_data.content,
        image_url=post_data.image_url,
    )

    return {
        "code": "POST_CREATED",
        "message": "게시글이 생성되었습니다.",
        "data": {
            "post_id": post.id,
        },
        "errors": [],
        "timestamp": timestamp,
    }


async def update_post(
    post_id: int,
    post_data: UpdatePostRequest,
    current_user: User,
    request: Request,
) -> dict:
    """게시글을 수정합니다.

    Args:
        post_id: 수정할 게시글 ID.
        post_data: 수정할 정보 (제목, 내용).
        current_user: 현재 인증된 사용자 객체.
        request: FastAPI Request 객체.

    Returns:
        수정된 게시글 정보가 포함된 응답 딕셔너리.

    Raises:
        HTTPException: 게시글 없으면 404, 권한 없으면 403, 변경 없으면 400.
    """
    timestamp = get_request_timestamp(request)

    post = await post_models.get_post_by_id(post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "post_not_found",
                "timestamp": timestamp,
            },
        )

    # 작성자 확인
    if post.author_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "not_author",
                "message": "게시글 작성자만 수정할 수 있습니다.",
                "timestamp": timestamp,
            },
        )

    # 변경 사항 수집
    updates = {}
    if post_data.title is not None:
        updates["title"] = post_data.title
    if post_data.content is not None:
        updates["content"] = post_data.content
    if post_data.image_url is not None:
        updates["image_url"] = post_data.image_url

    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "no_changes_provided",
                "timestamp": timestamp,
            },
        )

    updated_post = await post_models.update_post(
        post_id,
        title=updates.get("title"),
        content=updates.get("content"),
        image_url=updates.get("image_url"),
    )

    return {
        "code": "POST_UPDATED",
        "message": "게시글이 수정되었습니다.",
        "data": {
            "post_id": updated_post.id,
            "title": updated_post.title,
            "content": updated_post.content,
        },
        "errors": [],
        "timestamp": timestamp,
    }


async def delete_post(
    post_id: int,
    current_user: User,
    request: Request,
) -> dict:
    """게시글을 삭제합니다.

    Args:
        post_id: 삭제할 게시글 ID.
        current_user: 현재 인증된 사용자 객체.
        request: FastAPI Request 객체.

    Returns:
        삭제 성공 응답 딕셔너리.

    Raises:
        HTTPException: 게시글 없으면 404, 권한 없으면 403.
    """
    timestamp = get_request_timestamp(request)

    post = await post_models.get_post_by_id(post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "post_not_found",
                "timestamp": timestamp,
            },
        )

    # 작성자 확인
    if post.author_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "not_author",
                "message": "게시글 작성자만 삭제할 수 있습니다.",
                "timestamp": timestamp,
            },
        )

    await post_models.delete_post(post_id)

    return {
        "code": "POST_DELETED",
        "message": "게시글이 삭제되었습니다.",
        "data": {},
        "errors": [],
        "timestamp": timestamp,
    }


async def upload_image(
    file: UploadFile,
    current_user: User,
    request: Request,
) -> dict:
    """이미지를 업로드합니다.

    Args:
        file: 업로드할 이미지 파일.
        current_user: 현재 인증된 사용자 객체.
        request: FastAPI Request 객체.

    Returns:
        업로드된 이미지 URL이 포함된 응답 딕셔너리.

    Raises:
        HTTPException: 잘못된 파일 형식이면 400, 파일 크기 초과면 400.
    """
    timestamp = get_request_timestamp(request)

    try:
        url = await save_upload_file(file, IMAGE_UPLOAD_DIR)
    except HTTPException as e:
        if isinstance(e.detail, dict):
            e.detail["timestamp"] = timestamp
        raise e

    return {
        "code": "IMAGE_UPLOADED",
        "message": "이미지가 업로드되었습니다.",
        "data": {
            "url": url,
        },
        "errors": [],
        "timestamp": timestamp,
    }
