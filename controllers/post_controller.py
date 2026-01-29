"""post_controller: 게시글, 댓글, 좋아요 관련 컨트롤러 모듈.

게시글 CRUD, 이미지 업로드, 좋아요, 댓글 기능을 제공합니다.
"""

import os
import uuid
from fastapi import HTTPException, Request, UploadFile, status
from models import post_models
from models import user_models
from models.user_models import User
from schemas.post_schemas import CreatePostRequest, UpdatePostRequest
from schemas.comment_schemas import CreateCommentRequest, UpdateCommentRequest
from dependencies.request_context import get_request_timestamp


# 허용된 이미지 확장자
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
# 최대 이미지 크기 (5MB)
MAX_IMAGE_SIZE = 5 * 1024 * 1024
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

    posts = await post_models.get_posts_by_offset(offset, limit)
    total_count = await post_models.get_total_posts_count()
    has_more = offset + limit < total_count

    # 게시꺀 목록을 응답 형태로 변환
    posts_data = []
    for post in posts:
        author = await user_models.get_user_by_id(post.author_id)
        posts_data.append(
            {
                "post_id": post.id,
                "title": post.title,
                "content": post.content[:200] + "..."
                if len(post.content) > 200
                else post.content,
                "image_url": post.image_url,
                "author": {
                    "user_id": author.id if author else None,
                    "nickname": author.nickname if author else "탈퇴한 사용자",
                    "profileImageUrl": author.profileImageUrl if author else None,
                },
                "likes_count": await post_models.get_post_likes_count(post.id),
                "comments_count": await post_models.get_comments_count_by_post(post.id),
                "views_count": post.views,
                "created_at": post.created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        )

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

    post = await post_models.get_post_by_id(post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "post_not_found",
                "timestamp": timestamp,
            },
        )

    # 로그인한 사용자인 경우 조회수 증가 (하루 한 번)
    if current_user:
        await post_models.increment_view_count(post_id, current_user.id)
        # 조회수 증가 후 다시 조회하여 최신 값 반영
        post = await post_models.get_post_by_id(post_id)

    author = await user_models.get_user_by_id(post.author_id)
    comments = await post_models.get_comments_by_post(post_id)

    # 댓글 목록 변환
    comments_data = []
    for comment in comments:
        comment_author = await user_models.get_user_by_id(comment.author_id)
        comments_data.append(
            {
                "comment_id": comment.id,
                "content": comment.content,
                "author": {
                    "user_id": comment_author.id if comment_author else None,
                    "nickname": comment_author.nickname
                    if comment_author
                    else "탈퇴한 사용자",
                    "profileImageUrl": comment_author.profileImageUrl
                    if comment_author
                    else None,
                },
                "created_at": comment.created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "updated_at": comment.updated_at.strftime("%Y-%m-%dT%H:%M:%SZ")
                if comment.updated_at
                else None,
            }
        )

    return {
        "code": "POST_RETRIEVED",
        "message": "게시글 조회에 성공했습니다.",
        "data": {
            "post": {
                "post_id": post.id,
                "title": post.title,
                "content": post.content,
                "image_url": post.image_url,
                "author": {
                    "user_id": author.id if author else None,
                    "nickname": author.nickname if author else "탈퇴한 사용자",
                    "profileImageUrl": author.profileImageUrl if author else None,
                },
                "likes_count": await post_models.get_post_likes_count(post_id),
                "views_count": post.views,
                "created_at": post.created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "updated_at": post.updated_at.strftime("%Y-%m-%dT%H:%M:%SZ")
                if post.updated_at
                else None,
            },
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

    # 파일 확장자 검증
    filename = file.filename or ""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_file_type",
                "message": f"허용된 이미지 형식: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}",
                "timestamp": timestamp,
            },
        )

    # 파일 크기 검증
    contents = await file.read()
    if len(contents) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "file_too_large",
                "message": f"파일 크기는 {MAX_IMAGE_SIZE // (1024 * 1024)}MB를 초과할 수 없습니다.",
                "timestamp": timestamp,
            },
        )

    # 유니크한 파일명 생성
    unique_filename = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(IMAGE_UPLOAD_DIR, unique_filename)

    # 디렉토리가 없으면 생성
    os.makedirs(IMAGE_UPLOAD_DIR, exist_ok=True)

    # 파일 저장
    with open(file_path, "wb") as f:
        f.write(contents)

    return {
        "code": "IMAGE_UPLOADED",
        "message": "이미지가 업로드되었습니다.",
        "data": {
            "url": f"/{file_path}",
        },
        "errors": [],
        "timestamp": timestamp,
    }


# ============ 좋아요 관련 핸들러 ============


