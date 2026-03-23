"""파일 업로드/삭제 보안 단위 테스트.

Path Traversal, MIME 검증, 매직 넘버 검증 등 보안 로직을 검증한다.
tmp_path + monkeypatch로 실제 파일시스템을 격리한다.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException, UploadFile

from utils.storage import delete_file, save_uploaded_file

# ---------------------------------------------------------------------------
# 헬퍼: UploadFile mock 생성
# ---------------------------------------------------------------------------


def _make_upload_file(
    filename: str = "test.jpg",
    content_type: str = "image/jpeg",
    content: bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 100,
) -> MagicMock:
    """테스트용 UploadFile mock을 생성한다."""
    mock = MagicMock(spec=UploadFile)
    mock.filename = filename
    mock.content_type = content_type
    mock.read = AsyncMock(return_value=content)
    return mock


# ---------------------------------------------------------------------------
# 정상 동작
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_file_succeeds(tmp_path, monkeypatch):
    """유효한 JPEG 파일 저장이 성공해야 한다."""
    # Arrange
    monkeypatch.setattr("utils.storage.UPLOAD_DIR", tmp_path)
    file = _make_upload_file()

    # Act
    url = await save_uploaded_file(file, folder="images")

    # Assert — URL 형식 및 파일 존재 확인
    assert url.startswith("/uploads/images/")
    assert url.endswith(".jpg")

    # 실제 파일이 생성되었는지 확인
    saved_files = list((tmp_path / "images").iterdir())
    assert len(saved_files) == 1


@pytest.mark.asyncio
async def test_delete_file_succeeds(tmp_path, monkeypatch):
    """파일 삭제가 성공해야 한다."""
    # Arrange
    monkeypatch.setattr("utils.storage.UPLOAD_DIR", tmp_path)
    (tmp_path / "images").mkdir()
    test_file = tmp_path / "images" / "test-file.jpg"
    test_file.write_bytes(b"fake image data")

    # Act
    result = delete_file("/uploads/images/test-file.jpg")

    # Assert
    assert result is True
    assert not test_file.exists()


# ---------------------------------------------------------------------------
# Path Traversal 방지
# ---------------------------------------------------------------------------


def test_path_traversal_rejected(tmp_path, monkeypatch):
    """상위 디렉토리 접근 경로가 거부되어야 한다."""
    monkeypatch.setattr("utils.storage.UPLOAD_DIR", tmp_path)

    # Act
    result = delete_file("/uploads/../../../etc/passwd")

    # Assert — uploads 접두사는 있지만 resolve 후 UPLOAD_DIR 외부이므로 거부
    assert result is False


def test_nested_path_traversal_rejected(tmp_path, monkeypatch):
    """중첩된 상위 디렉토리 접근 경로가 거부되어야 한다."""
    monkeypatch.setattr("utils.storage.UPLOAD_DIR", tmp_path)

    # Act
    result = delete_file("/uploads/images/../../etc/passwd")

    # Assert
    assert result is False


# ---------------------------------------------------------------------------
# MIME / 확장자 검증
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invalid_mime_type_rejected(tmp_path, monkeypatch):
    """허용되지 않은 MIME 타입이 거부되어야 한다."""
    # Arrange
    monkeypatch.setattr("utils.storage.UPLOAD_DIR", tmp_path)
    file = _make_upload_file(
        filename="malware.jpg",
        content_type="application/exe",
    )

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await save_uploaded_file(file)
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["error"] == "invalid_content_type"


@pytest.mark.asyncio
async def test_invalid_extension_rejected(tmp_path, monkeypatch):
    """허용되지 않은 확장자가 거부되어야 한다."""
    # Arrange
    monkeypatch.setattr("utils.storage.UPLOAD_DIR", tmp_path)
    file = _make_upload_file(
        filename="payload.exe",
        content_type="image/jpeg",
    )

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await save_uploaded_file(file)
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["error"] == "invalid_file_type"


# ---------------------------------------------------------------------------
# 빈 파일 / 잘못된 시그니처
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_file_rejected(tmp_path, monkeypatch):
    """빈 파일(0 bytes)이 거부되어야 한다."""
    # Arrange
    monkeypatch.setattr("utils.storage.UPLOAD_DIR", tmp_path)
    file = _make_upload_file(content=b"")

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await save_uploaded_file(file)
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["error"] == "empty_file"


@pytest.mark.asyncio
async def test_invalid_file_signature_rejected(tmp_path, monkeypatch):
    """올바른 확장자/MIME이지만 잘못된 매직 넘버가 거부되어야 한다."""
    # Arrange — 텍스트 데이터를 JPEG로 위장
    monkeypatch.setattr("utils.storage.UPLOAD_DIR", tmp_path)
    file = _make_upload_file(
        filename="fake.jpg",
        content_type="image/jpeg",
        content=b"This is not an image file at all",
    )

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await save_uploaded_file(file)
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["error"] == "invalid_file_content"
