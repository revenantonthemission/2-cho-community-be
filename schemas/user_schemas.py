"""user_schemas: 사용자 관련 Pydantic 모델 모듈.

사용자 등록, 수정, 비밀번호 변경, 탈퇴 요청 스키마를 정의합니다.
"""

from pydantic import BaseModel, EmailStr, Field, field_validator
import re

_PASSWORD_PATTERN = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,20}$"
)
_PASSWORD_ERROR = (
    "비밀번호는 대문자, 소문자, 숫자, 특수문자(@, $, !, %, *, ?, &)를 "
    "포함하여 8자 이상 20자 이하여야 합니다."
)

_NICKNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_]{3,10}$")
_NICKNAME_ERROR = (
    "닉네임은 3자 이상 10자 이하의 영문, 숫자, 언더바로 구성하여야 합니다."
)


def _validate_password(v: str) -> str:
    """비밀번호 형식을 검증합니다.

    Args:
        v: 입력된 비밀번호.

    Returns:
        검증된 비밀번호.

    Raises:
        ValueError: 비밀번호 형식이 올바르지 않은 경우.
    """
    if not _PASSWORD_PATTERN.match(v):
        raise ValueError(_PASSWORD_ERROR)
    return v


class CreateUserRequest(BaseModel):
    """사용자 등록 요청 모델.

    Attributes:
        email: 이메일 주소.
        password: 비밀번호 (8~20자, 대/소문자/숫자/특수문자 포함).
        nickname: 닉네임 (3~10자, 영문/숫자/언더바).
        profileImageUrl: 프로필 이미지 URL.
    """

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=20)
    nickname: str = Field(..., min_length=3, max_length=10)
    profileImageUrl: str | None = "/assets/profiles/default_profile.jpg"

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _validate_password(v)

    @field_validator("nickname")
    @classmethod
    def validate_nickname(cls, v: str) -> str:
        """닉네임 형식을 검증합니다."""
        if not _NICKNAME_PATTERN.match(v):
            raise ValueError(_NICKNAME_ERROR)
        return v

    @field_validator("profileImageUrl")
    @classmethod
    def validate_profile_image(cls, v: str | None) -> str:
        """프로필 이미지 URL 형식을 검증합니다.

        Args:
            v: 입력된 프로필 이미지 URL.

        Returns:
            검증된 프로필 이미지 URL.

        Raises:
            ValueError: 이미지 형식이 올바르지 않은 경우.
        """
        if v is None:
            return "/assets/profiles/default_profile.jpg"
        allowed_extensions = {".jpg", ".jpeg", ".png"}
        if not any(v.endswith(ext) for ext in allowed_extensions):
            raise ValueError("프로필 이미지는 .jpg, .jpeg, .png로 구성하여야 합니다.")
        return v


class UpdateUserRequest(BaseModel):
    """사용자 정보 수정 요청 모델.

    Attributes:
        nickname: 새 닉네임 (선택).
        profileImageUrl: 새 프로필 이미지 URL (선택) - 문자열 또는 {"url": "..."} 객체.
    """

    nickname: str | None = Field(None, min_length=3, max_length=10)
    profileImageUrl: str | dict | None = None

    @field_validator("nickname")
    @classmethod
    def validate_nickname(cls, v: str | None) -> str | None:
        """닉네임 형식을 검증합니다."""
        if v is None:
            return None
        if not _NICKNAME_PATTERN.match(v):
            raise ValueError(_NICKNAME_ERROR)
        return v

    @field_validator("profileImageUrl")
    @classmethod
    def validate_profile_image_url(cls, v: str | dict | None) -> str | None:
        """프로필 이미지 URL을 추출합니다.
        객체 형태 {"url": "..."} 또는 문자열 모두 처리합니다.

        Args:
            v: 입력된 프로필 이미지 URL.

        Returns:
            추출된 URL 문자열 또는 None.
        """
        if v is None:
            return None
        if isinstance(v, dict):
            return v.get("url")
        return v


class ChangePasswordRequest(BaseModel):
    """비밀번호 변경 요청 모델.

    Attributes:
        new_password: 새 비밀번호.
        new_password_confirm: 새 비밀번호 확인.
    """

    new_password: str = Field(..., min_length=8, max_length=20)
    new_password_confirm: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        return _validate_password(v)


class WithdrawRequest(BaseModel):
    """사용자 탈퇴 요청 모델.

    Attributes:
        password: 현재 비밀번호.
        agree: 탈퇴 동의 여부.
    """

    password: str
    agree: bool

    @field_validator("agree")
    @classmethod
    def must_agree(cls, v: bool) -> bool:
        """탈퇴 동의 여부를 검증합니다.

        Args:
            v: 동의 여부.

        Returns:
            검증된 동의 여부.

        Raises:
            ValueError: 동의하지 않은 경우.
        """
        if not v:
            raise ValueError("계정을 삭제하기 전에 반드시 동의하여야 합니다.")
        return v
