"""report_schemas: 신고 관련 Pydantic 모델 모듈."""

from pydantic import BaseModel, Field, field_validator


VALID_TARGET_TYPES = {"post", "comment"}
VALID_REASONS = {"spam", "abuse", "inappropriate", "other"}
VALID_RESOLVE_STATUSES = {"resolved", "dismissed"}


class CreateReportRequest(BaseModel):
    """신고 생성 요청 모델."""

    target_type: str = Field(..., description="신고 대상 타입 (post, comment)")
    target_id: int = Field(..., ge=1, description="신고 대상 ID")
    reason: str = Field(..., description="신고 사유 (spam, abuse, inappropriate, other)")
    description: str | None = Field(None, max_length=500, description="상세 설명 (선택)")

    @field_validator("target_type")
    @classmethod
    def validate_target_type(cls, v: str) -> str:
        if v not in VALID_TARGET_TYPES:
            raise ValueError(f"유효하지 않은 신고 대상입니다: {v}")
        return v

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        if v not in VALID_REASONS:
            raise ValueError(f"유효하지 않은 신고 사유입니다: {v}")
        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            return v if v else None
        return None


class ResolveReportRequest(BaseModel):
    """신고 처리 요청 모델."""

    status: str = Field(..., description="처리 상태 (resolved, dismissed)")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in VALID_RESOLVE_STATUSES:
            raise ValueError(f"유효하지 않은 처리 상태입니다: {v}")
        return v
