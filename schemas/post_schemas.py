"""post_schemas: 게시글 관련 Pydantic 모델 모듈.

게시글 생성, 수정 요청 스키마를 정의합니다.
"""

from pydantic import BaseModel, Field, field_validator

from schemas._image_validators import validate_upload_image_url


class CreatePostRequest(BaseModel):
    """게시글 생성 요청 모델.

    Attributes:
        title: 게시글 제목 (3~100자).
        content: 게시글 내용 (1~10000자).
        image_url: 첨부 이미지 URL (선택, 최대 1개).
    """

    title: str = Field(..., min_length=3, max_length=100)
    content: str = Field(..., min_length=1, max_length=10000)
    image_url: str | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        """제목 형식을 검증합니다.

        Args:
            v: 입력된 제목.

        Returns:
            공백이 제거된 검증된 제목.

        Raises:
            ValueError: 제목이 3자 미만인 경우.
        """
        v = v.strip()
        if len(v) < 3:
            raise ValueError("제목은 최소 3자 이상이어야 합니다.")
        return v

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        """내용 형식을 검증합니다.

        Args:
            v: 입력된 내용.

        Returns:
            공백이 제거된 검증된 내용.

        Raises:
            ValueError: 내용이 1자 미만인 경우.
        """
        v = v.strip()
        if len(v) < 1:
            raise ValueError("내용은 최소 1자 이상이어야 합니다.")
        return v

    @field_validator("image_url")
    @classmethod
    def validate_image_url(cls, v: str | None) -> str | None:
        """이미지 URL 형식을 검증합니다."""
        return validate_upload_image_url(v)


class UpdatePostRequest(BaseModel):
    """게시글 수정 요청 모델.

    Attributes:
        title: 새 제목 (선택, 3~100자).
        content: 새 내용 (선택, 1~10000자).
    """

    title: str | None = Field(None, min_length=3, max_length=100)
    content: str | None = Field(None, min_length=1, max_length=10000)
    image_url: str | None = None

    @field_validator("image_url")
    @classmethod
    def validate_image_url(cls, v: str | None) -> str | None:
        """이미지 URL 형식을 검증합니다."""
        return validate_upload_image_url(v)

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str | None) -> str | None:
        """제목 형식을 검증합니다.

        Args:
            v: 입력된 제목.

        Returns:
            공백이 제거된 검증된 제목 또는 None.

        Raises:
            ValueError: 제목이 3자 미만인 경우.
        """
        if v is None:
            return None
        v = v.strip()
        if len(v) < 3:
            raise ValueError("제목은 최소 3자 이상이어야 합니다.")
        return v

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str | None) -> str | None:
        """내용 형식을 검증합니다.

        Args:
            v: 입력된 내용.

        Returns:
            공백이 제거된 검증된 내용 또는 None.

        Raises:
            ValueError: 내용이 1자 미만인 경우.
        """
        if v is None:
            return None
        v = v.strip()
        if len(v) < 1:
            raise ValueError("내용은 최소 1자 이상이어야 합니다.")
        return v
