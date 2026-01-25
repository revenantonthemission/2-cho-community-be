"""post_models: 게시글, 댓글, 좋아요 관련 데이터 모델 및 함수 모듈.

게시글, 댓글, 좋아요 데이터 클래스와 인메모리 저장소를 관리하는 함수들을 제공합니다.
"""

from dataclasses import dataclass, replace, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class Post:
    """게시글 데이터 클래스.

    Attributes:
        id: 게시글 고유 식별자.
        author_id: 작성자 ID.
        title: 제목.
        content: 내용.
        created_at: 생성 시간.
        updated_at: 수정 시간.
        image_urls: 첨부 이미지 URL 목록.
        is_deleted: 삭제 여부.
    """

    id: int
    author_id: int
    title: str
    content: str
    created_at: datetime
    updated_at: datetime
    image_urls: list[str] = field(default_factory=list)
    is_deleted: bool = False


@dataclass
class Comment:
    """댓글 데이터 클래스.

    Attributes:
        id: 댓글 고유 식별자.
        post_id: 게시글 ID.
        author_id: 작성자 ID.
        content: 내용.
        created_at: 생성 시간.
        updated_at: 수정 시간.
        is_deleted: 삭제 여부.
    """

    id: int
    post_id: int
    author_id: int
    content: str
    created_at: datetime
    updated_at: datetime
    is_deleted: bool = False


@dataclass
class Like:
    """좋아요 데이터 클래스.

    Attributes:
        id: 좋아요 고유 식별자.
        post_id: 게시글 ID.
        user_id: 사용자 ID.
        created_at: 생성 시간.
    """

    id: int
    post_id: int
    user_id: int
    created_at: datetime


