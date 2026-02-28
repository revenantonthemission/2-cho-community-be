"""temp_password: 임시 비밀번호 생성 유틸리티.

기존 비밀번호 정책(대문자+소문자+숫자+특수문자, 8-20자)을 충족하는
암호학적으로 안전한 임시 비밀번호를 생성합니다.
"""

import secrets
import string

# 기존 비밀번호 정책과 동일한 특수문자 집합 (schemas/user_schemas.py _PASSWORD_PATTERN 참조)
_SPECIAL_CHARS = "@$!%*?&"
_LOWER = string.ascii_lowercase
_UPPER = string.ascii_uppercase
_DIGITS = string.digits
_ALL_CHARS = _LOWER + _UPPER + _DIGITS + _SPECIAL_CHARS


def generate_temp_password() -> str:
    """정책을 충족하는 임시 비밀번호를 생성합니다.

    생성 규칙: 대문자 1개 이상, 소문자 1개 이상, 숫자 1개 이상,
    특수문자(@$!%*?&) 1개 이상, 총 12자.
    secrets 모듈로 암호학적으로 안전한 난수 사용.

    Returns:
        임시 비밀번호 문자열 (12자).
    """
    # 각 필수 문자 클래스에서 최소 1개씩 보장
    guaranteed = [
        secrets.choice(_UPPER),
        secrets.choice(_LOWER),
        secrets.choice(_DIGITS),
        secrets.choice(_SPECIAL_CHARS),
    ]
    # 나머지 8자리는 전체 풀에서 선택
    remaining = [secrets.choice(_ALL_CHARS) for _ in range(8)]

    combined = guaranteed + remaining
    # secrets.SystemRandom으로 셔플 (암호학적으로 안전)
    secrets.SystemRandom().shuffle(combined)
    return "".join(combined)
