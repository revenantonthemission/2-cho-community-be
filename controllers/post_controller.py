# post_controller: 게시글, 댓글, 좋아요 관련 컨트롤러 모듈

import os
import uuid
from fastapi import HTTPException, Request, UploadFile, status
from models import post_models
from models import user_models
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


# 게시글 목록 조회
async def get_posts(
    page: int,
    limit: int,
    request: Request,
) -> dict:
    timestamp = get_request_timestamp(request)

    # page와 limit 유효성 검사
    if page < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_page",
                "message": "페이지 번호는 0 이상이어야 합니다.",
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

    posts = post_models.get_posts(page, limit)
    total_count = post_models.get_total_posts_count()
    has_more = (page + 1) * limit < total_count

    # 게시글 목록을 응답 형태로 변환
    posts_data = []
    for post in posts:
        author = user_models.get_user_by_id(post.author_id)
        posts_data.append(
            {
                "post_id": post.id,
                "title": post.title,
                "content": post.content[:200] + "..."
                if len(post.content) > 200
                else post.content,
                "image_urls": post.image_urls,
                "author": {
                    "user_id": author.id if author else None,
                    "nickname": author.nickname if author else "탈퇴한 사용자",
                    "profileImageUrl": author.profileImageUrl if author else None,
                },
                "likes_count": post_models.get_post_likes_count(post.id),
                "comments_count": len(post_models.get_comments_by_post(post.id)),
                "created_at": post.created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        )

    return {
        "code": "POSTS_RETRIEVED",
        "message": "게시글 목록 조회에 성공했습니다.",
        "data": {
            "posts": posts_data,
            "pagination": {
                "page": page,
                "limit": limit,
                "total_count": total_count,
                "has_more": has_more,
            },
        },
        "errors": [],
        "timestamp": timestamp,
    }


# 게시글 상세 조회
async def get_post(post_id: int, request: Request) -> dict:
    timestamp = get_request_timestamp(request)

    if post_id < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_post_id",
                "timestamp": timestamp,
            },
        )

    post = post_models.get_post_by_id(post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "post_not_found",
                "timestamp": timestamp,
            },
        )

    author = user_models.get_user_by_id(post.author_id)
    comments = post_models.get_comments_by_post(post_id)

    # 댓글 목록 변환
    comments_data = []
    for comment in comments:
        comment_author = user_models.get_user_by_id(comment.author_id)
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
                "updated_at": comment.updated_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
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
                "image_urls": post.image_urls,
                "author": {
                    "user_id": author.id if author else None,
                    "nickname": author.nickname if author else "탈퇴한 사용자",
                    "profileImageUrl": author.profileImageUrl if author else None,
                },
                "likes_count": post_models.get_post_likes_count(post_id),
                "created_at": post.created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "updated_at": post.updated_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
            "comments": comments_data,
        },
        "errors": [],
        "timestamp": timestamp,
    }


# 게시글 생성
async def create_post(
    post_data: CreatePostRequest,
    current_user,
    request: Request,
) -> dict:
    timestamp = get_request_timestamp(request)

    post = post_models.create_post(
        author_id=current_user.id,
        title=post_data.title,
        content=post_data.content,
        image_urls=post_data.image_urls,
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


# 게시글 수정
async def update_post(
    post_id: int,
    post_data: UpdatePostRequest,
    current_user,
    request: Request,
) -> dict:
    timestamp = get_request_timestamp(request)

    post = post_models.get_post_by_id(post_id)
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

    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "no_changes_provided",
                "timestamp": timestamp,
            },
        )

    updated_post = post_models.update_post(post_id, **updates)

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


# 게시글 삭제
async def delete_post(
    post_id: int,
    current_user,
    request: Request,
) -> dict:
    timestamp = get_request_timestamp(request)

    post = post_models.get_post_by_id(post_id)
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

    post_models.delete_post(post_id)

    return {
        "code": "POST_DELETED",
        "message": "게시글이 삭제되었습니다.",
        "data": {},
        "errors": [],
        "timestamp": timestamp,
    }


# 이미지 업로드
async def upload_image(
    file: UploadFile,
    current_user,
    request: Request,
) -> dict:
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

    # 파일 크기 검증 (스트리밍으로 읽으면서 확인)
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


# 게시글에 좋아요 추가
async def like_post(
    post_id: int,
    current_user,
    request: Request,
) -> dict:
    timestamp = get_request_timestamp(request)

    post = post_models.get_post_by_id(post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "post_not_found",
                "timestamp": timestamp,
            },
        )

    # 이미 좋아요를 눌렀는지 확인
    existing_like = post_models.get_like(post_id, current_user.id)
    if existing_like:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "already_liked",
                "message": "이미 좋아요를 누른 게시글입니다.",
                "timestamp": timestamp,
            },
        )

    post_models.add_like(post_id, current_user.id)

    return {
        "code": "LIKE_ADDED",
        "message": "좋아요가 추가되었습니다.",
        "data": {
            "likes_count": post_models.get_post_likes_count(post_id),
        },
        "errors": [],
        "timestamp": timestamp,
    }


# 좋아요 취소하기
async def unlike_post(
    post_id: int,
    current_user,
    request: Request,
) -> dict:
    timestamp = get_request_timestamp(request)

    post = post_models.get_post_by_id(post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "post_not_found",
                "timestamp": timestamp,
            },
        )

    # 좋아요를 눌렀는지 확인
    existing_like = post_models.get_like(post_id, current_user.id)
    if not existing_like:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "like_not_found",
                "message": "좋아요를 누르지 않은 게시글입니다.",
                "timestamp": timestamp,
            },
        )

    post_models.remove_like(post_id, current_user.id)

    return {
        "code": "LIKE_REMOVED",
        "message": "좋아요가 취소되었습니다.",
        "data": {
            "likes_count": post_models.get_post_likes_count(post_id),
        },
        "errors": [],
        "timestamp": timestamp,
    }


# ============ 댓글 관련 핸들러 ============


# 댓글 작성하기
async def create_comment(
    post_id: int,
    comment_data: CreateCommentRequest,
    current_user,
    request: Request,
) -> dict:
    timestamp = get_request_timestamp(request)

    post = post_models.get_post_by_id(post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "post_not_found",
                "timestamp": timestamp,
            },
        )

    comment = post_models.create_comment(
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


# 댓글 수정하기
async def update_comment(
    post_id: int,
    comment_id: int,
    comment_data: UpdateCommentRequest,
    current_user,
    request: Request,
) -> dict:
    timestamp = get_request_timestamp(request)

    # 게시글이 있는지 확인
    post = post_models.get_post_by_id(post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "post_not_found",
                "timestamp": timestamp,
            },
        )

    # 댓글이 있는지 확인
    comment = post_models.get_comment_by_id(comment_id)
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

    updated_comment = post_models.update_comment(comment_id, comment_data.content)

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


# 댓글 삭제하기
async def delete_comment(
    post_id: int,
    comment_id: int,
    current_user,
    request: Request,
) -> dict:
    timestamp = get_request_timestamp(request)

    # 게시글이 있는지 확인
    post = post_models.get_post_by_id(post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "post_not_found",
                "timestamp": timestamp,
            },
        )

    # 댓글이 있는지 확인
    comment = post_models.get_comment_by_id(comment_id)
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

    post_models.delete_comment(comment_id)

    return {
        "code": "COMMENT_DELETED",
        "message": "댓글이 삭제되었습니다.",
        "data": {},
        "errors": [],
        "timestamp": timestamp,
    }
