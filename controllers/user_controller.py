from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from datetime import datetime
from models import user_models
import re
import uuid


# 유저 조회하기 (/v1/users/{nickname})
async def get_user(request: Request):
    try:
        nickname = request.path_params.get("nickname")
        if not nickname:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "invalid_nickname",
                    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )
        user = user_models.get_user_by_nickname(nickname)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "user_not_found",
                    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )

        content = {
            "code": "AUTH_SUCCESS",
            "message": "사용자 조회에 성공했습니다.",
            "data": {
                "user": {
                    "user_id": user.id,
                    "email": user.email,
                    "name": user.name,
                    "nickname": user.nickname,
                    "profileImageUrl": user.profileImageUrl,
                }
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


# 유저 생성하기 (/v1/users)
async def create_user(request: Request):
    try:
        body = await request.json()
        name = body.get("name")
        email = body.get("email")
        password = body.get("password")
        nickname = body.get("nickname")
        profileImageUrl = body.get("profileImageUrl")
        if not profileImageUrl:
            profileImageUrl = "/assets/default_profile.png"

        # 데이터 누락
        if not name or not email or not password or not nickname or not profileImageUrl:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "missing_required_fields",
                    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )

        if (
            not isinstance(name, str)
            or not isinstance(email, str)
            or not isinstance(password, str)
            or not isinstance(nickname, str)
            or not isinstance(profileImageUrl, str)
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "invalid_field_types",
                    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )

        # 이미지 파일 검사 - 1. 확장자 검사 (단순 문자열 형식 검증)
        allowed_extensions: set[str] = {".jpg", ".jpeg", ".png"}
        if not any(profileImageUrl.endswith(ext) for ext in allowed_extensions):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "invalid_image_format",
                    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )

        # 요청 메소드는 반드시 POST여야 함.
        if request.method != "POST":
            raise HTTPException(
                status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
                detail={
                    "error": "method_not_allowed",
                    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )

        if user_models.get_user_by_email(email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "email_already_exists",
                    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )
        if user_models.get_user_by_nickname(nickname):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "nickname_already_exists",
                    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )

        # 이미지 파일 검사 - 2. MIME 타입 검증: (보류 - URL/스트링 기반으로는 서버측 검증이 복잡함)
        # 현재는 단순 확장자 검사만 수행합니다.

        # 이메일 형식 검사 (정규표현식)
        if not re.match(r"^[^@]+@[^@]+\.[^@]+", email):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={
                    "error": "invalid_email_format",
                    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )

        # 비밀번호 형식 검사 (정규표현식)
        # 반드시 대문자, 소문자, 특수문자가 각각 한 개 이상 들어가야 함.
        if not re.match(
            r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,20}$",
            password,
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={
                    "error": "invalid_password_format",
                    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )

        # 닉네임 형식 검사 (정규표현식)
        if not re.match(r"^[a-zA-Z0-9_]{3,20}$", nickname):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={
                    "error": "invalid_nickname_format",
                    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )

        content = {
            "code": "SIGNUP_SUCCESS",
            "message": "사용자 생성에 성공했습니다.",
            "data": {},
            "errors": [],
            "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

        new_user = user_models.User(
            id=len(user_models.get_users()) + 1,
            name=name,
            email=email,
            password=password,
            nickname=nickname,
            profileImageUrl=profileImageUrl,
        )
        user_models.add_user(new_user)

        return JSONResponse(
            content=content,
            status_code=status.HTTP_201_CREATED,
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


# 내 정보 조회하기 (/v1/users/me)
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
                    "error": "Access Denied",
                    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )

        if request.method != "GET":
            raise HTTPException(
                status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
                detail={
                    "error": "Method Not Allowed",
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


# 유저 정보 조회하기 (/v1/users/{nickname})
async def get_user_info(request: Request):
    try:
        # 로그인한 상태인지 확인
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
                    "error": "access_denied",
                    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )

        nickname = request.path_params.get("nickname")
        user = user_models.get_user_by_nickname(nickname)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "user_not_found",
                    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )

        content = {
            "code": "QUERY_SUCCESS",
            "message": "유저 조회에 성공했습니다.",
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


# 내 정보 수정하기 (/v1/users/me)
async def update_user(request: Request):
    try:
        body = await request.json()
        session_id = request.session.get("session_id")
        if not session_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error": "unauthorized",
                    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )

        # 세션에서 현재 로그인한 사용자 정보 가져오기
        current_email = request.session.get("email")
        current_user = user_models.get_user_by_email(current_email)

        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "user_not_found",
                    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )

        if request.method != "PATCH":
            raise HTTPException(
                status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
                detail={
                    "error": "method_not_allowed",
                    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )

        # 변경할 데이터 확인: 닉네임, 이메일
        updates = {}
        if "nickname" in body:
            updates["nickname"] = body["nickname"]
        if "email" in body:
            updates["email"] = body["email"]

        # 변경사항이 없는 경우
        if not updates:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "no_changes_provided",
                    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )

        # 1. 닉네임 형식 검사 (정규표현식)
        if not re.match(r"^[a-zA-Z0-9_]{3,20}$", updates["nickname"]):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={
                    "error": "invalid_nickname_format",
                    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )

        # 2. 닉네임 중복 검사 (본인 닉네임인 경우 제외)
        existing_user = user_models.get_user_by_nickname(updates["nickname"])
        if existing_user and existing_user.id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "nickname_already_exists",
                    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )

        # 3. 이메일 형식 검사 (정규표현식)
        if not re.match(
            r"^[a-zA-Z0-9_]+@[a-zA-Z0-9_]+\.[a-zA-Z0-9_]+$", updates["email"]
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={
                    "error": "invalid_email_format",
                    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )

        # 4. 이메일 중복 검사 (본인 이메일인 경우 제외)
        existing_user = user_models.get_user_by_email(updates["email"])
        if existing_user and existing_user.id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "email_already_exists",
                    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )

        # 모델 업데이트 호출
        updated_user = user_models.update_user(current_user.id, **updates)

        # 세션 정보도 업데이트
        if "nickname" in updates:
            request.session["nickname"] = updates["nickname"]
        if "email" in updates:
            request.session["email"] = updates["email"]

        content = {
            "code": "UPDATE_SUCCESS",
            "message": "유저 정보 수정에 성공했습니다.",
            "data": {
                "user": {
                    "user_id": updated_user.id,
                    "email": updated_user.email,
                    "nickname": updated_user.nickname,
                    "profileImageUrl": updated_user.profileImageUrl,
                }
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


# 내 비밀번호 수정하기 (/v1/users/me/password)
async def change_password(request: Request):
    try:
        body = await request.json()
        current_password = body.get("current_password")
        new_password = body.get("new_password")
        new_password_confirm = body.get("new_password_confirm")

        # 현재 세션 확인
        session_id = request.session.get("session_id")
        if not session_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error": "unauthorized",
                    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )

        # 세션에 있는 이메일을 통해 현재 로그인한 사용자의 정보를 가져온다.
        current_user = user_models.get_user_by_email(request.session.get("email"))
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "user_not_found",
                    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )

        # 필수 필드 확인하기
        if not current_password or not new_password or not new_password_confirm:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "bad_request",
                    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )

        # 현재 비밀번호 검증하기
        if current_user.password != current_password:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error": "invalid_current_password",
                    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )

        # 새 비밀번호와 새 비밀번호 확인이 일치하는지 확인하기
        if new_password != new_password_confirm:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "password_mismatch",
                    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )

        # 새 비밀번호가 기존 비밀번호와 같은지 확인
        if new_password == current_user.password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "same_password",
                    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )

        # 새 비밀번호가 정책에 부합하는지 확인하기 - 회원가입 시 사용했던 기존 로직과 동일함.
        if not re.match(
            r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,20}$",
            new_password,
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "invalid_password",
                    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )

        # 비밀번호 업데이트
        user_models.update_password(current_user.id, new_password)
        content = {
            "code": "PASSWORD_CHANGE_SUCCESS",
            "message": "비밀번호 변경에 성공했습니다.",
            "data": {},
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


# 회원 탈퇴하기 (/v1/users/me)
async def withdraw_user(request: Request):
    try:
        # 현재 세션 확인
        session_id = request.session.get("session_id")
        if not session_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error": "unauthorized",
                    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )

        # 세션에 있는 이메일을 통해 현재 로그인한 사용자의 정보를 가져온다.
        current_user = user_models.get_user_by_email(request.session.get("email"))
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "user_not_found",
                    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )
        if not current_user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "inactive_user",
                    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )

        body = await request.json()
        password_input = body.get("password")
        agree = body.get("agree")
        if password_input is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "password_input_required",
                    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )
        if agree is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "agreement_required",
                    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )

        if password_input != current_user.password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "invalid_password",
                    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )

        if not agree:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "agreement_required",
                    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )

        content = {
            "code": "WITHDRAWAL_ACCEPTED",
            "message": "탈퇴 신청이 접수되었습니다.",
            "data": {},
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
