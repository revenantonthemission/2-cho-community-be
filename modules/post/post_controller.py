from fastapi import HTTPException, Request, UploadFile, status

from core.dependencies.request_context import get_request_timestamp
from core.utils.exceptions import not_found_error
from core.utils.pagination import validate_pagination
from core.utils.upload import save_file
from modules.post.post_models import ALLOWED_SORT_OPTIONS
from modules.post.post_schemas import CreatePostRequest, UpdatePostRequest
from modules.post.post_service import PostService
from modules.user.models import User
from schemas.common import create_response

# ============ 게시글 관련 핸들러 ============


async def get_posts(
    offset: int,
    limit: int,
    request: Request,
    search: str | None = None,
    sort: str = "latest",
    author_id: int | None = None,
    category_id: int | None = None,
    current_user: User | None = None,
    tag: str | None = None,
    following: bool = False,
) -> dict:
    """
    게시글 목록을 조회합니다.

    Args:
        offset (int): 조회 시작 위치 (0 이상)
        limit (int): 조회할 게시글 수 (1~100)
        request (Request): FastAPI Request 객체
        search (str | None): 검색어 (제목+내용). None이면 전체 조회.
        sort (str): 정렬 옵션 (latest, likes, views, comments).
        author_id (int | None): 작성자 ID로 필터링. None이면 전체 조회.

    Returns:
        dict: 게시글 목록과 페이지네이션 정보를 포함한 응답 딕셔너리

    Raises:
        HTTPException: offset이나 limit가 유효하지 않을 경우 400 에러 발생
    """
    timestamp = get_request_timestamp(request)

    # DB에서 음수 offset을 허용하면 의도치 않은 범위 조회가 발생할 수 있어 Controller에서 선제 차단
    # 상한선(100) 없이 허용하면 단일 요청으로 대량 데이터를 조회하는 남용을 막기 어려움
    validate_pagination(offset, limit, timestamp)

    # 공백만 있는 검색어는 None으로 정규화 — SQL LIKE '%  %' 같은 무의미한 쿼리 방지
    if search is not None:
        search = search.strip() or None

    # 클라이언트가 잘못된 정렬값을 보내도 400 대신 기본값으로 폴백 — UX 관용성 유지
    if sort not in ALLOWED_SORT_OPTIONS:
        sort = "latest"

    # Service Layer 호출
    result = await PostService.get_posts(
        offset,
        limit,
        search=search,
        sort=sort,
        author_id=author_id,
        category_id=category_id,
        current_user=current_user,
        tag=tag,
        following=following,
    )

    response_data = {
        "posts": [p.model_dump() for p in result.posts],
        "pagination": {
            "offset": offset,
            "limit": limit,
            "total_count": result.total_count,
            "has_more": result.has_more,
        },
    }

    # 추천 피드(following=True)에서 팔로우 중인 사용자가 없으면 최신순으로 폴백하는데,
    # 클라이언트가 실제로 어떤 정렬로 응답받았는지 알아야 UI를 올바르게 표시할 수 있음
    if result.effective_sort is not None:
        response_data["effective_sort"] = result.effective_sort

    return create_response(
        "POSTS_RETRIEVED",
        "게시글 목록 조회에 성공했습니다.",
        data=response_data,
        timestamp=timestamp,
    )


