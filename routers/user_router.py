from fastapi import APIRouter, Request, status
from controllers import user_controller


# 라우터 생성
user_router = APIRouter(prefix="/v1/users", tags=["users"])


# 사용자 생성
@user_router.post("/", status_code=status.HTTP_201_CREATED)
async def create_user(request: Request):
    return await user_controller.create_user(request)


# 내 정보 얻기
@user_router.get("/me", status_code=status.HTTP_200_OK)
async def get_my_info(request: Request):
    return await user_controller.get_my_info(request)


# 사용자 닉네임으로 유저 정보 얻기
@user_router.get("/{nickname}", status_code=status.HTTP_200_OK)
async def get_user(request: Request):
    # 본인이라면 get_my_info로 처리
    if request.path_params.get("nickname") == request.session.get("nickname"):
        return await user_controller.get_my_info(request)
    return await user_controller.get_user(request)


# 내 정보 수정하기
@user_router.patch("/me", status_code=status.HTTP_200_OK)
async def update_user(request: Request):
    return await user_controller.update_user(request)


# 비밀번호 변경하기
@user_router.put("/me/password", status_code=status.HTTP_200_OK)
async def change_password(request: Request):
    return await user_controller.change_password(request)


# 회원 탈퇴하기
@user_router.delete("/me", status_code=status.HTTP_200_OK)
async def withdraw_user(request: Request):
    return await user_controller.withdraw_user(request)
