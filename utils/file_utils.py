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
    메모리 효율을 위해 스트리밍(청크 단위) 방식으로 처리합니다.

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

    # 2. 유니크 파일명 생성 및 경로 설정
    unique_filename = f"{uuid.uuid4().hex}{ext}"
    os.makedirs(directory, exist_ok=True)
    file_path = os.path.join(directory, unique_filename)

    # 3. 청크 단위 저장 및 검증
    total_size = 0
    chunk_size = 1024 * 64  # 64KB
    first_chunk = True

    try:
        with open(file_path, "wb") as f:
            while chunk := await file.read(chunk_size):
                total_size += len(chunk)
                
                # 크기 검증
                if total_size > MAX_IMAGE_SIZE:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail={
                            "error": "file_too_large",
                            "message": f"파일 크기는 {MAX_IMAGE_SIZE // (1024 * 1024)}MB를 초과할 수 없습니다.",
                        },
                    )

                # 첫 번째 청크에서 매직 넘버 검증 (확장자 위변조 방지)
                if first_chunk:
                    is_valid_signature = False
                    for signatures in MAGIC_NUMBERS.values():
                        for signature in signatures:
                            if chunk.startswith(signature):
                                is_valid_signature = True
                                break
                        if is_valid_signature:
                            break

                    if not is_valid_signature:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail={
                                "error": "invalid_file_content",
                                "message": "파일의 내용이 유효한 이미지 형식이 아닙니다.",
                            },
                        )
                    first_chunk = False
                
                f.write(chunk)
    except Exception as e:
        # 실패 시 생성된 파일 삭제
        if os.path.exists(file_path):
            os.remove(file_path)
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "file_save_error", "message": "파일 저장 중 오류가 발생했습니다."},
        )

    return f"/{file_path}"
