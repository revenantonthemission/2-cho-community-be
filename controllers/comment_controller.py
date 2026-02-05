"""comment_controller: 댓글 관련 컨트롤러 모듈."""

from fastapi import HTTPException, Request, status
from models import post_models, comment_models
from models.user_models import User
from schemas.comment_schemas import CreateCommentRequest, UpdateCommentRequest
from schemas.common import create_response
from dependencies.request_context import get_request_timestamp
from utils.formatters import format_datetime


async def _validate_comment_access(
    post_id: int,
    comment_id: int,
    current_user: User,
    timestamp: str,
    require_author: bool = True,
) -> comment_models.Comment:
    """댓글 접근 권한을 검증합니다.

    게시글 존재, 댓글 존재, 댓글-게시글 소속, 작성자 권한을 확인합니다.

    Args:
        post_id: 게시글 ID.
        comment_id: 댓글 ID.
        current_user: 현재 인증된 사용자 객체.
        timestamp: 요청 타임스탬프.
        require_author: 작성자 권한 확인 여부.

    Returns:
        검증된 댓글 객체.

    Raises:
        HTTPException: 검증 실패 시.
    """
    # 게시글 존재 확인
    post = await post_models.get_post_by_id(post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "post_not_found", "timestamp": timestamp},
        )

    # 댓글 존재 확인
    comment = await comment_models.get_comment_by_id(comment_id)
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "comment_not_found", "timestamp": timestamp},
        )

    # 댓글이 해당 게시글에 속하는지 확인
    if comment.post_id != post_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "comment_not_in_post", "timestamp": timestamp},
        )

    # 작성자 권한 확인
    if require_author and comment.author_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "not_author",
                "message": "댓글 작성자만 수정/삭제할 수 있습니다.",
                "timestamp": timestamp,
            },
        )

    return comment


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

    comment = await comment_models.create_comment(
        post_id=post_id,
        author_id=current_user.id,
        content=comment_data.content,
    )

    return create_response(
        "COMMENT_CREATED",
        "댓글이 생성되었습니다.",
        data={
            "comment_id": comment.id,
            "content": comment.content,
            "created_at": format_datetime(comment.created_at),
        },
        timestamp=timestamp,
    )


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

    # 공통 검증 로직
    await _validate_comment_access(post_id, comment_id, current_user, timestamp)

    updated_comment = await comment_models.update_comment(
        comment_id, comment_data.content
    )

    return create_response(
        "COMMENT_UPDATED",
        "댓글이 수정되었습니다.",
        data={
            "comment_id": updated_comment.id,
            "content": updated_comment.content,
            "updated_at": format_datetime(updated_comment.updated_at),
        },
        timestamp=timestamp,
    )


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

    # 공통 검증 로직
    await _validate_comment_access(post_id, comment_id, current_user, timestamp)

    await comment_models.delete_comment(comment_id)

    return create_response("COMMENT_DELETED", "댓글이 삭제되었습니다.", timestamp=timestamp)
