from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers.user_router import router as user_router

app = FastAPI()

# 메인 어플리케이션에 라우터 포함
app.include_router(user_router, tags=["users"])

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