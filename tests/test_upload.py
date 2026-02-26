"""Unit tests for storage dispatcher (utils/upload.py)."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_save_file_dispatches_to_local():
    """save_file should call save_uploaded_file."""
    mock_file = MagicMock()
    with patch("utils.upload.save_uploaded_file", new_callable=AsyncMock) as mock_local:
        mock_local.return_value = "/uploads/posts/test.jpg"
        from utils.upload import save_file
        result = await save_file(mock_file, folder="posts")
        mock_local.assert_called_once_with(mock_file, folder="posts")
        assert result == "/uploads/posts/test.jpg"


@pytest.mark.asyncio
async def test_delete_image_dispatches_to_local():
    """delete_image should call delete_file."""
    with patch("utils.upload.delete_file") as mock_local:
        mock_local.return_value = True
        from utils.upload import delete_image
        result = await delete_image("/uploads/posts/test.jpg")
        mock_local.assert_called_once_with("/uploads/posts/test.jpg")
        assert result is True
