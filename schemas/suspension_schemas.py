"""suspension_schemas: 계정 정지 관련 Pydantic 모델."""

from pydantic import BaseModel, Field, field_validator


class SuspendUserRequest(BaseModel):
    """사용자 정지 요청 모델."""

    duration_days: int = Field(..., ge=1, le=365, description="정지 기간 (일, 1~365)")
    reason: str = Field(..., min_length=1, max_length=500, description="정지 사유")

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("정지 사유를 입력해주세요.")
        return v