# 인메모리 데이터 저장소
_posts: list[Post] = [
    Post(
        id=1,
        author_id=1,
        title="test",
        content="test",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
]
_comments: list[Comment] = []
_likes: list[Like] = []

# ID 카운터
_next_post_id = 1
_next_comment_id = 1
_next_like_id = 1


# ============ 게시글 관련 함수 ============


def get_posts(page: int = 0, limit: int = 20) -> list[Post]:
    """게시글 목록을 조회합니다.

    삭제되지 않은 게시글을 최신순으로 정렬하여 페이지네이션을 적용합니다.

    Args:
        page: 페이지 번호 (0부터 시작).
        limit: 페이지당 게시글 수.

    Returns:
        게시글 목록.
    """
    active_posts = [p for p in _posts if not p.is_deleted]
    sorted_posts = sorted(active_posts, key=lambda p: p.created_at, reverse=True)
    start = page * limit
    end = start + limit
    return sorted_posts[start:end]


def get_total_posts_count() -> int:
    """삭제되지 않은 게시글의 총 개수를 반환합니다.

    Returns:
        게시글 총 개수.
    """
    return len([p for p in _posts if not p.is_deleted])


def get_post_by_id(post_id: int) -> Post | None:
    """ID로 게시글을 조회합니다.

    Args:
        post_id: 조회할 게시글 ID.

    Returns:
        게시글 객체, 없거나 삭제된 경우 None.
    """
    return next((p for p in _posts if p.id == post_id and not p.is_deleted), None)


def create_post(
    author_id: int, title: str, content: str, image_urls: list[str] | None = None
) -> Post:
    """새 게시글을 생성합니다.

    Args:
        author_id: 작성자 ID.
        title: 제목.
        content: 내용.
        image_urls: 첨부 이미지 URL 목록 (선택).

    Returns:
        생성된 게시글 객체.
    """
    global _next_post_id

    now = datetime.now(timezone.utc)
    post = Post(
        id=_next_post_id,
        author_id=author_id,
        title=title,
        content=content,
        image_urls=image_urls or [],
        created_at=now,
        updated_at=now,
    )
    _posts.append(post)
    _next_post_id += 1
    return post


def update_post(post_id: int, **kwargs: Any) -> Post | None:
    """게시글을 수정합니다.

    Args:
        post_id: 수정할 게시글 ID.
        **kwargs: 수정할 필드와 값.

    Returns:
        수정된 게시글 객체, 없거나 삭제된 경우 None.
    """
    for i, post in enumerate(_posts):
        if post.id == post_id and not post.is_deleted:
            kwargs["updated_at"] = datetime.now(timezone.utc)
            updated_post = replace(post, **kwargs)
            _posts[i] = updated_post
            return updated_post
    return None


def delete_post(post_id: int) -> bool:
    """게시글을 삭제합니다.

    소프트 삭제를 수행하여 is_deleted를 True로 설정합니다.

    Args:
        post_id: 삭제할 게시글 ID.

    Returns:
        삭제 성공 여부.
    """
    for i, post in enumerate(_posts):
        if post.id == post_id and not post.is_deleted:
            _posts[i] = replace(post, is_deleted=True)
            return True
    return False


# ============ 좋아요 관련 함수 ============


def get_like(post_id: int, user_id: int) -> Like | None:
    """특정 사용자가 특정 게시글에 남긴 좋아요를 조회합니다.

    Args:
        post_id: 게시글 ID.
        user_id: 사용자 ID.

    Returns:
        좋아요 객체, 없으면 None.
    """
    return next(
        (
            like
            for like in _likes
            if like.post_id == post_id and like.user_id == user_id
        ),
        None,
    )


def get_post_likes_count(post_id: int) -> int:
    """게시글의 좋아요 개수를 조회합니다.

    Args:
        post_id: 게시글 ID.

    Returns:
        좋아요 개수.
    """
    return len([like for like in _likes if like.post_id == post_id])


def add_like(post_id: int, user_id: int) -> Like:
    """게시글에 좋아요를 추가합니다.

    Args:
        post_id: 게시글 ID.
        user_id: 사용자 ID.

    Returns:
        생성된 좋아요 객체.
    """
    global _next_like_id

    like = Like(
        id=_next_like_id,
        post_id=post_id,
        user_id=user_id,
        created_at=datetime.now(timezone.utc),
    )
    _likes.append(like)
    _next_like_id += 1
    return like


def remove_like(post_id: int, user_id: int) -> bool:
    """게시글 좋아요를 취소합니다.

    Args:
        post_id: 게시글 ID.
        user_id: 사용자 ID.

    Returns:
        취소 성공 여부.
    """
    global _likes
    original_count = len(_likes)
    _likes = [
        like
        for like in _likes
        if not (like.post_id == post_id and like.user_id == user_id)
    ]
    return len(_likes) < original_count


# ============ 댓글 관련 함수 ============


def get_comments_by_post(post_id: int) -> list[Comment]:
    """특정 게시글의 댓글 목록을 조회합니다.

    삭제되지 않은 댓글을 최신순으로 정렬하여 반환합니다.

    Args:
        post_id: 게시글 ID.

    Returns:
        댓글 목록.
    """
    comments = [c for c in _comments if c.post_id == post_id and not c.is_deleted]
    return sorted(comments, key=lambda c: c.created_at, reverse=True)


def get_comment_by_id(comment_id: int) -> Comment | None:
    """ID로 댓글을 조회합니다.

    Args:
        comment_id: 조회할 댓글 ID.

    Returns:
        댓글 객체, 없거나 삭제된 경우 None.
    """
    return next((c for c in _comments if c.id == comment_id and not c.is_deleted), None)


def create_comment(post_id: int, author_id: int, content: str) -> Comment:
    """새 댓글을 생성합니다.

    Args:
        post_id: 게시글 ID.
        author_id: 작성자 ID.
        content: 내용.

    Returns:
        생성된 댓글 객체.
    """
    global _next_comment_id

    now = datetime.now(timezone.utc)
    comment = Comment(
        id=_next_comment_id,
        post_id=post_id,
        author_id=author_id,
        content=content,
        created_at=now,
        updated_at=now,
    )
    _comments.append(comment)
    _next_comment_id += 1
    return comment


def update_comment(comment_id: int, content: str) -> Comment | None:
    """댓글을 수정합니다.

    Args:
        comment_id: 수정할 댓글 ID.
        content: 새 내용.

    Returns:
        수정된 댓글 객체, 없거나 삭제된 경우 None.
    """
    for i, comment in enumerate(_comments):
        if comment.id == comment_id and not comment.is_deleted:
            updated_comment = replace(
                comment, content=content, updated_at=datetime.now(timezone.utc)
            )
            _comments[i] = updated_comment
            return updated_comment
    return None


def delete_comment(comment_id: int) -> bool:
    """댓글을 삭제합니다.

    소프트 삭제를 수행하여 is_deleted를 True로 설정합니다.

    Args:
        comment_id: 삭제할 댓글 ID.

    Returns:
        삭제 성공 여부.
    """
    for i, comment in enumerate(_comments):
        if comment.id == comment_id and not comment.is_deleted:
            _comments[i] = replace(comment, is_deleted=True)
            return True
    return False


def clear_all_data() -> None:
    """테스트용 헬퍼 함수로, 인메모리 데이터를 초기화합니다."""
    global _posts, _comments, _likes, _next_post_id, _next_comment_id, _next_like_id
    _posts = []
    _comments = []
    _likes = []
    _next_post_id = 1
    _next_comment_id = 1
    _next_like_id = 1
