"""wiki_schemas: 위키 관련 Pydantic 모델."""

import re

from pydantic import BaseModel, Field, field_validator


_SLUG_RE = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')


class CreateWikiPageRequest(BaseModel):
    """위키 페이지 생성 요청 스키마."""

    title: str = Field(..., min_length=2, max_length=200)
    slug: str = Field(..., min_length=2, max_length=200)
    content: str = Field(..., min_length=10, max_length=50000)
    tags: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        """슬러그 형식을 검증합니다 (영문 소문자, 숫자, 하이픈만 허용)."""
        if not _SLUG_RE.match(v):
            raise ValueError("슬러그는 영문 소문자, 숫자, 하이픈만 사용할 수 있습니다.")
        return v

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str]) -> list[str]:
        """태그 이름을 정규화합니다."""
        return [t.strip().lower() for t in v if t.strip()]


class UpdateWikiPageRequest(BaseModel):
    """위키 페이지 편집 요청 스키마."""

    title: str | None = Field(None, min_length=2, max_length=200)
    content: str | None = Field(None, min_length=10, max_length=50000)
    tags: list[str] | None = Field(None, max_length=10)

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str] | None) -> list[str] | None:
        """태그 이름을 정규화합니다."""
        if v is None:
            return None
        return [t.strip().lower() for t in v if t.strip()]
