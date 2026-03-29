"""tag_schemas: 태그 관련 요청/응답 스키마 모듈."""

from pydantic import BaseModel, Field


class UpdateTagRequest(BaseModel):
    """태그 설명 및 본문 수정 요청 스키마."""

    description: str | None = Field(None, max_length=200)
    body: str | None = Field(None, max_length=50000)
