"""main: FastAPI 애플리케이션의 메인 진입점.

애플리케이션 설정, 미들웨어 구성, 라우터 등록, 전역 예외 핸들러를 설정합니다.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from routers.auth_router import auth_router
from routers.user_router import user_router
from routers.post_router import post_router
from routers.terms_router import terms_router
from middleware import TimingMiddleware, LoggingMiddleware
from middleware.exception_handler import (
    global_exception_handler,
    request_validation_exception_handler,
)
from core.config import settings
from database.connection import init_db, close_db
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
import os


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 생명주기 관리.

    시작 시 데이터베이스 연결 풀을 초기화하고,
    종료 시 연결 풀을 정리합니다.
    """
    # 시작: 데이터베이스 연결 풀 초기화
    await init_db()
    yield
    # 종료: 데이터베이스 연결 풀 해제
    await close_db()


# FastAPI 인스턴스 생성
app = FastAPI(
    title="2cho Community API",
    description="커뮤니티 백엔드 API 서버",
    version="1.0.0",
    lifespan=lifespan,
)
"""FastAPI 애플리케이션 인스턴스."""

# 미들웨어 추가

# TimingMiddleware: 각 요청에 타임스탬프를 주입
app.add_middleware(TimingMiddleware)

# LoggingMiddleware: 요청/응답을 로깅
app.add_middleware(LoggingMiddleware)

# SessionMiddleware: 모든 요청과 응답에서 세션을 처리
# 프로젝트 루트에 .env 파일이 있어야 하고 그 안에 SECRET_KEY="..."가 있어야 함
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    max_age=24 * 60 * 60,
    https_only=settings.HTTPS_ONLY,
    same_site="lax",
)

# CORSMiddleware: CORS 정책을 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type"],
)

# 라우터 추가
app.include_router(auth_router)
app.include_router(user_router)
app.include_router(post_router)
app.include_router(terms_router)

# 정적 파일 서빙 설정
# assets 디렉토리가 없으면 생성 (안전장치)
os.makedirs("assets", exist_ok=True)

app.mount("/assets", StaticFiles(directory="assets"), name="assets")


@app.get("/health", status_code=200)
async def health_check():
    """서버 상태 및 DB 연결 확인."""
    from database.connection import test_connection

    if await test_connection():
        return {"status": "ok", "database": "connected"}
    return {"status": "error", "database": "disconnected"}


# 전역 예외 핸들러 등록


app.add_exception_handler(Exception, global_exception_handler)
app.add_exception_handler(RequestValidationError, request_validation_exception_handler)
