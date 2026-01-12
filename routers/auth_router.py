from fastapi import APIRouter, status, Response
from controllers import auth_controller


auth_router = APIRouter(prefix="/v1/auth")


@auth_router.get("/me")
def get_my_info(data: dict):
    return auth_controller.get_my_info(data)


@auth_router.post("/session")
def login(data: dict):
    return auth_controller.login(data)


@auth_router.delete("/session")
def logout(data: dict):
    return auth_controller.logout(data)
