"""comment_schemas: 댓글 관련 Pydantic 모델 모듈.

댓글 생성, 수정 요청 스키마를 정의합니다.
"""

from pydantic import BaseModel, Field, field_validator


def _validate_comment_content(v: str) -> str:
    """댓글 내용을 검증하고 정규화합니다.

    Args:
        v: 입력된 내용.

    Returns:
        공백이 제거된 검증된 내용.

    Raises:
        ValueError: 내용이 1자 미만인 경우.
    """
    v = v.strip()
    if len(v) < 1:
        raise ValueError("댓글 내용은 최소 1자 이상이어야 합니다.")
    return v


class CreateCommentRequest(BaseModel):
    """댓글 생성 요청 모델.

    Attributes:
        content: 댓글 내용 (1~1000자).
        parent_id: 답글 대상 댓글 ID (1단계만 허용, 선택).
    """

    content: str = Field(..., min_length=1, max_length=1000)
    parent_id: int | None = Field(None, description="답글 대상 댓글 ID (1단계만 허용)")

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        return _validate_comment_content(v)


class UpdateCommentRequest(BaseModel):
    """댓글 수정 요청 모델.

    Attributes:
        content: 새 댓글 내용 (1~1000자).
    """

    content: str = Field(..., min_length=1, max_length=1000)

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        return _validate_comment_content(v)
