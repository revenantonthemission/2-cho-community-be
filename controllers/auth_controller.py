import uuid
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from datetime import datetime
from models import user_models


# 내 정보 얻기 (/v1/auth/me)
async def get_my_info(request: Request):
    try:
        session_id = request.session.get("session_id")
        if not session_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error": "unauthorized",
                    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )

        email = request.session.get("email")
        user = user_models.get_user_by_email(email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "unauthorized",
                    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )

        content = {
            "code": "AUTH_SUCCESS",
            "message": "현재 로그인 중인 상태입니다.",
            "data": {
                "user": {
                    "user_id": user.id,
                    "email": user.email,
                    "nickname": user.nickname,
                    "profileImageUrl": user.profileImageUrl,
                },
            },
            "errors": [],
            "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        return JSONResponse(
            content=content,
            status_code=status.HTTP_200_OK,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "trackingID": str(uuid.uuid4()),
                "error": str(e),
                "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )


# 로그인하기 (/v1/auth/session)
async def login(request: Request):
    try:
        body = await request.json()
        email = body.get("email")
        password = body.get("password")

        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "missing_email",
                    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )
        if not password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "missing_password",
                    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )

        user = user_models.get_user_by_email(email)

        if not user or not user.password == password:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error": "unauthorized",
                    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )

        if request.method != "POST":
            raise HTTPException(
                status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
                detail={
                    "error": "method_not_allowed",
                    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )

        session_id = request.session.get("session_id")
        if not session_id:
            session_id = str(uuid.uuid4())
            request.session["session_id"] = session_id
            request.session["email"] = email
            request.session["nickname"] = user.nickname

        content = {
            "code": "LOGIN_SUCCESS",
            "message": "로그인에 성공했습니다.",
            "data": {
                "user": {
                    "user_id": user.id,
                    "email": user.email,
                    "nickname": user.nickname,
                    "profileImageUrl": user.profileImageUrl,
                },
            },
            "errors": [],
            "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

        return JSONResponse(
            content=content,
            status_code=status.HTTP_200_OK,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "trackingID": str(uuid.uuid4()),
                "error": str(e),
                "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )


# 로그아웃하기 (/v1/auth/session)
async def logout(request: Request):
    content = {
        "code": "LOGOUT_SUCCESS",
        "message": "로그아웃에 성공했습니다.",
        "data": {},
        "errors": [],
        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    try:
        session_id = request.session.get("session_id")
        if not session_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error": "unauthorized",
                    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )
        if request.method != "DELETE":
            raise HTTPException(
                status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
                detail={
                    "error": "method_not_allowed",
                    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )
        request.session.clear()
        return JSONResponse(
            content=content,
            status_code=status.HTTP_200_OK,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "trackingID": str(uuid.uuid4()),
                "error": str(e),
                "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )
