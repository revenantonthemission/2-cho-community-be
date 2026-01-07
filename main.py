from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers.user_router import router as user_router

app = FastAPI()
app.include_router(user_router, tags=["users"])

origins = [
    "http://localhost",
    "http://localhost:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)