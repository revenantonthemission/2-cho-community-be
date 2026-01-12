from fastapi import HTTPException, status
from datetime import datetime
from models import user_models
import re


def get_users():
    users = user_models.get_users()
    if not users:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="no_users_found"
        )
    return {"data": users}


def get_user(user_id: int):
    if user_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_user_id"
        )
    user = user_models.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="user_not_found"
        )
    return {"data": user}


def create_user(data: dict):
    name = data.get("name")
    email = data.get("email")
    password = data.get("password")
    nickname = data.get("nickname")
    profileImageUrl = data.get("profileImageUrl")

    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
    print("포맷 지정: ", timestamp)

    # 데이터 누락
    if not name or not email or not password or not nickname or not profileImageUrl:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="missing_required_fields"
        )
    if (
        not isinstance(name, str)
        or not isinstance(email, str)
        or not isinstance(password, str)
        or not isinstance(nickname, str)
        or not isinstance(profileImageUrl, str)
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_field_types"
        )

    if user_models.get_user_by_email(email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="email_already_exists"
        )
    if user_models.get_user_by_nickname(nickname):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="nickname_already_exists"
        )

    # 이미지 파일 형식 검사 (.jpg/.png)
    if not profileImageUrl.endswith(".jpg") and not profileImageUrl.endswith(".png"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="invalid_image_format",
        )

    # 이메일 형식 검사 (정규표현식)
    if not re.match(r"^[^@]+@[^@]+\.[^@]+", email):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="invalid_email_format",
        )

    # 비밀번호 형식 검사 (정규표현식)
    if not re.match(
        r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,20}$",
        password,
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid_password"
        )

    # 닉네임 형식 검사 (정규표현식)
    if not re.match(r"^[a-zA-Z0-9_]{3,20}$", nickname):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="invalid_nickname_format",
        )

    new_user = {
        "id": len(user_models.get_users()) + 1,
        "name": name,
        "email": email,
        "nickname": nickname,
        "profileImageUrl": profileImageUrl,
    }
    user_models.add_user(new_user)

    return {"data": new_user}


# issue: middleware
# issue: orm
# issue: sign up function
