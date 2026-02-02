from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """애플리케이션 설정을 관리하는 클래스.

    환경 변수에서 설정을 로드하며, 기본값을 제공합니다.

    Attributes:
        SECRET_KEY: 세션 암호화 키.
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
        "http://127.0.0.1:8000",
        "http://127.0.0.1:8080",
        "http://localhost:8080",
        "http://localhost:8000",
    ]

    # MySQL Database Settings
    DB_HOST: str
    DB_PORT: int
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str

    # File Upload Settings
    IMAGE_UPLOAD_DIR: str = "assets/posts"
    PROFILE_IMAGE_UPLOAD_DIR: str = "assets/profiles"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()
