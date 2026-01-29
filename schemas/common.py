"""common: 공통 응답 Pydantic 모델 모듈.

API 응답 및 공통 데이터 모델을 정의합니다.
"""

from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class APIResponse(BaseModel):
    """표준 API 응답 모델.

    Attributes:
        code: 응답 코드.
        message: 응답 메시지.
        data: 응답 데이터.
        errors: 에러 목록.
        timestamp: 응답 타임스탬프.
    """

    code: str
    message: str
    data: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    timestamp: str = Field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
    )


class UserData(BaseModel):
    """사용자 정보 응답 모델.

    Attributes:
        user_id: 사용자 ID.
        email: 이메일 주소.
        nickname: 닉네임.
        profileImageUrl: 프로필 이미지 URL.
    """

    user_id: int
    email: str
    nickname: str
    profileImageUrl: str
