# post_models: 게시글, 댓글, 좋아요 관련 데이터 모델 및 함수

from dataclasses import dataclass, replace, field
from datetime import datetime, timezone
from typing import List


# 게시물 데이터 클래스
@dataclass
class Post:
    id: int
    author_id: int
    title: str
    content: str
    created_at: datetime
    updated_at: datetime
    image_urls: List[str] = field(default_factory=list)
    is_deleted: bool = False


# 댓글 데이터 클래스
@dataclass
class Comment:
    id: int
    post_id: int
    author_id: int
    content: str
    created_at: datetime
    updated_at: datetime
    is_deleted: bool = False


# 좋아요 데이터 클래스
@dataclass
class Like:
    id: int
    post_id: int
    user_id: int
    created_at: datetime


# 인메모리 데이터 저장소
_posts: List[Post] = []
_comments: List[Comment] = []
_likes: List[Like] = []

# ID 카운터
_next_post_id = 1
_next_comment_id = 1
_next_like_id = 1


# ============ 게시글 관련 함수 ============


# 게시글 목록 조회하기 (페이지네이션, 최신순 정렬)
def get_posts(page: int = 0, limit: int = 20) -> List[Post]:
    # 삭제되지 않은 게시글만 필터링
    active_posts = [p for p in _posts if not p.is_deleted]
    # 최신순 정렬
    sorted_posts = sorted(active_posts, key=lambda p: p.created_at, reverse=True)
    # 페이지네이션 적용
    start = page * limit
    end = start + limit
    return sorted_posts[start:end]


# 삭제되지 않은 게시글의 총 개수 반환하기
def get_total_posts_count() -> int:
    return len([p for p in _posts if not p.is_deleted])


# ID로 게시글 조회하기
def get_post_by_id(post_id: int) -> Post | None:
    return next((p for p in _posts if p.id == post_id and not p.is_deleted), None)


# 새 게시글 생성하기
def create_post(
    author_id: int, title: str, content: str, image_urls: List[str] | None = None
) -> Post:
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


# 게시글 수정하기
def update_post(post_id: int, **kwargs) -> Post | None:
    for i, post in enumerate(_posts):
        if post.id == post_id and not post.is_deleted:
            # updated_at을 현재 시간으로 설정
            kwargs["updated_at"] = datetime.now(timezone.utc)
            updated_post = replace(post, **kwargs)
            _posts[i] = updated_post
            return updated_post
    return None


# 게시글 소프트 삭제
def delete_post(post_id: int) -> bool:
    for i, post in enumerate(_posts):
        if post.id == post_id and not post.is_deleted:
            _posts[i] = replace(post, is_deleted=True)
            return True
    return False


# ============ 좋아요 관련 함수 ============


# 특정 사용자가 특정 게시글에 남긴 좋아요 조회
def get_like(post_id: int, user_id: int) -> Like | None:
    return next(
        (
            like
            for like in _likes
            if like.post_id == post_id and like.user_id == user_id
        ),
        None,
    )


# 게시글의 좋아요 개수 조회
def get_post_likes_count(post_id: int) -> int:
    return len([like for like in _likes if like.post_id == post_id])


# 게시글에 좋아요 추가
def add_like(post_id: int, user_id: int) -> Like:
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


# 게시글 좋아요 취소하기
def remove_like(post_id: int, user_id: int) -> bool:
    global _likes
    original_count = len(_likes)
    _likes = [
        like
        for like in _likes
        if not (like.post_id == post_id and like.user_id == user_id)
    ]
    return len(_likes) < original_count


# ============ 댓글 관련 함수 ============


# 특정 게시글의 댓글 목록 조회 (최신순 정렬)
def get_comments_by_post(post_id: int) -> List[Comment]:
    comments = [c for c in _comments if c.post_id == post_id and not c.is_deleted]
    return sorted(comments, key=lambda c: c.created_at, reverse=True)


# ID로 댓글 조회
def get_comment_by_id(comment_id: int) -> Comment | None:
    return next((c for c in _comments if c.id == comment_id and not c.is_deleted), None)


# 새 댓글 만들기
def create_comment(post_id: int, author_id: int, content: str) -> Comment:
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


# 댓글 수정하기
def update_comment(comment_id: int, content: str) -> Comment | None:
    for i, comment in enumerate(_comments):
        if comment.id == comment_id and not comment.is_deleted:
            updated_comment = replace(
                comment, content=content, updated_at=datetime.now(timezone.utc)
            )
            _comments[i] = updated_comment
            return updated_comment
    return None


# 댓글 삭제하기
def delete_comment(comment_id: int) -> bool:
    for i, comment in enumerate(_comments):
        if comment.id == comment_id and not comment.is_deleted:
            _comments[i] = replace(comment, is_deleted=True)
            return True
    return False


# 테스트용 헬퍼 함수. 인메모리 데이터를 초기화하는 역할을 한다.
def clear_all_data():
    global _posts, _comments, _likes, _next_post_id, _next_comment_id, _next_like_id
    _posts = []
    _comments = []
    _likes = []
    _next_post_id = 1
    _next_comment_id = 1
    _next_like_id = 1
