from fastapi import APIRouter, Request, status
from controllers import auth_controller
from main import app

auth_router = APIRouter(prefix="/v1/auth")
app.include_router(auth_router, tags=["auth"])


@auth_router.get("/me")
async def get_my_info(request: Request):
    return await auth_controller.get_my_info(request)


@auth_router.post("/session")
async def login(request: Request):
    return await auth_controller.login(request)


@auth_router.delete("/session", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request):
    return await auth_controller.logout(request)
