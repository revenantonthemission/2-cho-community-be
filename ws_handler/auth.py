"""auth: WebSocket Lambda용 JWT 검증 (경량).

FastAPI/Pydantic 의존성 없이 JWT Access Token을 검증합니다.
SECRET_KEY는 SSM Parameter Store에서 콜드 스타트 시 1회 조회합니다.

주의: 계정 정지(suspended_until) 검증은 수행하지 않습니다.
WebSocket Lambda는 DynamoDB만 사용하며 MySQL 접근이 없으므로,
정지된 사용자가 Access Token 만료(최대 30분)까지 알림을 수신할 수 있습니다.
알림 수신은 읽기 전용이므로 허용 가능한 수준의 제한사항입니다.
"""

import logging
import os

import jwt

logger = logging.getLogger(__name__)

_secret_key: str | None = None

_JWT_ALGORITHM = "HS256"


def _get_secret_key() -> str:
    """SECRET_KEY를 반환합니다 (SSM 또는 환경변수에서 조회, 1회 캐싱)."""
    global _secret_key
    if _secret_key is not None:
        return _secret_key

    ssm_name = os.environ.get("SECRET_KEY_SSM_NAME")
    if ssm_name:
        import boto3

        ssm = boto3.client("ssm")
        try:
            response = ssm.get_parameter(Name=ssm_name, WithDecryption=True)
            _secret_key = response["Parameter"]["Value"]
        except Exception:
            logger.exception("SSM SECRET_KEY 조회 실패")
            raise
    else:
        # 로컬 테스트/개발용 폴백
        _secret_key = os.environ.get("SECRET_KEY", "")
        if not _secret_key:
            raise ValueError("SECRET_KEY가 설정되지 않았습니다")

    return _secret_key


def verify_token(token: str) -> int | None:
    """Access Token을 검증하고 user_id를 반환합니다.

    Returns:
        user_id (int) 검증 성공 시, None 실패 시.
    """
    try:
        payload = jwt.decode(token, _get_secret_key(), algorithms=[_JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        logger.debug("토큰 만료")
        return None
    except jwt.PyJWTError:
        logger.debug("토큰 검증 실패")
        return None

    if payload.get("type") != "access":
        logger.debug("토큰 타입 불일치: %s", payload.get("type"))
        return None

    sub = payload.get("sub")
    if not sub:
        return None

    try:
        return int(sub)
    except (ValueError, TypeError):
        return None
