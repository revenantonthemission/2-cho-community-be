from fastapi import APIRouter, status
from controllers import user_controller

user_router = APIRouter(prefix="/v1/users")


# 모든 유저의 목록을 획득
@user_router.get("/all")
def get_users():
    return user_controller.get_users()


# 사용자 ID로 유저 정보 얻기
@user_router.get("/{user_id}")
def get_user(user_id: int):
    return user_controller.get_user(user_id)


# 사용자 생성
@user_router.post("", status_code=status.HTTP_201_CREATED)
def create_user(data: dict):
    return user_controller.create_user(data)
