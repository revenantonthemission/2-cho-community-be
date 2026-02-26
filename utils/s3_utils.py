"""S3 파일 업로드 유틸리티.

AWS S3에 이미지 파일을 업로드하고 URL을 반환합니다.
CLOUDFRONT_DOMAIN이 설정된 경우 CloudFront CDN URL을 반환하고,
그렇지 않으면 직접 S3 URL을 반환합니다 (로컬 개발 및 마이그레이션 전환기용).
"""

import io
import os
import uuid

import boto3
from botocore.exceptions import ClientError
from fastapi import HTTPException, UploadFile, status

from core.config import settings

# 허용된 이미지 확장자 및 MIME 타입
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
}
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB

# 이미지 매직 넘버 (파일 시그니처)
MAGIC_NUMBERS = {
    "jpg": [b"\xFF\xD8\xFF"],
    "jpeg": [b"\xFF\xD8\xFF"],
    "png": [b"\x89\x50\x4E\x47\x0D\x0A\x1A\x0A"],
    "gif": [b"\x47\x49\x46\x38\x37\x61", b"\x47\x49\x46\x38\x39\x61"],
    "webp": [b"\x52\x49\x46\x46"],
}


def get_s3_client():
    """S3 클라이언트를 생성합니다."""
    kwargs: dict[str, str] = {"region_name": settings.AWS_REGION}
    if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
        kwargs["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
        kwargs["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY
    return boto3.client("s3", **kwargs)


def build_image_url(s3_key: str) -> str:
    """S3 키로부터 이미지 접근 URL을 생성합니다.

    CLOUDFRONT_DOMAIN이 설정된 경우 CloudFront URL을 반환하고,
    그렇지 않으면 직접 S3 URL을 반환합니다 (로컬 개발 및 CloudFront 설정 전).

    Args:
        s3_key: S3 객체 키 (예: "profiles/uuid.jpg")

    Returns:
        이미지 공개 URL
    """
    if settings.CLOUDFRONT_DOMAIN:
        domain = settings.CLOUDFRONT_DOMAIN.rstrip("/")
        return f"https://{domain}/{s3_key}"
    return f"https://{settings.AWS_S3_BUCKET_NAME}.s3.{settings.AWS_REGION}.amazonaws.com/{s3_key}"


def extract_s3_key(image_url: str) -> str:
    """이미지 URL에서 S3 키를 추출합니다.

    CloudFront URL과 직접 S3 URL 모두 지원합니다.

    Args:
        image_url: CloudFront URL 또는 S3 직접 URL

    Returns:
        S3 객체 키 (예: "profiles/uuid.jpg")
    """
    # CloudFront URL (설정된 도메인으로 매칭):
    # https://d1234.cloudfront.net/profiles/uuid.jpg
    if settings.CLOUDFRONT_DOMAIN and settings.CLOUDFRONT_DOMAIN in image_url:
        domain = settings.CLOUDFRONT_DOMAIN.rstrip("/")
        return image_url.split(f"https://{domain}/")[-1]

    # CloudFront URL (도메인 미설정 시 패턴으로 매칭):
    # CLOUDFRONT_DOMAIN이 초기화된 후 롤백하거나 환경변수를 지운 경우에도 동작
    if ".cloudfront.net/" in image_url:
        return image_url.split(".cloudfront.net/")[-1]

    # 직접 S3 URL: https://bucket.s3.region.amazonaws.com/profiles/uuid.jpg
    s3_suffix = f".s3.{settings.AWS_REGION}.amazonaws.com/"
    if s3_suffix in image_url:
        return image_url.split(s3_suffix)[-1]

    # Fallback: 로컬 경로 (/assets/posts/image.jpg 등 S3 이전 레거시 레코드)
    return image_url.lstrip("/")


def validate_image_signature(first_chunk: bytes) -> bool:
    """파일의 첫 번째 청크에서 매직 넘버를 검증합니다.

    Args:
        first_chunk: 파일의 첫 번째 청크 데이터.

    Returns:
        유효한 이미지 시그니처인 경우 True, 아니면 False.
    """
    for signatures in MAGIC_NUMBERS.values():
        for signature in signatures:
            if first_chunk.startswith(signature):
                return True
    return False


async def upload_to_s3(
    file: UploadFile,
    folder: str = "images",
) -> str:
    """이미지 파일을 S3에 업로드하고 URL을 반환합니다.

    파일 검증 과정:
    1. 확장자 검증
    2. MIME 타입 검증
    3. 파일 크기 검증 (스트리밍 중)
    4. 매직 넘버 검증 (첫 번째 청크)

    Args:
        file: 업로드된 파일 객체.
        folder: S3 버킷 내 저장 폴더 (예: "images", "profiles", "posts").

    Returns:
        CloudFront URL (CLOUDFRONT_DOMAIN 설정 시) 또는 S3 직접 URL.

    Raises:
        HTTPException: 파일 형식이 잘못되었거나 크기가 초과된 경우.
    """
    # 1. 확장자 검증
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

    # 2. MIME 타입 검증
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_content_type",
                "message": f"허용된 콘텐츠 타입: {', '.join(ALLOWED_MIME_TYPES)}",
            },
        )

    # 3. 고유 파일명 생성
    unique_filename = f"{uuid.uuid4().hex}{ext}"
    s3_key = f"{folder}/{unique_filename}"

    # 4. 파일 내용을 메모리로 읽기 (청크 단위로 검증)
    file_buffer = io.BytesIO()
    total_size = 0
    chunk_size = 1024 * 64  # 64KB
    first_chunk = True

    try:
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

            # 첫 번째 청크에서 매직 넘버 검증
            if first_chunk:
                if not validate_image_signature(chunk):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail={
                            "error": "invalid_file_content",
                            "message": "파일의 내용이 유효한 이미지 형식이 아닙니다.",
                        },
                    )
                first_chunk = False

            file_buffer.write(chunk)

        # 5. S3 업로드
        if first_chunk:
            # 루프가 한 번도 실행되지 않음 — 빈 파일
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "empty_file", "message": "파일이 비어 있습니다."},
            )

        file_buffer.seek(0)
        s3_client = get_s3_client()

        # CLOUDFRONT_DOMAIN이 설정되기 전(전환 기간)에는 public-read ACL을 유지하여
        # 직접 S3 URL로도 이미지에 접근 가능하도록 함.
        # CloudFront OAC 설정 후에는 ACL 없이 버킷 정책으로만 접근 제어.
        extra_args: dict[str, str] = {"ContentType": file.content_type}
        if not settings.CLOUDFRONT_DOMAIN:
            extra_args["ACL"] = "public-read"

        s3_client.upload_fileobj(
            file_buffer,
            settings.AWS_S3_BUCKET_NAME,
            s3_key,
            ExtraArgs=extra_args,
        )

        # 6. URL 반환 (CloudFront 또는 S3 직접)
        return build_image_url(s3_key)

    except ClientError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "s3_upload_error",
                "message": f"S3 업로드 중 오류가 발생했습니다: {str(e)}",
            },
        )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "upload_error",
                "message": "파일 업로드 중 오류가 발생했습니다.",
            },
        )


async def delete_from_s3(image_url: str) -> bool:
    """S3에서 파일을 삭제합니다.

    CloudFront URL과 직접 S3 URL 모두 지원합니다.

    Args:
        image_url: 삭제할 파일의 URL (CloudFront URL 또는 S3 직접 URL).

    Returns:
        성공하면 True, 실패하면 False.
    """
    try:
        s3_key = extract_s3_key(image_url)
        s3_client = get_s3_client()
        s3_client.delete_object(
            Bucket=settings.AWS_S3_BUCKET_NAME,
            Key=s3_key,
        )
        return True

    except ClientError:
        return False
