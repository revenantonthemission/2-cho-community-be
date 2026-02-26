"""스토리지 디스패처.

STORAGE_TYPE 설정에 따라 로컬 파일시스템 또는 S3로 파일 업로드/삭제를 라우팅합니다.
"""

from fastapi import UploadFile

from core.config import settings
from utils.s3_utils import upload_to_s3, delete_from_s3
from utils.storage import save_uploaded_file, delete_file


async def save_file(file: UploadFile, folder: str = "images") -> str:
    """파일을 업로드하고 URL을 반환합니다."""
    if settings.STORAGE_TYPE == "s3":
        return await upload_to_s3(file, folder=folder)
    return await save_uploaded_file(file, folder=folder)


async def delete_image(image_url: str) -> bool:
    """이미지를 삭제합니다."""
    if settings.STORAGE_TYPE == "s3":
        return await delete_from_s3(image_url)
    return delete_file(image_url)
