from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv
from os import getenv
from routers.auth_router import auth_router
from routers.user_router import user_router

# .env 로드
load_dotenv()

# FastAPI 인스턴스 생성
app = FastAPI()

# SessionMiddleware: 모든 요청과 응답에서 세션을 처리.
# 프로젝트 루트에 .env 파일이 있어야 하고 그 안에 secret_key=".."와 같은 데이터가 있어야 합니다!
app.add_middleware(
    SessionMiddleware,
    secret_key=getenv("SECRET_KEY"),
    max_age=24 * 60 * 60,
    same_site="lax",
    https_only=False,
)

# 허용된 origin 목록
origins = [
    "http://localhost",
    "http://localhost:8000",
]

# CORSMiddleware 추가
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 추가
app.include_router(auth_router)
app.include_router(user_router)
