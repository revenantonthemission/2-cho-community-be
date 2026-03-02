"""이미지 URL 보안 검증 공통 헬퍼.

게시글 이미지, 프로필 이미지 등에서 공유하는 검증 로직을 정의합니다.
외부 URL → SSRF/Content Injection 방지를 위해 자체 업로드 경로만 허용합니다.
"""

_ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
_ALLOWED_PROFILE_PREFIXES = ("/uploads/", "/assets/profiles/")


def validate_upload_image_url(v: str | None) -> str | None:
    """업로드된 이미지 URL을 검증합니다 (게시글 이미지용).

    /uploads/ 프리픽스와 허용 확장자를 강제합니다.
    """
    if v is None:
        return None
    if ".." in v:
        raise ValueError("이미지 URL에 잘못된 경로 문자가 포함되어 있습니다.")
    if not v.startswith("/uploads/"):
        raise ValueError("이미지 URL은 업로드된 파일 경로만 허용됩니다.")
    if not any(v.lower().endswith(ext) for ext in _ALLOWED_IMAGE_EXTENSIONS):
        raise ValueError(
            "이미지는 .jpg, .jpeg, .png, .gif, .webp 형식만 허용됩니다."
        )
    return v


def validate_upload_image_url_list(
    v: list[str] | None, max_count: int = 5
) -> list[str] | None:
    """업로드된 이미지 URL 리스트를 검증합니다 (다중 이미지용).

    각 URL에 대해 validate_upload_image_url을 적용합니다.
    """
    if v is None:
        return None
    if len(v) > max_count:
        raise ValueError(f"이미지는 최대 {max_count}개까지만 업로드할 수 있습니다.")
    validated = [validate_upload_image_url(url) for url in v]
    # validate_upload_image_url은 None 입력에만 None을 반환하며,
    # 리스트 원소는 str이므로 결과도 str 리스트임
    return validated  # type: ignore[return-value]


def validate_profile_image_url(v: str | dict | None) -> str | None:
    """프로필 이미지 URL을 검증합니다.

    /uploads/ 또는 /assets/profiles/ 프리픽스와 허용 확장자를 강제합니다.
    기본 프로필 이미지(/assets/profiles/default_profile.jpg)도 허용합니다.
    """
    if v is None:
        return None
    if isinstance(v, dict):
        v = v.get("url")
        if v is None:
            return None
    if ".." in v:
        raise ValueError("프로필 이미지 URL에 잘못된 경로 문자가 포함되어 있습니다.")
    if not any(v.startswith(prefix) for prefix in _ALLOWED_PROFILE_PREFIXES):
        raise ValueError("프로필 이미지는 업로드된 파일 경로만 허용됩니다.")
    allowed_extensions = {".jpg", ".jpeg", ".png"}
    if not any(v.lower().endswith(ext) for ext in allowed_extensions):
        raise ValueError("프로필 이미지는 .jpg, .jpeg, .png 형식만 허용됩니다.")
    return v
