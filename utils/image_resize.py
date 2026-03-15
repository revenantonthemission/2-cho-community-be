"""이미지 리사이징 유틸리티.

업로드된 이미지를 용도에 맞게 리사이징합니다.
GIF는 애니메이션 보존을 위해 리사이징하지 않습니다.
"""

import io
import logging

from PIL import Image

logger = logging.getLogger(__name__)

# 프로필 이미지: 최대 400x400
PROFILE_MAX_SIZE = (400, 400)
# 게시글 이미지: 최대 폭 1200px (높이는 비율 유지)
POST_MAX_WIDTH = 1200
# JPEG 품질
JPEG_QUALITY = 85


def resize_image(
    content: bytes,
    *,
    max_size: tuple[int, int] | None = None,
    max_width: int | None = None,
) -> bytes:
    """이미지를 리사이징하고 바이트를 반환합니다.

    Args:
        content: 원본 이미지 바이트.
        max_size: (width, height) 최대 크기 — 프로필용.
        max_width: 최대 폭 — 게시글용 (높이는 비율 유지).

    Returns:
        리사이징된 이미지 바이트. 이미 작으면 원본 반환.
    """
    try:
        img: Image.Image = Image.open(io.BytesIO(content))
    except Exception:
        logger.warning("이미지 열기 실패 — 원본 반환")
        return content

    # GIF 애니메이션 보존
    if img.format == "GIF":
        return content

    original_width, original_height = img.size
    needs_resize = False

    if max_size:
        if original_width > max_size[0] or original_height > max_size[1]:
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            needs_resize = True
    elif max_width:
        if original_width > max_width:
            ratio = max_width / original_width
            new_height = int(original_height * ratio)
            img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
            needs_resize = True

    if not needs_resize:
        return content

    # RGBA → RGB 변환 (JPEG 저장용)
    output_format = img.format or "JPEG"
    if output_format.upper() in ("JPEG", "JPG"):
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

    buf = io.BytesIO()
    save_kwargs: dict = {}
    if output_format.upper() in ("JPEG", "JPG"):
        save_kwargs["quality"] = JPEG_QUALITY
        save_kwargs["optimize"] = True
    elif output_format.upper() == "WEBP":
        save_kwargs["quality"] = JPEG_QUALITY

    img.save(buf, format=output_format, **save_kwargs)
    result = buf.getvalue()

    logger.info(
        "이미지 리사이징 완료: %dx%d → %dx%d (%.1fKB → %.1fKB)",
        original_width, original_height,
        img.size[0], img.size[1],
        len(content) / 1024, len(result) / 1024,
    )
    return result


def resize_for_profile(content: bytes) -> bytes:
    """프로필 이미지용 리사이징 (최대 400x400)."""
    return resize_image(content, max_size=PROFILE_MAX_SIZE)


def resize_for_post(content: bytes) -> bytes:
    """게시글 이미지용 리사이징 (최대 폭 1200px)."""
    return resize_image(content, max_width=POST_MAX_WIDTH)
