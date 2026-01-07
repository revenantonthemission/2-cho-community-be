from fastapi import APIRouter
from controllers import user_controller

router = APIRouter(prefix="/users")

@router.get("")
def get_users():
    return user_controller.get_users()

@router.get("/{user_id}")
def get_user(user_id: int):
    return user_controller.get_user(user_id)

@router.post("/login")
def login(data: dict):
    return user_controller.login(data)