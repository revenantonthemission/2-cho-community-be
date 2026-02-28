"""Local file storage utility.

Saves uploaded images to the local filesystem and returns URL paths.
Nginx serves files from /uploads/* mapped to this directory.
"""

import os
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

# Upload directory (configurable via environment variable)
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "/mnt/uploads"))

# 허용된 이미지 확장자 및 MIME 타입
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
}
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB

# Image magic numbers (file signatures)
MAGIC_NUMBERS = {
    "jpg": [b"\xFF\xD8\xFF"],
    "jpeg": [b"\xFF\xD8\xFF"],
    "png": [b"\x89\x50\x4E\x47\x0D\x0A\x1A\x0A"],
    "gif": [b"\x47\x49\x46\x38\x37\x61", b"\x47\x49\x46\x38\x39\x61"],
    "webp": [b"\x52\x49\x46\x46"],
}


def validate_image_signature(data: bytes) -> bool:
    """Validate file content against known image signatures.

    Args:
        data: File content bytes.

    Returns:
        True if valid image signature, False otherwise.
    """
    for signatures in MAGIC_NUMBERS.values():
        for signature in signatures:
            if data.startswith(signature):
                return True
    return False


async def save_uploaded_file(file: UploadFile, folder: str = "images") -> str:
    """Save uploaded file to local storage and return URL path.

    Validates:
    1. File extension
    2. MIME type
    3. File size (max 5MB)
    4. Magic number (file signature)

    Args:
        file: FastAPI UploadFile object.
        folder: Subdirectory within uploads (e.g., "posts", "profiles").

    Returns:
        URL path for nginx to serve (e.g., "/uploads/posts/uuid.jpg").

    Raises:
        HTTPException: If validation fails.
    """
    # 1. Validate filename exists
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_filename", "message": "파일명이 없습니다."},
        )

    # 2. Validate extension
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_file_type",
                "message": f"허용된 이미지 형식: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}",
            },
        )

    # 3. Validate MIME type
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_content_type",
                "message": f"허용된 콘텐츠 타입: {', '.join(ALLOWED_MIME_TYPES)}",
            },
        )

    # 4. Read file content
    content = await file.read()

    # 5. Validate not empty
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "empty_file", "message": "파일이 비어 있습니다."},
        )

    # 6. Validate size
    if len(content) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "file_too_large",
                "message": f"파일 크기는 {MAX_IMAGE_SIZE // (1024 * 1024)}MB를 초과할 수 없습니다.",
            },
        )

    # 7. Validate magic number
    if not validate_image_signature(content):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_file_content",
                "message": "파일의 내용이 유효한 이미지 형식이 아닙니다.",
            },
        )

    # 8. Generate unique filename and save
    unique_filename = f"{uuid.uuid4().hex}{ext}"
    save_dir = UPLOAD_DIR / folder
    save_dir.mkdir(parents=True, exist_ok=True)

    file_path = save_dir / unique_filename
    file_path.write_bytes(content)

    # 9. Return URL path (nginx serves /uploads/*)
    return f"/uploads/{folder}/{unique_filename}"


def delete_file(url_path: str) -> bool:
    """Delete a file by its URL path.

    Args:
        url_path: URL path like "/uploads/posts/uuid.jpg".

    Returns:
        True if deleted successfully, False otherwise.
    """
    # Security: only allow paths starting with /uploads/
    if not url_path.startswith("/uploads/"):
        return False

    relative_path = url_path.replace("/uploads/", "", 1)
    file_path = (UPLOAD_DIR / relative_path).resolve()

    # Path Traversal 방지: 해석된 경로가 UPLOAD_DIR 내부인지 검증 (Python 3.9+)
    upload_dir_resolved = UPLOAD_DIR.resolve()
    if not file_path.is_relative_to(upload_dir_resolved):
        return False

    if file_path.exists():
        file_path.unlink()
        return True
    return False
