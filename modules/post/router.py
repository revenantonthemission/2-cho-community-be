"""post_router: 게시글, 댓글, 좋아요 관련 라우터 모듈.

게시글 CRUD, 이미지 업로드, 좋아요, 댓글 엔드포인트를 제공합니다.
"""

from fastapi import APIRouter, Depends, File, Path, Query, Request, UploadFile, status

from core.dependencies.auth import get_optional_user, require_admin, require_verified_email
from modules.post import (
    bookmark_controller,
    comment_controller,
    comment_like_controller,
    like_controller,
    poll_controller,
    post_controller,
    subscription_models,
)
from modules.post.comment_models import ALLOWED_COMMENT_SORT_OPTIONS
from modules.post.comment_schemas import CreateCommentRequest, UpdateCommentRequest
from modules.post.poll_schemas import PollVoteRequest
from modules.post.post_schemas import AcceptAnswerRequest, CreatePostRequest, UpdatePostRequest
from modules.post.subscription_schemas import SubscriptionRequest
from modules.user.models import User

post_router = APIRouter(prefix="/v1/posts", tags=["posts"])
"""게시글 관련 라우터 인스턴스."""


# ============ 게시글 라우터 ============


@post_router.get("/", status_code=status.HTTP_200_OK)
async def get_posts(
    request: Request,
    offset: int = Query(0, ge=0, description="시작 위치 (0부터 시작)"),
    limit: int = Query(10, ge=1, le=100, description="조회할 게시글 수"),
    search: str | None = Query(None, max_length=100, description="검색어 (제목+내용)"),
    sort: str = Query("latest", description="정렬: latest, likes, views, comments, hot"),
    author_id: int | None = Query(None, ge=1, description="작성자 ID로 필터링"),
    category_id: int | None = Query(None, ge=1, description="카테고리 ID로 필터링"),
    tag: str | None = Query(default=None, description="태그 이름으로 필터링"),
    following: bool = Query(False, description="팔로우한 사용자의 게시글만 조회"),
    current_user: User | None = Depends(get_optional_user),
) -> dict:
    """게시글 목록을 조회합니다.

    정렬 옵션에 따라 게시글을 페이지네이션하여 반환합니다.
    검색어가 있으면 제목+내용을 FULLTEXT 검색합니다.
    author_id가 있으면 해당 작성자의 글만 필터링합니다.
    category_id가 있으면 해당 카테고리의 글만 필터링합니다.

    Args:
        request: FastAPI Request 객체.
        offset: 시작 위치 (0부터 시작).
        limit: 조회할 게시글 수 (1~100, 기본 10).
        search: 검색어 (제목+내용, 최대 100자).
        sort: 정렬 옵션 (latest, likes, views, comments).
        author_id: 작성자 ID로 필터링 (선택).
        category_id: 카테고리 ID로 필터링 (선택).
        tag: 태그명으로 필터링 (선택).
        following: True이면 팔로우한 사용자의 게시글만 조회 (로그인 필요, 비로그인 시 무시).

    Returns:
        게시글 목록과 페이지네이션 정보가 포함된 응답.
    """
    return await post_controller.get_posts(
        offset,
        limit,
        request,
        search,
        sort,
        author_id=author_id,
        category_id=category_id,
        current_user=current_user,
        tag=tag,
        following=following,
    )


@post_router.get("/{post_id}/related", status_code=status.HTTP_200_OK)
async def get_related_posts(
    request: Request,
    post_id: int = Path(ge=1, description="게시글 ID"),
    limit: int = Query(5, ge=1, le=10, description="추천 게시글 수"),
    current_user: User | None = Depends(get_optional_user),
) -> dict:
    """현재 게시글과 관련된 게시글을 추천합니다.

    같은 태그/카테고리를 가진 게시글을 관련도 순으로 반환합니다.

    Args:
        request: FastAPI Request 객체.
        post_id: 기준 게시글 ID.
        limit: 추천 게시글 수 (1~10, 기본 5).
        current_user: 현재 인증된 사용자 (선택적).

    Returns:
        연관 게시글 목록이 포함된 응답.
    """
    return await post_controller.get_related_posts(
        post_id,
        request,
        limit=limit,
        current_user=current_user,
    )


