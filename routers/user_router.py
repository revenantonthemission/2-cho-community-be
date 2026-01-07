from fastapi import APIRouter
from controllers import user_controller

router = APIRouter(prefix="/users")

# 모든 유저의 목록을 획득
@router.get("")
def get_users():
    return user_controller.get_users()

# 사용자 ID로 유저 정보 얻기
@router.get("/{user_id}")
def get_user(user_id: int):
    return user_controller.get_user(user_id)

# 사용자 생성
@router.post("", status_code=201)
def create_user(data: dict):
    return user_controller.create_user(data)

# 로그인
@router.post("/login")
def login(data: dict):
    return user_controller.login(data)