"""social_auth_schemas: 소셜 로그인 관련 스키마."""

import re

from pydantic import BaseModel, Field, field_validator

_NICKNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_]{3,10}$")


class CompleteSignupRequest(BaseModel):
    """소셜 가입 닉네임 설정 요청."""

    nickname: str = Field(..., min_length=3, max_length=10)

    @field_validator("nickname")
    @classmethod
    def validate_nickname(cls, v: str) -> str:
        if not _NICKNAME_PATTERN.match(v):
            raise ValueError(
                "닉네임은 3자 이상 10자 이하의 영문, 숫자, 언더바로 구성하여야 합니다."
            )
        return v