@post_router.get("/{post_id}", status_code=status.HTTP_200_OK)
async def get_post(
    post_id: int,
    request: Request,
    current_user: User | None = Depends(get_optional_user),
    comment_sort: str = Query(
        default="oldest",
        description="댓글 정렬: oldest(오래된순), latest(최신순), popular(인기순)",
    ),
) -> dict:
    """특정 게시글의 상세 정보를 조회합니다.

    게시글 내용과 댓글 목록을 함께 반환합니다.
    로그인한 사용자의 경우 조회수가 증가합니다.

    Args:
        post_id: 조회할 게시글 ID.
        request: FastAPI Request 객체.
        current_user: 현재 인증된 사용자 (선택적).
        comment_sort: 댓글 정렬 옵션 (oldest, latest, popular).

    Returns:
        게시글 상세 정보와 댓글 목록이 포함된 응답.
    """
    if comment_sort not in ALLOWED_COMMENT_SORT_OPTIONS:
        comment_sort = "oldest"

    return await post_controller.get_post(post_id, request, current_user, comment_sort=comment_sort)


@post_router.post("/", status_code=status.HTTP_201_CREATED)
async def create_post(
    post_data: CreatePostRequest,
    request: Request,
    current_user: User = Depends(require_verified_email),
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
    current_user: User = Depends(require_verified_email),
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
    current_user: User = Depends(require_verified_email),
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
    current_user: User = Depends(require_verified_email),
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


# ============ 고정 라우터 (관리자 전용) ============


@post_router.patch("/{post_id}/pin", status_code=status.HTTP_200_OK)
async def pin_post(
    post_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
) -> dict:
    """게시글을 고정합니다 (관리자 전용)."""
    return await post_controller.pin_post(post_id, current_user, request)


@post_router.delete("/{post_id}/pin", status_code=status.HTTP_200_OK)
async def unpin_post(
    post_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
) -> dict:
    """게시글 고정을 해제합니다 (관리자 전용)."""
    return await post_controller.unpin_post(post_id, current_user, request)


# ============ 답변 채택 라우터 ============


@post_router.patch("/{post_id}/accepted-answer", status_code=status.HTTP_200_OK)
async def accept_answer(
    post_id: int,
    body: AcceptAnswerRequest,
    request: Request,
    current_user: User = Depends(require_verified_email),
) -> dict:
    """Q&A 게시글의 답변을 채택합니다 (게시글 작성자만 가능).

    Args:
        post_id: 게시글 ID.
        body: 채택할 댓글 ID를 포함한 요청.
        request: FastAPI Request 객체.
        current_user: 현재 인증된 사용자.

    Returns:
        채택 결과가 포함된 응답.
    """
    return await post_controller.accept_answer(post_id, body.comment_id, current_user, request)


@post_router.delete("/{post_id}/accepted-answer", status_code=status.HTTP_200_OK)
async def unaccept_answer(
    post_id: int,
    request: Request,
    current_user: User = Depends(require_verified_email),
) -> dict:
    """Q&A 게시글의 답변 채택을 해제합니다 (게시글 작성자만 가능).

    Args:
        post_id: 게시글 ID.
        request: FastAPI Request 객체.
        current_user: 현재 인증된 사용자.

    Returns:
        채택 해제 결과가 포함된 응답.
    """
    return await post_controller.unaccept_answer(post_id, current_user, request)


# ============ 좋아요 라우터 ============


@post_router.post("/{post_id}/likes", status_code=status.HTTP_201_CREATED)
async def like_post(
    post_id: int,
    request: Request,
    current_user: User = Depends(require_verified_email),
) -> dict:
    """게시글에 좋아요를 추가합니다.

    Args:
        post_id: 좋아요할 게시글 ID.
        request: FastAPI Request 객체.
        current_user: 현재 인증된 사용자.

    Returns:
        좋아요 개수가 포함된 응답.
    """
    return await like_controller.like_post(post_id, current_user, request)


@post_router.delete("/{post_id}/likes", status_code=status.HTTP_200_OK)
async def unlike_post(
    post_id: int,
    request: Request,
    current_user: User = Depends(require_verified_email),
) -> dict:
    """게시글 좋아요를 취소합니다.

    Args:
        post_id: 좋아요 취소할 게시글 ID.
        request: FastAPI Request 객체.
        current_user: 현재 인증된 사용자.

    Returns:
        좋아요 개수가 포함된 응답.
    """
    return await like_controller.unlike_post(post_id, current_user, request)


# ============ 댓글 라우터 ============


@post_router.post("/{post_id}/comments", status_code=status.HTTP_201_CREATED)
async def create_comment(
    post_id: int,
    comment_data: CreateCommentRequest,
    request: Request,
    current_user: User = Depends(require_verified_email),
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
    return await comment_controller.create_comment(post_id, comment_data, current_user, request)


@post_router.put("/{post_id}/comments/{comment_id}", status_code=status.HTTP_200_OK)
async def update_comment(
    post_id: int,
    comment_id: int,
    comment_data: UpdateCommentRequest,
    request: Request,
    current_user: User = Depends(require_verified_email),
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
    return await comment_controller.update_comment(post_id, comment_id, comment_data, current_user, request)


@post_router.delete("/{post_id}/comments/{comment_id}", status_code=status.HTTP_200_OK)
async def delete_comment(
    post_id: int,
    comment_id: int,
    request: Request,
    current_user: User = Depends(require_verified_email),
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
    return await comment_controller.delete_comment(
        post_id,
        comment_id,
        current_user,
        request,
        is_admin=current_user.is_admin,
    )


# ============ 북마크 라우터 ============


@post_router.post("/{post_id}/bookmark", status_code=status.HTTP_201_CREATED)
async def bookmark_post(
    post_id: int,
    request: Request,
    current_user: User = Depends(require_verified_email),
) -> dict:
    """게시글을 북마크에 추가합니다."""
    return await bookmark_controller.bookmark_post(post_id, current_user, request)


@post_router.delete("/{post_id}/bookmark", status_code=status.HTTP_200_OK)
async def unbookmark_post(
    post_id: int,
    request: Request,
    current_user: User = Depends(require_verified_email),
) -> dict:
    """북마크를 해제합니다."""
    return await bookmark_controller.unbookmark_post(post_id, current_user, request)


# ============ 구독 라우터 ============


@post_router.get("/{post_id}/subscription", status_code=status.HTTP_200_OK)
async def get_subscription(
    post_id: int,
    current_user: User = Depends(require_verified_email),
) -> dict:
    """현재 사용자의 게시글 구독 수준을 조회합니다."""
    level = await subscription_models.get_subscription_level(current_user.id, post_id)
    return {"post_id": post_id, "level": level}


@post_router.put("/{post_id}/subscription", status_code=status.HTTP_200_OK)
async def set_subscription(
    post_id: int,
    body: SubscriptionRequest,
    current_user: User = Depends(require_verified_email),
) -> dict:
    """게시글 구독 수준을 설정합니다 (watching 또는 muted)."""
    await subscription_models.set_subscription(current_user.id, post_id, body.level)
    return {"post_id": post_id, "level": body.level}


@post_router.delete("/{post_id}/subscription", status_code=status.HTTP_200_OK)
async def delete_subscription(
    post_id: int,
    current_user: User = Depends(require_verified_email),
) -> dict:
    """구독을 해제하여 기본 상태(normal)로 되돌립니다."""
    await subscription_models.delete_subscription(current_user.id, post_id)
    return {"post_id": post_id, "level": "normal"}


# ============ 댓글 좋아요 라우터 ============


@post_router.post("/{post_id}/comments/{comment_id}/like", status_code=status.HTTP_201_CREATED)
async def like_comment(
    post_id: int,
    comment_id: int,
    request: Request,
    current_user: User = Depends(require_verified_email),
) -> dict:
    """댓글에 좋아요를 추가합니다."""
    return await comment_like_controller.like_comment(post_id, comment_id, current_user, request)


@post_router.delete("/{post_id}/comments/{comment_id}/like", status_code=status.HTTP_200_OK)
async def unlike_comment(
    post_id: int,
    comment_id: int,
    request: Request,
    current_user: User = Depends(require_verified_email),
) -> dict:
    """댓글 좋아요를 취소합니다."""
    return await comment_like_controller.unlike_comment(post_id, comment_id, current_user, request)


# ============ 투표 라우터 ============


@post_router.post("/{post_id}/poll/vote", status_code=status.HTTP_200_OK)
async def vote_on_poll(
    post_id: int,
    vote_data: PollVoteRequest,
    request: Request,
    current_user: User = Depends(require_verified_email),
) -> dict:
    """게시글의 투표에 참여합니다."""
    return await poll_controller.vote_on_poll(post_id, vote_data, current_user, request)


@post_router.delete("/{post_id}/poll/vote", status_code=status.HTTP_200_OK)
async def cancel_poll_vote(
    post_id: int,
    request: Request,
    current_user: User = Depends(require_verified_email),
) -> dict:
    """투표를 취소합니다."""
    return await poll_controller.cancel_vote(post_id, current_user, request)


@post_router.put("/{post_id}/poll/vote", status_code=status.HTTP_200_OK)
async def change_poll_vote(
    post_id: int,
    vote_data: PollVoteRequest,
    request: Request,
    current_user: User = Depends(require_verified_email),
) -> dict:
    """투표를 변경합니다."""
    return await poll_controller.change_vote(post_id, vote_data, current_user, request)
