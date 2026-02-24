"""Tests for local file storage utility."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import UploadFile, HTTPException

from utils.storage import save_uploaded_file, delete_file, UPLOAD_DIR


@pytest.fixture
def temp_upload_dir(tmp_path):
    """Create a temporary upload directory."""
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    with patch("utils.storage.UPLOAD_DIR", upload_dir):
        yield upload_dir


@pytest.fixture
def mock_upload_file():
    """Create a mock UploadFile with valid JPEG content."""
    file = MagicMock(spec=UploadFile)
    file.filename = "test_image.jpg"
    file.content_type = "image/jpeg"
    # Valid JPEG magic number + fake content
    file.read = AsyncMock(return_value=b"\xFF\xD8\xFF" + b"fake image content")
    return file


@pytest.mark.asyncio
async def test_save_uploaded_file_success(temp_upload_dir, mock_upload_file):
    """Test successful file upload."""
    url = await save_uploaded_file(mock_upload_file, folder="posts")

    assert url.startswith("/uploads/posts/")
    assert url.endswith(".jpg")

    # Verify file was actually saved
    filename = url.replace("/uploads/posts/", "")
    saved_path = temp_upload_dir / "posts" / filename
    assert saved_path.exists()


@pytest.mark.asyncio
async def test_save_uploaded_file_creates_folder(temp_upload_dir, mock_upload_file):
    """Test that folder is created if it doesn't exist."""
    url = await save_uploaded_file(mock_upload_file, folder="new_folder")

    assert url.startswith("/uploads/new_folder/")
    assert (temp_upload_dir / "new_folder").exists()


@pytest.mark.asyncio
async def test_save_uploaded_file_invalid_extension(temp_upload_dir):
    """Test rejection of invalid file extension."""
    file = MagicMock(spec=UploadFile)
    file.filename = "malware.exe"
    file.content_type = "application/octet-stream"

    with pytest.raises(HTTPException) as exc_info:
        await save_uploaded_file(file, folder="posts")

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["error"] == "invalid_file_type"


@pytest.mark.asyncio
async def test_save_uploaded_file_invalid_mime_type(temp_upload_dir):
    """Test rejection of invalid MIME type."""
    file = MagicMock(spec=UploadFile)
    file.filename = "image.jpg"
    file.content_type = "text/plain"

    with pytest.raises(HTTPException) as exc_info:
        await save_uploaded_file(file, folder="posts")

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["error"] == "invalid_content_type"


@pytest.mark.asyncio
async def test_save_uploaded_file_empty_file(temp_upload_dir):
    """Test rejection of empty file."""
    file = MagicMock(spec=UploadFile)
    file.filename = "empty.jpg"
    file.content_type = "image/jpeg"
    file.read = AsyncMock(return_value=b"")

    with pytest.raises(HTTPException) as exc_info:
        await save_uploaded_file(file, folder="posts")

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["error"] == "empty_file"


@pytest.mark.asyncio
async def test_save_uploaded_file_invalid_signature(temp_upload_dir):
    """Test rejection of file with invalid magic number."""
    file = MagicMock(spec=UploadFile)
    file.filename = "fake.jpg"
    file.content_type = "image/jpeg"
    file.read = AsyncMock(return_value=b"not a real image")

    with pytest.raises(HTTPException) as exc_info:
        await save_uploaded_file(file, folder="posts")

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["error"] == "invalid_file_content"


@pytest.mark.asyncio
async def test_save_uploaded_file_no_filename(temp_upload_dir):
    """Test rejection of file without filename."""
    file = MagicMock(spec=UploadFile)
    file.filename = None
    file.content_type = "image/jpeg"

    with pytest.raises(HTTPException) as exc_info:
        await save_uploaded_file(file, folder="posts")

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["error"] == "invalid_filename"


def test_delete_file_success(temp_upload_dir):
    """Test successful file deletion."""
    # Create a file to delete
    test_file = temp_upload_dir / "posts" / "test.jpg"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_bytes(b"test content")

    result = delete_file("/uploads/posts/test.jpg")

    assert result is True
    assert not test_file.exists()


def test_delete_file_not_found(temp_upload_dir):
    """Test deletion of non-existent file."""
    result = delete_file("/uploads/posts/nonexistent.jpg")

    assert result is False


def test_delete_file_invalid_path(temp_upload_dir):
    """Test rejection of paths outside uploads directory."""
    result = delete_file("/etc/passwd")

    assert result is False
