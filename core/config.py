from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """애플리케이션 설정을 관리하는 클래스.

    환경 변수에서 설정을 로드하며, 기본값을 제공합니다.
    """

    SECRET_KEY: str
    ALLOWED_ORIGINS: list[str] = [
        "http://127.0.0.1:8000",
        "http://127.0.0.1:5500",
        "http://127.0.0.1:8080",
    ]

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()
