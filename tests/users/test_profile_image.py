"""Users 도메인 — 프로필 이미지 업로드 테스트."""

import pytest
from httpx import AsyncClient

from tests.conftest import create_verified_user

# ---------------------------------------------------------------------------
# 프로필 이미지 업로드 성공
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_profile_image_succeeds(client: AsyncClient, fake, tmp_path, monkeypatch):
    """POST /v1/users/profile/image — 유효한 JPEG 이미지 업로드가 성공한다."""
    # Arrange — UPLOAD_DIR을 임시 디렉토리로 변경
    monkeypatch.setattr("utils.storage.UPLOAD_DIR", tmp_path)
    user = await create_verified_user(client, fake)

    # JPEG 매직 넘버를 포함한 최소한의 바이트 데이터
    jpeg_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 100

    # Act
    res = await user["client"].post(
        "/v1/users/profile/image",
        files={"file": ("test.jpg", jpeg_bytes, "image/jpeg")},
    )

    # Assert
    assert res.status_code == 201
    data = res.json()["data"]
    assert "url" in data
    assert data["url"].startswith("/uploads/profiles/")
    assert data["url"].endswith(".jpg")


# ---------------------------------------------------------------------------
# 프로필 이미지 업로드 실패
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_invalid_mime_type_returns_400(client: AsyncClient, fake, tmp_path, monkeypatch):
    """허용되지 않은 MIME 타입(text/plain) 업로드 시 400을 반환한다."""
    # Arrange
    monkeypatch.setattr("utils.storage.UPLOAD_DIR", tmp_path)
    user = await create_verified_user(client, fake)

    # Act
    res = await user["client"].post(
        "/v1/users/profile/image",
        files={"file": ("test.txt", b"not an image", "text/plain")},
    )

    # Assert
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_upload_invalid_extension_returns_400(client: AsyncClient, fake, tmp_path, monkeypatch):
    """허용되지 않은 확장자(.bmp) 업로드 시 400을 반환한다."""
    # Arrange
    monkeypatch.setattr("utils.storage.UPLOAD_DIR", tmp_path)
    user = await create_verified_user(client, fake)

    # Act — .bmp 확장자는 ALLOWED_IMAGE_EXTENSIONS에 포함되지 않음
    res = await user["client"].post(
        "/v1/users/profile/image",
        files={"file": ("test.bmp", b"\x42\x4d" + b"\x00" * 100, "image/bmp")},
    )

    # Assert
    assert res.status_code == 400
