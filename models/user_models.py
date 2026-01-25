"""user_models: 사용자 관련 데이터 모델 및 함수 모듈.

사용자 데이터 클래스와 인메모리 저장소를 관리하는 함수들을 제공합니다.
"""

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class User:
    """사용자 데이터 클래스.

    Attributes:
        id: 사용자 고유 식별자.
        name: 사용자 이름.
        email: 이메일 주소.
        password: 비밀번호.
        nickname: 닉네임.
        profileImageUrl: 프로필 이미지 URL.
        is_active: 활성화 상태.
        deleted_at: 탈퇴 시간.
    """

    id: int
    name: str
    email: str
    password: str
    nickname: str
    profileImageUrl: str = "/assets/default_profile.png"
    is_active: bool = True
    deleted_at: datetime | None = None


@dataclass
class Post:
    """게시글 데이터 클래스 (레거시, 미사용).

    Attributes:
        id: 게시글 고유 식별자.
        author_id: 작성자 ID.
        title: 제목.
        content: 내용.
    """

    id: int
    author_id: int | None
    title: str
    content: str


_users: list[User] = [
    User(
        id=1,
        name="Alice",
        email="alice@test.com",
        password="PasswordAlice1!",
        nickname="alice",
    ),
    User(
        id=2,
        name="Bob",
        email="bob@test.com",
        password="PasswordBob2@",
        nickname="bob",
    ),
    User(
        id=3,
        name="Chris",
        email="chris@test.com",
        password="PasswordChris3#",
        nickname="chris",
    ),
]

_posts: list[Post] = [
    Post(
        id=129,
        author_id=3,
        title="우끼끼",
        content="나는 원숭이다",
    ),
    Post(
        id=111,
        author_id=2,
        title="뉴비입니다",
        content="회원가입은 어떻게 구현하나요?",
    ),
    Post(
        id=111,
        author_id=2,
        title="뉴비입니다",
        content="잘 부탁드립니다!",
    ),
]


def get_users() -> list[User]:
    """모든 사용자 목록을 반환합니다.

    Returns:
        사용자 목록의 복사본.
    """
    return _users.copy()


def get_user_by_id(user_id: int) -> User | None:
    """ID로 사용자를 조회합니다.

    Args:
        user_id: 조회할 사용자의 ID.

    Returns:
        사용자 객체, 없으면 None.
    """
    return next((u for u in _users if u.id == user_id), None)


def get_user_by_email(email: str) -> User | None:
    """이메일로 사용자를 조회합니다.

    Args:
        email: 조회할 이메일 주소.

    Returns:
        사용자 객체, 없으면 None.
    """
    return next((u for u in _users if u.email == email), None)


def get_user_by_nickname(nickname: str) -> User | None:
    """닉네임으로 사용자를 조회합니다.

    Args:
        nickname: 조회할 닉네임.

    Returns:
        사용자 객체, 없으면 None.
    """
    return next((u for u in _users if u.nickname == nickname), None)


def add_user(user: User) -> User:
    """새 사용자를 추가합니다.

    Args:
        user: 추가할 사용자 객체.

    Returns:
        추가된 사용자 객체.
    """
    _users.append(user)
    return user


def update_user(user_id: int, **kwargs: Any) -> User | None:
    """사용자 정보를 업데이트합니다.

    기존 사용자 정보를 바탕으로 새로운 사용자 객체를 생성하여 불변성을 유지합니다.

    Args:
        user_id: 업데이트할 사용자의 ID.
        **kwargs: 업데이트할 필드와 값.

    Returns:
        업데이트된 사용자 객체, 사용자가 없으면 None.
    """
    for i, user in enumerate(_users):
        if user.id == user_id:
            updated_user = replace(user, **kwargs)
            _users[i] = updated_user
            return updated_user
    return None


def update_password(user_id: int, new_password: str) -> User | None:
    """사용자 비밀번호를 업데이트합니다.

    Args:
        user_id: 업데이트할 사용자의 ID.
        new_password: 새 비밀번호.

    Returns:
        업데이트된 사용자 객체, 사용자가 없으면 None.
    """
    for i, user in enumerate(_users):
        if user.id == user_id:
            updated_user = replace(user, password=new_password)
            _users[i] = updated_user
            return updated_user
    return None


def withdraw_user(user: User) -> User:
    """회원 탈퇴를 처리합니다.

    사용자를 비활성화 상태로 변경하고 탈퇴 시간을 기록합니다.

    Args:
        user: 탈퇴할 사용자 객체.

    Returns:
        비활성화된 사용자 객체.
    """
    return replace(user, is_active=False, deleted_at=datetime.now())
