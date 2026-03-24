"""Posts 도메인 — 이미지 업로드 테스트."""

from unittest.mock import patch

import pytest

from tests.conftest import create_verified_user

# JPEG 매직넘버 + 가짜 바이트
FAKE_JPEG = b"\xff\xd8\xff" + b"\x00" * 100


# ---------------------------------------------------------------------------
# 이미지 업로드 성공
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_post_image_succeeds(client, fake, tmp_path):
    """유효한 JPEG 파일 업로드 시 201과 이미지 URL을 반환한다."""
    user = await create_verified_user(client, fake)

    with patch("core.utils.storage.UPLOAD_DIR", tmp_path):
        res = await client.post(
            "/v1/posts/image",
            files={"file": ("test.jpg", FAKE_JPEG, "image/jpeg")},
            headers=user["headers"],
        )

    assert res.status_code == 201
    data = res.json()["data"]
    assert "url" in data
    assert data["url"].startswith("/uploads/posts/")
    assert data["url"].endswith(".jpg")


# ---------------------------------------------------------------------------
# 잘못된 MIME 타입
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_invalid_mime_type_returns_400(client, fake, tmp_path):
    """허용되지 않는 MIME 타입의 파일 업로드 시 400을 반환한다."""
    user = await create_verified_user(client, fake)

    with patch("core.utils.storage.UPLOAD_DIR", tmp_path):
        res = await client.post(
            "/v1/posts/image",
            files={"file": ("test.txt", b"plain text", "text/plain")},
            headers=user["headers"],
        )

    assert res.status_code == 400


# ---------------------------------------------------------------------------
# PNG 파일 업로드
# ---------------------------------------------------------------------------


FAKE_PNG = b"\x89\x50\x4e\x47\x0d\x0a\x1a\x0a" + b"\x00" * 100


@pytest.mark.asyncio
async def test_upload_png_image_succeeds(client, fake, tmp_path):
    """유효한 PNG 파일 업로드 시 201을 반환한다."""
    user = await create_verified_user(client, fake)

    with patch("core.utils.storage.UPLOAD_DIR", tmp_path):
        res = await client.post(
            "/v1/posts/image",
            files={"file": ("test.png", FAKE_PNG, "image/png")},
            headers=user["headers"],
        )

    assert res.status_code == 201
    assert res.json()["data"]["url"].endswith(".png")
