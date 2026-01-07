from fastapi import HTTPException

_users = [
    {"id": 1, "name": "Alice", "email": "alice@test.com"},
    {"id": 2, "name": "Bob", "email": "bob@test.com"},
    {"id": 3, "name": "Chris", "email": "chris@test.com"}
]


def get_users():
    users = _users.copy()
    if not users:
        raise HTTPException(status_code=404, detail="no_users_found")
    
    return {"data": users}

def get_user(user_id: int):
    if user_id <= 0:
        raise HTTPException(status_code=400, detail="invalid_user_id")

    user = next((u for u in _users if u["id"] == user_id), None)
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")
    
    return {"data": user}


def create_user(data: dict):
    name = data.get("name")
    email = data.get("email")

    if not name or not email:
        raise HTTPException(status_code=400, detail="missing_required_fields")
    if any(u["email"] == email for u in _users):
        raise HTTPException(status_code=409, detail="email_already_exists")

    new_user = {"id": len(_users) + 1, "name": name, "email": email}
    _users.append(new_user)

    return {"data": new_user}


def login(data: dict):
    email = data.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="missing_email")

    user = next((u for u in _users if u["email"] == email), None)
    if not user:
        raise HTTPException(status_code=401, detail="unauthorized")

    return {"data": {"user_id": user["id"], "name": user["name"]}}