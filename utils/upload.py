"""스토리지 디스패처.

로컬 파일시스템으로 파일 업로드/삭제를 라우팅합니다.
"""

from fastapi import UploadFile

from utils.storage import save_uploaded_file, delete_file


async def save_file(file: UploadFile, folder: str = "images") -> str:
    """파일을 업로드하고 URL을 반환합니다."""
    return await save_uploaded_file(file, folder=folder)


async def delete_image(image_url: str) -> bool:
    """이미지를 삭제합니다."""
    return delete_file(image_url)
