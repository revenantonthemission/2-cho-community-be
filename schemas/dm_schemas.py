"""dm_schemas: DM 관련 Pydantic 모델 모듈."""

from pydantic import BaseModel, Field, field_validator


class CreateConversationRequest(BaseModel):
    """대화 시작 요청 모델."""

    recipient_id: int = Field(..., ge=1, description="대화 상대 사용자 ID")


class SendMessageRequest(BaseModel):
    """메시지 전송 요청 모델."""

    content: str = Field(..., min_length=1, max_length=2000, description="메시지 내용")

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("메시지 내용은 비어있을 수 없습니다.")
        return v
