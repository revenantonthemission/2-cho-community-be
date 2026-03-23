"""recovery_schemas: 계정 찾기 관련 Pydantic 모델.

이메일 찾기(닉네임 기반)와 비밀번호 찾기(이메일 기반)
요청 검증을 위한 스키마를 정의합니다.
"""

from pydantic import BaseModel, EmailStr, Field, field_validator


class FindEmailRequest(BaseModel):
    """이메일 찾기 요청 모델.

    Attributes:
        nickname: 가입 시 사용한 닉네임.
    """

    nickname: str = Field(..., min_length=1, max_length=10)

    @field_validator("nickname")
    @classmethod
    def strip_nickname(cls, v: str) -> str:
        """닉네임 앞뒤 공백을 제거합니다."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("닉네임을 입력해주세요.")
        return stripped


class FindPasswordRequest(BaseModel):
    """비밀번호 찾기 요청 모델.

    Attributes:
        email: 가입 시 사용한 이메일 주소.
    """

    email: EmailStr
