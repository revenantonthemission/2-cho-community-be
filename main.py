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
from middleware import TimingMiddleware, LoggingMiddleware, RateLimitMiddleware
from middleware.csrf_protection import CSRFProtectionMiddleware
from middleware.exception_handler import (
    global_exception_handler,
    request_validation_exception_handler,
)
from core.config import settings
from database.connection import init_db, close_db
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
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

# CSRFProtectionMiddleware: CSRF 공격 방어 (Double Submit Cookie 패턴)
# SessionMiddleware 이후 실행하여 세션 쿠키를 읽을 수 있도록 하고,
# RateLimitMiddleware 이전 실행하여 Rate Limiting 우회 방지
app.add_middleware(CSRFProtectionMiddleware)

# RateLimitMiddleware: API 요청 속도 제한 (브루트포스 방지)
app.add_middleware(RateLimitMiddleware)

# CORSMiddleware: CORS 정책을 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "X-CSRF-Token"],  # CSRF 토큰 헤더 허용
)

# ProxyHeadersMiddleware: 리버스 프록시(nginx) 뒤에서 X-Forwarded-Proto 헤더를 처리
# HTTPS 리다이렉트가 올바른 프로토콜을 사용하도록 함
# trusted_hosts: 신뢰할 프록시 IP만 지정 (settings.TRUSTED_PROXIES 또는 기본 localhost)
# "*"는 모든 호스트를 신뢰하므로 보안상 위험 - IP 스푸핑 가능
_proxy_trusted_hosts = list(settings.TRUSTED_PROXIES) if settings.TRUSTED_PROXIES else ["127.0.0.1", "::1"]
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=_proxy_trusted_hosts)

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
app.add_exception_handler(RequestValidationError, request_validation_exception_handler)  # type: ignore[arg-type]