async def get_post(
    post_id: int,
    request: Request,
    current_user: User | None = None,
    comment_sort: str = "oldest",
) -> dict:
    """
    게시글 상세 정보를 조회합니다.

    Args:
        post_id (int): 조회할 게시글 ID
        request (Request): FastAPI Request 객체
        current_user (User | None, optional): 현재 로그인한 사용자 정보. Defaults to None.

    Returns:
        dict: 게시글 상세 정보를 포함한 응답 딕셔너리

    Raises:
        HTTPException: post_id가 유효하지 않거나(400), 게시글을 찾을 수 없는 경우(404)
    """
    timestamp = get_request_timestamp(request)

    # DB auto_increment는 1부터 시작하므로 0 이하는 존재할 수 없는 ID — Service 호출 전 빠른 거절
    if post_id < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_post_id",
                "timestamp": timestamp,
            },
        )

    # Service Layer 호출
    result_data = await PostService.get_post_detail(post_id, current_user, timestamp, comment_sort=comment_sort)

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
    """
    새 게시글을 생성합니다.

    Args:
        post_data (CreatePostRequest): 생성할 게시글 데이터 (제목, 내용, 이미지 URL 등)
        current_user (User): 현재 로그인한 사용자
        request (Request): FastAPI Request 객체

    Returns:
        dict: 생성된 게시글 ID를 포함한 응답 딕셔너리
    """
    timestamp = get_request_timestamp(request)

    # is_admin과 actor_nickname을 함께 전달해 Service에서 공지 카테고리 권한 검사 및 알림 생성에 활용
    post_id = await PostService.create_post(
        current_user.id,
        post_data,
        is_admin=current_user.is_admin,
        actor_nickname=current_user.nickname,
    )

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
    """
    게시글을 수정합니다.

    Args:
        post_id (int): 수정할 게시글 ID
        post_data (UpdatePostRequest): 수정할 게시글 데이터
        current_user (User): 현재 로그인한 사용자 (작성자 본인이어야 함)
        request (Request): FastAPI Request 객체

    Returns:
        dict: 수정된 게시글 데이터를 포함한 응답 딕셔너리

    Raises:
        HTTPException: 권한이 없거나 게시글이 없는 경우
    """
    timestamp = get_request_timestamp(request)

    # actor_nickname은 수정 이력(audit log) 및 알림 메시지 생성에 사용됨
    updated_data = await PostService.update_post(
        post_id,
        current_user.id,
        post_data.title,
        post_data.content,
        post_data.image_url,
        timestamp,
        category_id=post_data.category_id,
        image_urls=post_data.image_urls,
        tags=post_data.tags,
        actor_nickname=current_user.nickname,
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
    """
    게시글을 삭제합니다.

    Args:
        post_id (int): 삭제할 게시글 ID
        current_user (User): 현재 로그인한 사용자 (작성자 본인이어야 함)
        request (Request): FastAPI Request 객체

    Returns:
        dict: 삭제 성공 메시지를 포함한 응답 딕셔너리

    Raises:
        HTTPException: 권한이 없거나 게시글이 없는 경우
    """
    timestamp = get_request_timestamp(request)

    # is_admin을 전달해 관리자가 타인 게시글도 삭제할 수 있도록 허용
    # 실제 삭제는 soft delete(deleted_at 설정) 방식으로 처리됨
    await PostService.delete_post(
        post_id,
        current_user.id,
        timestamp,
        is_admin=current_user.is_admin,
    )

    return create_response("POST_DELETED", "게시글이 삭제되었습니다.", timestamp=timestamp)


async def upload_image(
    file: UploadFile,
    _current_user: User,
    request: Request,
) -> dict:
    """
    이미지를 업로드합니다.

    Args:
        file (UploadFile): 업로드할 이미지 파일
        current_user (User): 현재 로그인한 사용자
        request (Request): FastAPI Request 객체

    Returns:
        dict: 업로드된 이미지 URL을 포함한 응답 딕셔너리

    Raises:
        HTTPException: 파일 형식이 잘못되었거나 업로드 실패 시
    """
    timestamp = get_request_timestamp(request)

    try:
        url = await save_file(file, folder="posts")
    except HTTPException as e:
        # save_file이 반환하는 HTTPException의 detail에 timestamp를 주입해
        # 에러 응답 형식을 다른 엔드포인트와 일관되게 유지
        if isinstance(e.detail, dict):
            e.detail["timestamp"] = timestamp
        raise e

    return create_response(
        "IMAGE_UPLOADED",
        "이미지가 업로드되었습니다.",
        data={"url": url},
        timestamp=timestamp,
    )


async def get_related_posts(
    post_id: int,
    request: Request,
    limit: int = 5,
    current_user: User | None = None,
) -> dict:
    """현재 게시글과 관련된 게시글을 추천합니다.

    Args:
        post_id: 기준 게시글 ID.
        request: FastAPI Request 객체.
        limit: 추천 게시글 수 (1~10, 라우터에서 검증).
        current_user: 현재 인증된 사용자 (선택적).

    Returns:
        연관 게시글 목록이 포함된 응답.
    """
    timestamp = get_request_timestamp(request)

    posts = await PostService.get_related_posts(
        post_id,
        current_user=current_user,
        limit=limit,
    )

    # 기준 게시글 자체가 존재하지 않으면 연관 게시글도 의미 없으므로 404 반환
    if posts is None:
        raise not_found_error("post", timestamp)

    return create_response(
        "RELATED_POSTS_RETRIEVED",
        "연관 게시글 조회에 성공했습니다.",
        data={"posts": posts},
        timestamp=timestamp,
    )


async def pin_post(
    post_id: int,
    _current_user: User,
    request: Request,
) -> dict:
    """게시글을 고정합니다 (관리자 전용)."""
    timestamp = get_request_timestamp(request)

    # 권한 검사는 라우터의 require_admin 의존성에서 처리 — 여기서는 비즈니스 로직만 위임
    await PostService.pin_post(post_id, timestamp)

    return create_response("POST_PINNED", "게시글이 고정되었습니다.", timestamp=timestamp)


async def unpin_post(
    post_id: int,
    _current_user: User,
    request: Request,
) -> dict:
    """게시글 고정을 해제합니다 (관리자 전용)."""
    timestamp = get_request_timestamp(request)

    # 권한 검사는 라우터의 require_admin 의존성에서 처리 — 여기서는 비즈니스 로직만 위임
    await PostService.unpin_post(post_id, timestamp)

    return create_response("POST_UNPINNED", "게시글 고정이 해제되었습니다.", timestamp=timestamp)
