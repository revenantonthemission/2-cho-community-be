"""Unit tests for storage dispatcher (utils/upload.py)."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_save_file_dispatches_to_local(monkeypatch):
    """STORAGE_TYPE=local should call save_uploaded_file."""
    monkeypatch.setattr("utils.upload.settings.STORAGE_TYPE", "local")

    mock_file = MagicMock()
    with patch("utils.upload.save_uploaded_file", new_callable=AsyncMock) as mock_local:
        mock_local.return_value = "/uploads/posts/test.jpg"
        from utils.upload import save_file
        result = await save_file(mock_file, folder="posts")
        mock_local.assert_called_once_with(mock_file, folder="posts")
        assert result == "/uploads/posts/test.jpg"


@pytest.mark.asyncio
async def test_save_file_dispatches_to_s3(monkeypatch):
    """STORAGE_TYPE=s3 should call upload_to_s3."""
    monkeypatch.setattr("utils.upload.settings.STORAGE_TYPE", "s3")

    mock_file = MagicMock()
    with patch("utils.upload.upload_to_s3", new_callable=AsyncMock) as mock_s3:
        mock_s3.return_value = "https://my-community-s3.s3.ap-northeast-2.amazonaws.com/posts/test.jpg"
        from utils.upload import save_file
        result = await save_file(mock_file, folder="posts")
        mock_s3.assert_called_once_with(mock_file, folder="posts")
        assert "s3" in result


@pytest.mark.asyncio
async def test_delete_image_dispatches_to_local(monkeypatch):
    """STORAGE_TYPE=local should call delete_file."""
    monkeypatch.setattr("utils.upload.settings.STORAGE_TYPE", "local")

    with patch("utils.upload.delete_file") as mock_local:
        mock_local.return_value = True
        from utils.upload import delete_image
        result = await delete_image("/uploads/posts/test.jpg")
        mock_local.assert_called_once_with("/uploads/posts/test.jpg")
        assert result is True


@pytest.mark.asyncio
async def test_delete_image_dispatches_to_s3(monkeypatch):
    """STORAGE_TYPE=s3 should call delete_from_s3."""
    monkeypatch.setattr("utils.upload.settings.STORAGE_TYPE", "s3")

    with patch("utils.upload.delete_from_s3", new_callable=AsyncMock) as mock_s3:
        mock_s3.return_value = True
        from utils.upload import delete_image
        result = await delete_image("https://my-community-s3.s3.ap-northeast-2.amazonaws.com/posts/test.jpg")
        mock_s3.assert_called_once()
        assert result is True
