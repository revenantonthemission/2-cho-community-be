# auth_schemas: 인증 관련 Pydantic 모델

from pydantic import BaseModel, EmailStr


# 로그인 요청
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# 로그아웃 응답
class LogoutResponse(BaseModel):
    code: str = "LOGOUT_SUCCESS"
    message: str = "로그아웃에 성공했습니다."
