import logging
import os

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


def _resolve_ssm_secrets() -> None:
    """Lambda 환경에서 SSM Parameter Store의 SecureString 값을 환경 변수로 설정합니다.

    SSM 파라미터 이름은 Lambda 환경변수 DB_PASSWORD_SSM_NAME, SECRET_KEY_SSM_NAME에 지정.
    pydantic-settings가 환경변수에서 값을 읽기 전에 호출해야 합니다.
    """
    if os.getenv("AWS_LAMBDA_EXEC") != "true":
        return

    ssm_mappings = {
        "DB_PASSWORD": os.getenv("DB_PASSWORD_SSM_NAME"),
        "SECRET_KEY": os.getenv("SECRET_KEY_SSM_NAME"),
        "INTERNAL_API_KEY": os.getenv("INTERNAL_API_KEY_SSM_NAME"),
    }

    params_to_fetch = {k: v for k, v in ssm_mappings.items() if v}
    if not params_to_fetch:
        return

    import boto3  # Lambda 런타임에 기본 포함

    ssm = boto3.client("ssm")

    # 배치 API로 한 번에 조회 (콜드스타트 지연 최소화)
    try:
        response = ssm.get_parameters(
            Names=list(params_to_fetch.values()),
            WithDecryption=True,
        )
    except Exception:
        logger.exception("SSM 배치 파라미터 조회 실패")
        raise

    if response.get("InvalidParameters"):
        raise RuntimeError(
            f"SSM 파라미터 조회 실패: {response['InvalidParameters']}"
        )

    # 모든 파라미터 조회 성공 후 환경변수 일괄 설정 (원자성 보장)
    name_to_env = {v: k for k, v in params_to_fetch.items()}
    resolved = {}
    for param in response["Parameters"]:
        env_var = name_to_env[param["Name"]]
        resolved[env_var] = param["Value"]

    for env_var, value in resolved.items():
        os.environ[env_var] = value


# Settings 인스턴스 생성 전에 SSM에서 시크릿을 환경변수로 설정
_resolve_ssm_secrets()


class Settings(BaseSettings):
    """애플리케이션 설정을 관리하는 클래스.

    환경 변수에서 설정을 로드하며, 기본값을 제공합니다.

    Attributes:
        SECRET_KEY: JWT 토큰 서명 키.
        ALLOWED_ORIGINS: CORS 허용 오리진 목록.
        DB_HOST: MySQL 호스트 주소.
        DB_PORT: MySQL 포트 번호.
        DB_USER: MySQL 사용자명.
        DB_PASSWORD: MySQL 비밀번호.
        DB_NAME: MySQL 데이터베이스 이름.
    """

    SECRET_KEY: str
    HTTPS_ONLY: bool = False
    ALLOWED_ORIGINS: list[str] = [
        "http://127.0.0.1:8080",  # 로컬 개발 (프론트엔드)
        "http://localhost:8080",  # 로컬 개발 (프론트엔드)
    ]

    DB_HOST: str
    DB_PORT: int
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str

    JWT_ACCESS_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_EXPIRE_DAYS: int = 7

    # 로컬 개발 시 .env에서 DEBUG=True로 설정. 기본값 False로 프로덕션 안전성 보장
    DEBUG: bool = False
    TESTING: bool = False

    IMAGE_UPLOAD_DIR: str = "assets/posts"
    PROFILE_IMAGE_UPLOAD_DIR: str = "assets/profiles"

    RATE_LIMIT_BACKEND: str = "memory"  # "memory" (로컬) | "redis" (K8s 프로덕션)
    RATE_LIMIT_MAX_IPS: int = 10000  # 메모리 보호를 위한 최대 추적 IP 수
    TRUSTED_PROXIES: set[str] = set()  # 프로덕션에서 nginx 등의 프록시 IP 설정 필요

    # Redis (K8s 환경)
    REDIS_URL: str = ""

    # 이메일 발송 설정
    EMAIL_BACKEND: str = "smtp"  # "ses" (프로덕션) | "smtp" (로컬)
    EMAIL_FROM: str = "noreply@my-community.shop"
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SES_REGION: str = "ap-northeast-2"

    # 프론트엔드 URL (이메일 인증 링크 등에 사용)
    FRONTEND_URL: str = "http://localhost:8080"

    # 내부 API 인증 키 (EventBridge 등 자동화된 호출에서 사용)
    INTERNAL_API_KEY: str = ""

    # WebSocket 푸시 설정 (Lambda 환경에서만 설정, 로컬에서는 빈 문자열)
    WS_DYNAMODB_TABLE: str = ""
    WS_API_GW_ENDPOINT: str = ""

    # WebSocket 백엔드 (K8s: "redis", Lambda: "dynamodb")
    WS_BACKEND: str = "dynamodb"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()  # type: ignore[call-arg]  # pydantic-settings는 .env에서 환경 변수를 불러옴.
