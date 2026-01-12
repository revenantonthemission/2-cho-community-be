from fastapi import FastAPI, Request, Response, HTTPException, status
from datetime import datetime
from models import user_models


def get_my_info(data: dict):
    print(f"auth_me: {datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')}")
    return None


def login(data: dict):
    email = data.get("email")
    password = data.get("password")

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="missing_email"
        )
    if not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="missing_password"
        )

    user = user_models.get_user_by_email(email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized"
        )

    print(f"login: {datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')}")

    return {
        "data": {
            "user_id": user["id"],
            "name": user["name"],
        },
    }


def logout(data: dict):
    print(f"logout: {datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')}")
    return None
