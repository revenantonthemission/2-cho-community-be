from fastapi import HTTPException
from models import user_model

def get_users():
    users = user_model.get_users()
    if not users:
        raise HTTPException(status_code=404, detail="no_users_found")
    return {"data": users}

def get_user(user_id: int):
    if user_id <= 0:
        raise HTTPException(status_code=400, detail="invalid_user_id")

    user = user_model.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")
    return {"data": user}


def create_user(data: dict):
    name = data.get("name")
    email = data.get("email")

    if not name or not email:
        raise HTTPException(status_code=400, detail="missing_required_fields")
    if user_model.get_user_by_email(email):
        raise HTTPException(status_code=409, detail="email_already_exists")

    new_user = {"id": len(user_model.get_users()) + 1, "name": name, "email": email}
    user_model.add_user(new_user)

    return {"data": new_user}


def login(data: dict):
    email = data.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="missing_email")

    user = user_model.get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=401, detail="unauthorized")

    return {"data": {"user_id": user["id"], "name": user["name"]}}