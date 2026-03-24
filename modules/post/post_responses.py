"""post_responses: 게시글 관련 응답 Pydantic 모델."""

from __future__ import annotations

from pydantic import BaseModel


class AuthorSummary(BaseModel):
    """게시글 작성자 요약 정보."""

    user_id: int | None = None
    nickname: str | None = None
    profileImageUrl: str | None = None
    distro: str | None = None


class TagSummary(BaseModel):
    """태그 요약 정보."""

    id: int
    name: str


class PostSummary(BaseModel):
    """게시글 목록 항목."""

    post_id: int
    title: str
    content: str
    image_url: str | None = None
    views_count: int = 0
    created_at: str
    updated_at: str | None = None
    author: AuthorSummary
    likes_count: int = 0
    comments_count: int = 0
    is_pinned: bool = False
    category_id: int | None = None
    category_name: str | None = None
    bookmarks_count: int = 0
    tags: list[TagSummary] = []
    is_read: bool = False


class PostListResult(BaseModel):
    """게시글 목록 조회 결과."""

    posts: list[PostSummary]
    total_count: int
    has_more: bool
    effective_sort: str | None = None
