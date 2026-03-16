"""package_schemas: 패키지/리뷰 관련 Pydantic 모델."""

from pydantic import BaseModel, Field, field_validator


VALID_PACKAGE_CATEGORIES = frozenset({
    'editor', 'terminal', 'devtool', 'system',
    'desktop', 'utility', 'multimedia', 'security',
})


class CreatePackageRequest(BaseModel):
    """패키지 등록 요청 스키마."""

    name: str = Field(..., min_length=1, max_length=100)
    display_name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(None, max_length=2000)
    homepage_url: str | None = Field(None, max_length=500)
    category: str
    package_manager: str | None = Field(None, max_length=20)

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        """카테고리 유효성을 검사합니다."""
        if v not in VALID_PACKAGE_CATEGORIES:
            raise ValueError("유효하지 않은 패키지 카테고리입니다.")
        return v


class UpdatePackageRequest(BaseModel):
    """패키지 수정 요청 스키마."""

    display_name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=2000)
    homepage_url: str | None = Field(None, max_length=500)
    category: str | None = None
    package_manager: str | None = Field(None, max_length=20)

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str | None) -> str | None:
        """카테고리 유효성을 검사합니다."""
        if v is None:
            return None
        if v not in VALID_PACKAGE_CATEGORIES:
            raise ValueError("유효하지 않은 패키지 카테고리입니다.")
        return v


class CreateReviewRequest(BaseModel):
    """리뷰 작성 요청 스키마."""

    rating: int = Field(..., ge=1, le=5)
    title: str = Field(..., min_length=2, max_length=200)
    content: str = Field(..., min_length=10, max_length=5000)


class UpdateReviewRequest(BaseModel):
    """리뷰 수정 요청 스키마."""

    rating: int | None = Field(None, ge=1, le=5)
    title: str | None = Field(None, min_length=2, max_length=200)
    content: str | None = Field(None, min_length=10, max_length=5000)
