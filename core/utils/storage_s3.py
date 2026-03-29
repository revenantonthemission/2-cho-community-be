"""S3 file storage utility.

S3 버킷에 이미지를 업로드하고 공개 URL을 반환합니다.
CloudFront 도메인이 설정된 경우 CDN URL을 반환합니다.
"""

import logging
import os
import threading
import uuid

from fastapi import HTTPException, UploadFile, status

from core.utils.storage import (
    ALLOWED_IMAGE_EXTENSIONS,
    ALLOWED_MIME_TYPES,
    MAX_IMAGE_SIZE,
    validate_image_signature,
)

logger = logging.getLogger(__name__)

S3_UPLOADS_BUCKET = os.getenv("S3_UPLOADS_BUCKET", "")
S3_UPLOADS_PREFIX = os.getenv("S3_UPLOADS_PREFIX", "uploads")
S3_UPLOADS_CDN_DOMAIN = os.getenv("S3_UPLOADS_CDN_DOMAIN", "")
S3_REGION = os.getenv("S3_REGION", "ap-northeast-2")

_s3_client = None
_s3_lock = threading.Lock()


def _get_s3_client():
    """S3 클라이언트 지연 초기화 (double-checked locking으로 경쟁 방지)."""
    global _s3_client
    if _s3_client is None:
        with _s3_lock:
            if _s3_client is None:
                import boto3

                _s3_client = boto3.client("s3", region_name=S3_REGION)
    return _s3_client


def _build_url(key: str) -> str:
    """S3 키에서 공개 URL을 생성합니다."""
    if S3_UPLOADS_CDN_DOMAIN:
        return f"https://{S3_UPLOADS_CDN_DOMAIN}/{key}"
    return f"https://{S3_UPLOADS_BUCKET}.s3.{S3_REGION}.amazonaws.com/{key}"


async def save_uploaded_file_s3(file: UploadFile, folder: str = "images") -> str:
    """S3에 파일을 업로드하고 공개 URL을 반환합니다.

    검증 로직은 로컬 스토리지와 동일합니다.

    Args:
        file: FastAPI UploadFile 객체.
        folder: S3 키 프리픽스 내 하위 폴더 (e.g., "posts", "profiles").

    Returns:
        S3 공개 URL 또는 CDN URL.

    Raises:
        HTTPException: 검증 실패 시.
    """
    import asyncio

    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_filename", "message": "파일명이 없습니다."},
        )

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_file_type",
                "message": f"허용된 이미지 형식: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}",
            },
        )

    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_content_type",
                "message": f"허용된 콘텐츠 타입: {', '.join(ALLOWED_MIME_TYPES)}",
            },
        )

    content = await file.read()

    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "empty_file", "message": "파일이 비어 있습니다."},
        )

    if len(content) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "file_too_large",
                "message": f"파일 크기는 {MAX_IMAGE_SIZE // (1024 * 1024)}MB를 초과할 수 없습니다.",
            },
        )

    if not await asyncio.to_thread(validate_image_signature, content):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_file_content",
                "message": "파일의 내용이 유효한 이미지 형식이 아닙니다.",
            },
        )

    # Resize image based on folder (purpose) — CPU 바운드, 이벤트 루프 차단 방지
    from core.utils.image_resize import resize_for_post, resize_for_profile

    if folder == "profiles":
        content = await asyncio.to_thread(resize_for_profile, content)
    elif folder in ("posts", "images"):
        content = await asyncio.to_thread(resize_for_post, content)

    unique_filename = f"{uuid.uuid4().hex}{ext}"
    key = f"{S3_UPLOADS_PREFIX}/{folder}/{unique_filename}"

    s3 = _get_s3_client()
    await asyncio.to_thread(
        s3.put_object,
        Bucket=S3_UPLOADS_BUCKET,
        Key=key,
        Body=content,
        ContentType=file.content_type,
    )

    return _build_url(key)


def delete_file_s3(url: str) -> bool:
    """S3에서 파일을 삭제합니다.

    Args:
        url: S3 URL 또는 CDN URL.

    Returns:
        True if deleted, False otherwise.
    """
    key = _url_to_key(url)
    if not key:
        return False

    try:
        s3 = _get_s3_client()
        s3.delete_object(Bucket=S3_UPLOADS_BUCKET, Key=key)
        return True
    except Exception:
        logger.exception("S3 파일 삭제 실패: %s", url)
        return False


def _url_to_key(url: str) -> str | None:
    """URL에서 S3 키를 추출합니다."""
    if not url:
        return None

    # CDN URL: https://cdn.example.com/uploads/profiles/uuid.jpg
    if S3_UPLOADS_CDN_DOMAIN and S3_UPLOADS_CDN_DOMAIN in url:
        prefix = f"https://{S3_UPLOADS_CDN_DOMAIN}/"
        if url.startswith(prefix):
            return url[len(prefix) :]

    # S3 URL: https://bucket.s3.region.amazonaws.com/uploads/profiles/uuid.jpg
    s3_prefix = f"https://{S3_UPLOADS_BUCKET}.s3.{S3_REGION}.amazonaws.com/"
    if url.startswith(s3_prefix):
        return url[len(s3_prefix) :]

    return None
