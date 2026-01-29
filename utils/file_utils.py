import os
import uuid
from fastapi import UploadFile, HTTPException, status

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
MAX_IMAGE_SIZE = 5 * 1024 * 1024


async def save_upload_file(file: UploadFile, directory: str) -> str:
    """이미지 파일을 지정된 디렉토리에 저장하고 URL을 반환합니다.

    Args:
        file: 업로드된 파일 객체.
        directory: 저장할 디렉토리 경로.

    Returns:
        저장된 파일의 URL (예: /assets/posts/filename.jpg).

    Raises:
        HTTPException: 파일 형식이 잘못되었거나 크기가 너무 클 경우.
    """
    # 1. 확장자 검증
    filename = file.filename or ""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_file_type",
                "message": f"허용된 이미지 형식: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}",
            },
        )

    # 2. 크기 검증
    # 주의: read()는 메모리에 파일을 올리므로 큰 파일은 stream으로 처리하는 것이 좋지만,
    # 여기서는 5MB 제한이 있으므로 read() 후 len() 체크도 괜찮음.
    contents = await file.read()
    if len(contents) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "file_too_large",
                "message": f"파일 크기는 {MAX_IMAGE_SIZE // (1024 * 1024)}MB를 초과할 수 없습니다.",
            },
        )

    # 3. 유니크 파일명 생성
    unique_filename = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(directory, unique_filename)

    # 4. 디렉토리 생성
    os.makedirs(directory, exist_ok=True)

    # 5. 저장
    with open(file_path, "wb") as f:
        f.write(contents)

    return f"/{file_path}"
