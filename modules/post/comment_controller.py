"""comment_controller: 댓글 관련 컨트롤러 모듈."""

from fastapi import Request

from core.dependencies.request_context import get_request_timestamp
from core.utils.formatters import format_datetime
from modules.post.comment_schemas import CreateCommentRequest, UpdateCommentRequest
from modules.post.comment_service import CommentService
from modules.user.models import User
from schemas.common import create_response


async def create_comment(
    post_id: int,
    comment_data: CreateCommentRequest,
    current_user: User,
    request: Request,
) -> dict:
    """새 댓글을 작성합니다.

    Args:
        post_id: 댓글을 작성할 게시글 ID.
        comment_data: 댓글 생성 정보 (내용, 부모 댓글 ID).
        current_user: 현재 인증된 사용자 객체.
        request: FastAPI Request 객체.

    Returns:
        생성된 댓글 정보가 포함된 응답 딕셔너리.

    Raises:
        HTTPException: 게시글 없으면 404, 대댓글 검증 실패 시 400.
    """
    timestamp = get_request_timestamp(request)

    # actor_nickname은 알림 생성에 재사용 — 서비스에서 User를 다시 조회하지 않도록 미리 전달
    comment = await CommentService.create_comment(
        post_id=post_id,
        user_id=current_user.id,
        content=comment_data.content,
        parent_id=comment_data.parent_id,
        actor_nickname=current_user.nickname,
        timestamp=timestamp,
    )

    return create_response(
        "COMMENT_CREATED",
        "댓글이 생성되었습니다.",
        # parent_id 포함 — 클라이언트가 대댓글 트리에 즉시 삽입할 수 있도록
        # created_at을 응답에 포함 — 클라이언트 측에서 별도 조회 없이 UI 렌더링 가능
        data={
            "comment_id": comment.id,
            "content": comment.content,
            "parent_id": comment.parent_id,
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

    # 댓글 수정 시에도 post_id 검증 — 댓글이 해당 게시글에 속하는지 확인
    updated_comment = await CommentService.update_comment(
        post_id=post_id,
        comment_id=comment_id,
        user_id=current_user.id,
        content=comment_data.content,
        timestamp=timestamp,
        actor_nickname=current_user.nickname,
    )

    return create_response(
        "COMMENT_UPDATED",
        "댓글이 수정되었습니다.",
        # updated_at 반환 — "방금 수정됨" 표시를 위해 클라이언트에서 서버 시각 사용
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
    is_admin: bool = False,
) -> dict:
    """댓글을 삭제합니다.

    Args:
        post_id: 게시글 ID.
        comment_id: 삭제할 댓글 ID.
        current_user: 현재 인증된 사용자 객체.
        request: FastAPI Request 객체.
        is_admin: 관리자 여부 (True면 작성자 검증 스킵).

    Returns:
        삭제 성공 응답 딕셔너리.

    Raises:
        HTTPException: 게시글/댓글 없으면 404, 권한 없으면 403, 불일치면 400.
    """
    timestamp = get_request_timestamp(request)

    # is_admin=True이면 작성자 검증 스킵 — 관리자가 타인의 댓글 삭제 시
    await CommentService.delete_comment(
        post_id=post_id,
        comment_id=comment_id,
        user_id=current_user.id,
        timestamp=timestamp,
        is_admin=is_admin,
    )

    return create_response("COMMENT_DELETED", "댓글이 삭제되었습니다.", timestamp=timestamp)
