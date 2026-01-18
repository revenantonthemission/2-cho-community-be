# common_schemas: 공통 응답 모델

from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


# API 응답 모델
class APIResponse(BaseModel):
    code: str
    message: str
    data: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    timestamp: str = Field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
    )


# 사용자 데이터 모델
class UserData(BaseModel):
    user_id: int
    email: str
    nickname: str
    profileImageUrl: str
    name: str | None = None
