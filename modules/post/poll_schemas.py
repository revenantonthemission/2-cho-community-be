"""poll_schemas: 투표 관련 Pydantic 모델 모듈."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class PollCreate(BaseModel):
    """투표 생성 요청 모델."""

    question: str = Field(..., min_length=1, max_length=200)
    options: list[str] = Field(..., min_length=2, max_length=10)
    expires_at: datetime | None = None

    @field_validator("options")
    @classmethod
    def validate_options(cls, v: list[str]) -> list[str]:
        """옵션 유효성 검증."""
        if len(v) < 2:
            raise ValueError("옵션은 최소 2개 이상이어야 합니다.")
        if len(v) > 10:
            raise ValueError("옵션은 최대 10개까지 가능합니다.")
        validated = []
        for opt in v:
            opt = opt.strip()
            if not opt:
                raise ValueError("빈 옵션은 허용되지 않습니다.")
            if len(opt) > 100:
                raise ValueError("옵션은 100자 이내여야 합니다.")
            validated.append(opt)
        return validated


class PollVoteRequest(BaseModel):
    """투표 요청 모델."""

    option_id: int = Field(..., ge=1)
