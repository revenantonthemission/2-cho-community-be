"""password: 비밀번호 해싱 및 검증 유틸리티 모듈.

bcrypt를 사용하여 비밀번호를 안전하게 해싱하고 검증합니다.
"""

import bcrypt


def hash_password(password: str) -> str:
    """비밀번호를 해싱합니다.

    bcrypt 알고리즘을 사용하여 비밀번호를 안전하게 해싱합니다.

    Args:
        password: 평문 비밀번호.

    Returns:
        해싱된 비밀번호 문자열.
    """
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """비밀번호를 검증합니다.

    평문 비밀번호가 해싱된 비밀번호와 일치하는지 확인합니다.

    Args:
        plain_password: 평문 비밀번호.
        hashed_password: 해싱된 비밀번호.

    Returns:
        비밀번호 일치 여부.
    """
    try:
        password_bytes = plain_password.encode("utf-8")
        hashed_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception:
        return False
