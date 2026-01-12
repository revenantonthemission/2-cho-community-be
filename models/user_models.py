_users = [
    {
        "id": 1,
        "name": "Alice",
        "email": "alice@test.com",
        "password": "password",
        "nickname": "pietro",
        "profileImageUrl": "https://example.com/profile.jpg",
    },
    {
        "id": 2,
        "name": "Bob",
        "email": "bob@test.com",
        "password": "password",
        "nickname": "bob",
        "profileImageUrl": "https://example.com/profile.jpg",
    },
    {
        "id": 3,
        "name": "Chris",
        "email": "chris@test.com",
        "password": "password",
        "nickname": "chris",
        "profileImageUrl": "https://example.com/profile.jpg",
    },
]


def get_users():
    return _users.copy()


def get_user_by_id(user_id: int):
    return next((u for u in _users if u["id"] == user_id), None)


def get_user_by_email(email: str):
    return next((u for u in _users if u["email"] == email), None)


def get_user_by_nickname(nickname: str):
    return next((u for u in _users if u["nickname"] == nickname), None)


def add_user(user: dict):
    _users.append(user)
    return user
