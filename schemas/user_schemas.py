# user_schemas: 사용자 관련 Pydantic 모델

from pydantic import BaseModel, EmailStr, Field, field_validator
import re


# 사용자 등록 요청
class CreateUserRequest(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=20)
    nickname: str = Field(..., min_length=3, max_length=20)
    profileImageUrl: str | None = "/assets/default_profile.png"

    # 비밀번호는 대문자, 소문자, 숫자, 특수문자를 포함하여 8자 이상 20자 이하
    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        pattern = (
            r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,20}$"
        )
        if not re.match(pattern, v):
            raise ValueError(
                "비밀번호는 대문자, 소문자, 숫자, 특수문자를 포함하여 8자 이상 20자 이하여야 합니다."
            )
        return v

    # 닉네임은 3자 이상 20자 이하의 영문, 숫자, 언더바로 구성
    @field_validator("nickname")
    @classmethod
    def validate_nickname(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z0-9_]{3,20}$", v):
            raise ValueError(
                "닉네임은 3자 이상 20자 이하의 영문, 숫자, 언더바로 구성하여야 합니다."
            )
        return v

    # 프로필 이미지는 .jpg, .jpeg, .png로 구성
    @field_validator("profileImageUrl")
    @classmethod
    def validate_profile_image(cls, v: str | None) -> str:
        if v is None:
            return "/assets/default_profile.png"
        allowed_extensions = {".jpg", ".jpeg", ".png"}
        if not any(v.endswith(ext) for ext in allowed_extensions):
            raise ValueError("프로필 이미지는 .jpg, .jpeg, .png로 구성하여야 합니다.")
        return v


# 사용자 정보 수정 요청
class UpdateUserRequest(BaseModel):
    nickname: str | None = Field(None, min_length=3, max_length=20)
    email: EmailStr | None = None

    # 닉네임은 3자 이상 20자 이하의 영문, 숫자, 언더바로 구성
    @field_validator("nickname")
    @classmethod
    def validate_nickname(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not re.match(r"^[a-zA-Z0-9_]{3,20}$", v):
            raise ValueError(
                "닉네임은 3자 이상 20자 이하의 영문, 숫자, 언더바로 구성하여야 합니다."
            )
        return v


# 비밀번호 변경 요청
class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=20)
    new_password_confirm: str

    # 비밀번호는 대문자, 소문자, 숫자, 특수문자를 포함하여 8자 이상 20자 이하
    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        pattern = (
            r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,20}$"
        )
        if not re.match(pattern, v):
            raise ValueError(
                "비밀번호는 대문자, 소문자, 숫자, 특수문자를 포함하여 8자 이상 20자 이하로 구성하여야 합니다."
            )
        return v


# 사용자 탈퇴 요청
class WithdrawRequest(BaseModel):
    password: str
    agree: bool

    # 사용자가 계정을 삭제하기 전에 반드시 동의해야 함
    @field_validator("agree")
    @classmethod
    def must_agree(cls, v: bool) -> bool:
        if not v:
            raise ValueError("계정을 삭제하기 전에 반드시 동의하여야 합니다.")
        return v
