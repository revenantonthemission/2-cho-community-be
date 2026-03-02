"""common: 공통 응답 유틸리티 모듈.

API 응답 생성 및 공통 데이터 변환 함수를 정의합니다.
"""

from datetime import datetime
from typing import Any


def create_response(
    code: str,
    message: str,
    data: dict[str, Any] | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """표준 API 응답 딕셔너리를 생성합니다.

    Args:
        code: 응답 코드 (예: "SUCCESS", "POST_CREATED").
        message: 사용자에게 표시할 메시지.
        data: 응답 데이터 (기본값: 빈 딕셔너리).
        timestamp: 타임스탬프 (기본값: 현재 시간).

    Returns:
        표준 형식의 응답 딕셔너리.
    """
    return {
        "code": code,
        "message": message,
        "data": data if data is not None else {},
        "errors": [],
        "timestamp": timestamp or datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


DEFAULT_PROFILE_IMAGE = "/assets/profiles/default_profile.jpg"


def build_author_dict(user_id, nickname, profile_img) -> dict[str, Any]:
    """작성자 정보 딕셔너리를 생성합니다.

    탈퇴한 사용자인 경우 기본값으로 대체합니다.

    Args:
        user_id: 사용자 ID (탈퇴 시 None).
        nickname: 닉네임 (탈퇴 시 None).
        profile_img: 프로필 이미지 URL (없으면 기본 이미지).

    Returns:
        작성자 정보 딕셔너리.
    """
    return {
        "user_id": user_id,
        "nickname": nickname if nickname else "탈퇴한 사용자",
        "profileImageUrl": profile_img or DEFAULT_PROFILE_IMAGE,
    }


def serialize_user(user) -> dict[str, Any]:
    """User 객체를 API 응답용 딕셔너리로 변환합니다.

    Args:
        user: User 데이터 객체 (id, email, nickname, profileImageUrl 속성 필요).

    Returns:
        사용자 정보 딕셔너리.
    """
    return {
        "user_id": user.id,
        "email": user.email,
        "email_verified": user.email_verified,
        "nickname": user.nickname,
        "profileImageUrl": user.profileImageUrl,
    }