async def like_post(
    post_id: int,
    current_user: User,
    request: Request,
) -> dict:
    """게시글에 좋아요를 추가합니다.

    Args:
        post_id: 좋아요할 게시글 ID.
        current_user: 현재 인증된 사용자 객체.
        request: FastAPI Request 객체.

    Returns:
        좋아요 개수가 포함된 응답 딕셔너리.

    Raises:
        HTTPException: 게시글 없으면 404, 이미 좋아요했으면 409.
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

    # 이미 좋아요를 눌렀는지 확인
    existing_like = await post_models.get_like(post_id, current_user.id)
    if existing_like:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "already_liked",
                "message": "이미 좋아요를 누른 게시글입니다.",
                "timestamp": timestamp,
            },
        )

    await post_models.add_like(post_id, current_user.id)

    return {
        "code": "LIKE_ADDED",
        "message": "좋아요가 추가되었습니다.",
        "data": {
            "likes_count": await post_models.get_post_likes_count(post_id),
        },
        "errors": [],
        "timestamp": timestamp,
    }


async def unlike_post(
    post_id: int,
    current_user: User,
    request: Request,
) -> dict:
    """좋아요를 취소합니다.

    Args:
        post_id: 좋아요 취소할 게시글 ID.
        current_user: 현재 인증된 사용자 객체.
        request: FastAPI Request 객체.

    Returns:
        좋아요 개수가 포함된 응답 딕셔너리.

    Raises:
        HTTPException: 게시글 없으면 404, 좋아요 안했으면 404.
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

    # 좋아요를 눌렀는지 확인
    existing_like = await post_models.get_like(post_id, current_user.id)
    if not existing_like:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "like_not_found",
                "message": "좋아요를 누르지 않은 게시글입니다.",
                "timestamp": timestamp,
            },
        )

    await post_models.remove_like(post_id, current_user.id)

    return {
        "code": "LIKE_REMOVED",
        "message": "좋아요가 취소되었습니다.",
        "data": {
            "likes_count": await post_models.get_post_likes_count(post_id),
        },
        "errors": [],
        "timestamp": timestamp,
    }


# ============ 댓글 관련 핸들러 ============


async def create_comment(
    post_id: int,
    comment_data: CreateCommentRequest,
    current_user: User,
    request: Request,
) -> dict:
    """새 댓글을 작성합니다.

    Args:
        post_id: 댓글을 작성할 게시글 ID.
        comment_data: 댓글 생성 정보 (내용).
        current_user: 현재 인증된 사용자 객체.
        request: FastAPI Request 객체.

    Returns:
        생성된 댓글 정보가 포함된 응답 딕셔너리.

    Raises:
        HTTPException: 게시글 없으면 404.
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

    comment = await post_models.create_comment(
        post_id=post_id,
        author_id=current_user.id,
        content=comment_data.content,
    )

    return {
        "code": "COMMENT_CREATED",
        "message": "댓글이 생성되었습니다.",
        "data": {
            "comment_id": comment.id,
            "content": comment.content,
            "created_at": comment.created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "errors": [],
        "timestamp": timestamp,
    }


async def update_comment(
    post_id: int,
    comment_id: int,
    comment_data: UpdateCommentRequest,
    current_user: User,
    request: Request,
) -> dict:
    """댓글을 수정합니다.

    Args:
        post_id: 게시글 ID.
        comment_id: 수정할 댓글 ID.
        comment_data: 수정할 내용.
        current_user: 현재 인증된 사용자 객체.
        request: FastAPI Request 객체.

    Returns:
        수정된 댓글 정보가 포함된 응답 딕셔너리.

    Raises:
        HTTPException: 게시글/댓글 없으면 404, 권한 없으면 403, 불일치면 400.
    """
    timestamp = get_request_timestamp(request)

    # 게시글이 있는지 확인
    post = await post_models.get_post_by_id(post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "post_not_found",
                "timestamp": timestamp,
            },
        )

    # 댓글이 있는지 확인
    comment = await post_models.get_comment_by_id(comment_id)
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "comment_not_found",
                "timestamp": timestamp,
            },
        )

    # 댓글이 해당 게시글에 속하는지 확인
    if comment.post_id != post_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "comment_not_in_post",
                "timestamp": timestamp,
            },
        )

    # 작성자 확인
    if comment.author_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "not_author",
                "message": "댓글 작성자만 수정할 수 있습니다.",
                "timestamp": timestamp,
            },
        )

    updated_comment = await post_models.update_comment(comment_id, comment_data.content)

    return {
        "code": "COMMENT_UPDATED",
        "message": "댓글이 수정되었습니다.",
        "data": {
            "comment_id": updated_comment.id,
            "content": updated_comment.content,
            "updated_at": updated_comment.updated_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "errors": [],
        "timestamp": timestamp,
    }


async def delete_comment(
    post_id: int,
    comment_id: int,
    current_user: User,
    request: Request,
) -> dict:
    """댓글을 삭제합니다.

    Args:
        post_id: 게시글 ID.
        comment_id: 삭제할 댓글 ID.
        current_user: 현재 인증된 사용자 객체.
        request: FastAPI Request 객체.

    Returns:
        삭제 성공 응답 딕셔너리.

    Raises:
        HTTPException: 게시글/댓글 없으면 404, 권한 없으면 403, 불일치면 400.
    """
    timestamp = get_request_timestamp(request)

    # 게시글이 있는지 확인
    post = await post_models.get_post_by_id(post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "post_not_found",
                "timestamp": timestamp,
            },
        )

    # 댓글이 있는지 확인
    comment = await post_models.get_comment_by_id(comment_id)
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "comment_not_found",
                "timestamp": timestamp,
            },
        )

    # 댓글이 해당 게시글에 속하는지 확인
    if comment.post_id != post_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "comment_not_in_post",
                "timestamp": timestamp,
            },
        )

    # 작성자 확인
    if comment.author_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "not_author",
                "message": "댓글 작성자만 삭제할 수 있습니다.",
                "timestamp": timestamp,
            },
        )

    await post_models.delete_comment(comment_id)

    return {
        "code": "COMMENT_DELETED",
        "message": "댓글이 삭제되었습니다.",
        "data": {},
        "errors": [],
        "timestamp": timestamp,
    }
