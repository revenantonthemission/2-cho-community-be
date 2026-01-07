_users = [
    {"id": 1, "name": "Alice", "email": "alice@test.com"},
    {"id": 2, "name": "Bob", "email": "bob@test.com"},
]

def get_users():
    return _users.copy()

def get_user_by_id(user_id: int):
    return next((u for u in _users if u["id"] == user_id), None)

def get_user_by_email(email: str):
    return next((u for u in _users if u["email"] == email), None)

def add_user(user: dict):
    _users.append(user)
    return user