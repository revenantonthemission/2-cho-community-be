# K8s 환경용 FastAPI 이미지 (Lambda와 별도)
FROM python:3.13-slim

ARG APP_VERSION=dev
LABEL maintainer="my-community"
LABEL version="${APP_VERSION}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# uv 패키지 매니저
COPY --from=ghcr.io/astral-sh/uv:0.6 /uv /uvx /bin/

# 시스템 의존성 (mysqlclient 빌드용)
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc default-libmysqlclient-dev pkg-config libmagic1 && \
    rm -rf /var/lib/apt/lists/*

# Python 의존성 설치 (소스 코드 없이 의존성만 먼저 캐싱)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --extra k8s --no-install-project

# 애플리케이션 코드
COPY . .
RUN uv sync --frozen --no-dev --extra k8s
RUN mkdir -p assets/posts assets/profiles

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
