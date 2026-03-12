"""스토리지 디스패처.

STORAGE_BACKEND 환경변수에 따라 로컬 파일시스템 또는 S3로 라우팅합니다.
- "local" (기본): 로컬 디스크에 저장 (개발 환경, Lambda EFS)
- "s3": S3 버킷에 저장 (K8s 프로덕션)
"""

import os

from fastapi import UploadFile

_STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local")


async def save_file(file: UploadFile, folder: str = "images") -> str:
    """파일을 업로드하고 URL을 반환합니다."""
    if _STORAGE_BACKEND == "s3":
        from utils.storage_s3 import save_uploaded_file_s3

        return await save_uploaded_file_s3(file, folder=folder)

    from utils.storage import save_uploaded_file

    return await save_uploaded_file(file, folder=folder)


async def delete_image(image_url: str) -> bool:
    """이미지를 삭제합니다."""
    if _STORAGE_BACKEND == "s3":
        from utils.storage_s3 import delete_file_s3

        return delete_file_s3(image_url)

    from utils.storage import delete_file

    return delete_file(image_url)
