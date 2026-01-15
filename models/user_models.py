from dataclasses import dataclass, replace
from datetime import datetime
from typing import List


@dataclass(frozen=True)
class User:
    id: int
    name: str
    email: str
    password: str
    nickname: str
    profileImageUrl: str = "/assets/default_profile.png"
    is_active: bool = True
    deleted_at: datetime | None = None


# 아직 게시물 기능 구현 안됨! 현재는 그냥 더미 데이터입니다.
@dataclass
class Post:
    id: int
    author_id: int | None
    title: str
    content: str


_users: List[User] = [
    User(
        id=1,
        name="Alice",
        email="alice@test.com",
        password="PasswordAlice1",
        nickname="alice",
    ),
    User(
        id=2,
        name="Bob",
        email="bob@test.com",
        password="PasswordBob2",
        nickname="bob",
    ),
    User(
        id=3,
        name="Chris",
        email="chris@test.com",
        password="PasswordChris3",
        nickname="chris",
    ),
]

_posts: List[Post] = [
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


# 모든 유저의 목록
def get_users():
    return _users.copy()


# ID로 유저 조회
def get_user_by_id(user_id: int) -> User | None:
    return next((u for u in _users if u.id == user_id), None)


# 이메일로 유저 조회
def get_user_by_email(email: str) -> User | None:
    return next((u for u in _users if u.email == email), None)


# 닉네임으로 유저 조회
def get_user_by_nickname(nickname: str) -> User | None:
    return next((u for u in _users if u.nickname == nickname), None)


# 사용자 추가하기
def add_user(user: User) -> User:
    _users.append(user)
    return user


# 사용자 정보 업데이트 (기존 정보 삭제 후 새로운 사용자로 추가)
def update_user(user_id: int, **kwargs) -> User | None:
    for i, user in enumerate(_users):
        if user.id == user_id:
            # 기존 유저 정보를 바탕으로 새로운 유저 객체 생성 (불변성 유지)
            updated_user = replace(user, **kwargs)
            _users[i] = updated_user
            return updated_user
    return None


# 비밀번호 업데이트
def update_password(user_id: int, new_password: str) -> User | None:
    for i, user in enumerate(_users):
        if user.id == user_id:
            updated_user = replace(user, password=new_password)
            _users[i] = updated_user
            return updated_user
    return None


# 회원 탈퇴 기능: 유저를 비활성화 상태로 바꾸고 그 시간을 기록한다.
def withdraw_user(user: User) -> User:
    return replace(user, is_active=False, deleted_at=datetime.now())
