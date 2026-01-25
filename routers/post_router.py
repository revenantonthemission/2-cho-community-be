"""post_router: 게시글, 댓글, 좋아요 관련 라우터 모듈.

게시글 CRUD, 이미지 업로드, 좋아요, 댓글 엔드포인트를 제공합니다.
"""

from fastapi import APIRouter, Depends, Query, Request, UploadFile, File, status
from controllers import post_controller
from dependencies.auth import get_current_user
from models.user_models import User
from schemas.post_schemas import CreatePostRequest, UpdatePostRequest
from schemas.comment_schemas import CreateCommentRequest, UpdateCommentRequest


post_router = APIRouter(prefix="/v1/posts", tags=["posts"])
"""게시글 관련 라우터 인스턴스."""


# ============ 게시글 라우터 ============


@post_router.get("/", status_code=status.HTTP_200_OK)
async def get_posts(
    request: Request,
    page: int = Query(0, ge=0, description="페이지 번호 (0부터 시작)"),
    limit: int = Query(20, ge=1, le=100, description="페이지당 게시글 수"),
) -> dict:
    """게시글 목록을 조회합니다.

    최신순으로 정렬된 게시글을 페이지네이션하여 반환합니다.

    Args:
        request: FastAPI Request 객체.
        page: 페이지 번호 (0부터 시작).
        limit: 페이지당 게시글 수 (1~100).

    Returns:
        게시글 목록과 페이지네이션 정보가 포함된 응답.
    """
    return await post_controller.get_posts(page, limit, request)


@post_router.get("/{post_id}", status_code=status.HTTP_200_OK)
async def get_post(post_id: int, request: Request) -> dict:
    """특정 게시글의 상세 정보를 조회합니다.

    게시글 내용과 댓글 목록을 함께 반환합니다.

    Args:
        post_id: 조회할 게시글 ID.
        request: FastAPI Request 객체.

    Returns:
        게시글 상세 정보와 댓글 목록이 포함된 응답.
    """
    return await post_controller.get_post(post_id, request)


@post_router.post("/", status_code=status.HTTP_201_CREATED)
async def create_post(
    post_data: CreatePostRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> dict:
    """새 게시글을 생성합니다.

    Args:
        post_data: 게시글 생성 정보 (제목, 내용, 이미지 URL).
        request: FastAPI Request 객체.
        current_user: 현재 인증된 사용자.

    Returns:
        생성된 게시글 ID가 포함된 응답.
    """
    return await post_controller.create_post(post_data, current_user, request)


@post_router.patch("/{post_id}", status_code=status.HTTP_200_OK)
async def update_post(
    post_id: int,
    post_data: UpdatePostRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> dict:
    """게시글을 수정합니다.

    Args:
        post_id: 수정할 게시글 ID.
        post_data: 수정할 정보 (제목, 내용).
        request: FastAPI Request 객체.
        current_user: 현재 인증된 사용자.

    Returns:
        수정된 게시글 정보가 포함된 응답.
    """
    return await post_controller.update_post(post_id, post_data, current_user, request)


@post_router.delete("/{post_id}", status_code=status.HTTP_200_OK)
async def delete_post(
    post_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> dict:
    """게시글을 삭제합니다.

    Args:
        post_id: 삭제할 게시글 ID.
        request: FastAPI Request 객체.
        current_user: 현재 인증된 사용자.

    Returns:
        삭제 성공 응답.
    """
    return await post_controller.delete_post(post_id, current_user, request)


@post_router.post("/image", status_code=status.HTTP_201_CREATED)
async def upload_image(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> dict:
    """이미지를 업로드합니다.

    Args:
        request: FastAPI Request 객체.
        file: 업로드할 이미지 파일.
        current_user: 현재 인증된 사용자.

    Returns:
        업로드된 이미지 URL이 포함된 응답.
    """
    return await post_controller.upload_image(file, current_user, request)


# ============ 좋아요 라우터 ============


@post_router.post("/{post_id}/likes", status_code=status.HTTP_201_CREATED)
async def like_post(
    post_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> dict:
    """게시글에 좋아요를 추가합니다.

    Args:
        post_id: 좋아요할 게시글 ID.
        request: FastAPI Request 객체.
        current_user: 현재 인증된 사용자.

    Returns:
        좋아요 개수가 포함된 응답.
    """
    return await post_controller.like_post(post_id, current_user, request)


@post_router.delete("/{post_id}/likes", status_code=status.HTTP_200_OK)
async def unlike_post(
    post_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> dict:
    """게시글 좋아요를 취소합니다.

    Args:
        post_id: 좋아요 취소할 게시글 ID.
        request: FastAPI Request 객체.
        current_user: 현재 인증된 사용자.

    Returns:
        좋아요 개수가 포함된 응답.
    """
    return await post_controller.unlike_post(post_id, current_user, request)


# ============ 댓글 라우터 ============


@post_router.post("/{post_id}/comments", status_code=status.HTTP_201_CREATED)
async def create_comment(
    post_id: int,
    comment_data: CreateCommentRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> dict:
    """새 댓글을 작성합니다.

    Args:
        post_id: 댓글을 작성할 게시글 ID.
        comment_data: 댓글 내용.
        request: FastAPI Request 객체.
        current_user: 현재 인증된 사용자.

    Returns:
        생성된 댓글 정보가 포함된 응답.
    """
    return await post_controller.create_comment(
        post_id, comment_data, current_user, request
    )


@post_router.put("/{post_id}/comments/{comment_id}", status_code=status.HTTP_200_OK)
async def update_comment(
    post_id: int,
    comment_id: int,
    comment_data: UpdateCommentRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> dict:
    """댓글을 수정합니다.

    Args:
        post_id: 게시글 ID.
        comment_id: 수정할 댓글 ID.
        comment_data: 수정할 내용.
        request: FastAPI Request 객체.
        current_user: 현재 인증된 사용자.

    Returns:
        수정된 댓글 정보가 포함된 응답.
    """
    return await post_controller.update_comment(
        post_id, comment_id, comment_data, current_user, request
    )


@post_router.delete("/{post_id}/comments/{comment_id}", status_code=status.HTTP_200_OK)
async def delete_comment(
    post_id: int,
    comment_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> dict:
    """댓글을 삭제합니다.

    Args:
        post_id: 게시글 ID.
        comment_id: 삭제할 댓글 ID.
        request: FastAPI Request 객체.
        current_user: 현재 인증된 사용자.

    Returns:
        삭제 성공 응답.
    """
    return await post_controller.delete_comment(
        post_id, comment_id, current_user, request
    )
