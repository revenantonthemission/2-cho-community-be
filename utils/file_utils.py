import os
import uuid
from fastapi import UploadFile, HTTPException, status

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
MAX_IMAGE_SIZE = 5 * 1024 * 1024

# 지원하는 이미지 포맷의 매직 넘버 (파일 시그니처)
MAGIC_NUMBERS = {
    "jpg": [b"\xFF\xD8\xFF"],
    "jpeg": [b"\xFF\xD8\xFF"],
    "png": [b"\x89\x50\x4E\x47\x0D\x0A\x1A\x0A"],
    "gif": [b"\x47\x49\x46\x38\x37\x61", b"\x47\x49\x46\x38\x39\x61"],
    "webp": [b"\x52\x49\x46\x46"],  # WEBP (RIFF 헤더)
}


async def save_upload_file(file: UploadFile, directory: str) -> str:
    """이미지 파일을 지정된 디렉토리에 저장하고 URL을 반환합니다.

    보안을 위해 확장자와 실제 파일 헤더(매직 넘버)를 모두 검증합니다.

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

    # 2. 매직 넘버 검증 (보안 강화)
    # 파일의 첫 1KB를 읽어 시그니처 확인
    header = await file.read(1024)
    await file.seek(0)  # 파일 포인터 초기화

    is_valid_signature = False
    for signatures in MAGIC_NUMBERS.values():
        for signature in signatures:
            if header.startswith(signature):
                is_valid_signature = True
                break
        if is_valid_signature:
            break

    if not is_valid_signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_file_content",
                "message": "파일의 내용이 유효한 이미지 형식이 아닙니다 (확장자 위변조 의심).",
            },
        )

    # 3. 크기 검증
    # read()로 인해 커서가 이동했을 수 있으나 seek(0)로 초기화됨.
    # 다시 전체를 읽어 저장 준비.
    contents = await file.read()
    if len(contents) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "file_too_large",
                "message": f"파일 크기는 {MAX_IMAGE_SIZE // (1024 * 1024)}MB를 초과할 수 없습니다.",
            },
        )

    # 4. 유니크 파일명 생성
    unique_filename = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(directory, unique_filename)

    # 5. 디렉토리 생성
    os.makedirs(directory, exist_ok=True)

    # 6. 저장
    with open(file_path, "wb") as f:
        f.write(contents)

    return f"/{file_path}"
