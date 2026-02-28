"""auth_schemas: 인증 관련 Pydantic 모델 모듈.

로그인 요청 스키마를 정의합니다.
"""

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    """로그인 요청 모델.

    Attributes:
        email: 사용자 이메일 주소.
        password: 비밀번호.
    """

    email: EmailStr
    password: str
