"""Unit tests for s3_utils helper functions.

Tests build_image_url and extract_s3_key across all URL format branches:
- CloudFront URL (domain configured)
- CloudFront URL (domain not configured — rollback scenario)
- Direct S3 URL
- Legacy local path (pre-S3 records)
"""

import pytest
from utils.s3_utils import build_image_url, extract_s3_key


BUCKET = "my-community-s3-fe"
REGION = "ap-southeast-2"
CF_DOMAIN = "d1waeja4u5zbzs.cloudfront.net"
S3_KEY = "profiles/abc123.jpg"


# ---------------------------------------------------------------------------
# build_image_url
# ---------------------------------------------------------------------------


class TestBuildImageUrl:
    def test_returns_cloudfront_url_when_domain_is_set(self, monkeypatch):
        monkeypatch.setattr("utils.s3_utils.settings.CLOUDFRONT_DOMAIN", CF_DOMAIN)
        monkeypatch.setattr("utils.s3_utils.settings.AWS_S3_BUCKET_NAME", BUCKET)
        monkeypatch.setattr("utils.s3_utils.settings.AWS_REGION", REGION)

        url = build_image_url(S3_KEY)
        assert url == f"https://{CF_DOMAIN}/{S3_KEY}"

    def test_returns_s3_url_when_domain_is_empty(self, monkeypatch):
        monkeypatch.setattr("utils.s3_utils.settings.CLOUDFRONT_DOMAIN", "")
        monkeypatch.setattr("utils.s3_utils.settings.AWS_S3_BUCKET_NAME", BUCKET)
        monkeypatch.setattr("utils.s3_utils.settings.AWS_REGION", REGION)

        url = build_image_url(S3_KEY)
        assert url == f"https://{BUCKET}.s3.{REGION}.amazonaws.com/{S3_KEY}"

    def test_strips_trailing_slash_from_cloudfront_domain(self, monkeypatch):
        monkeypatch.setattr("utils.s3_utils.settings.CLOUDFRONT_DOMAIN", CF_DOMAIN + "/")
        monkeypatch.setattr("utils.s3_utils.settings.AWS_S3_BUCKET_NAME", BUCKET)
        monkeypatch.setattr("utils.s3_utils.settings.AWS_REGION", REGION)

        url = build_image_url(S3_KEY)
        assert "//" not in url.replace("https://", "")
        assert url == f"https://{CF_DOMAIN}/{S3_KEY}"


# ---------------------------------------------------------------------------
# extract_s3_key
# ---------------------------------------------------------------------------


class TestExtractS3Key:
    def test_cloudfront_url_with_domain_configured(self, monkeypatch):
        monkeypatch.setattr("utils.s3_utils.settings.CLOUDFRONT_DOMAIN", CF_DOMAIN)
        monkeypatch.setattr("utils.s3_utils.settings.AWS_REGION", REGION)

        url = f"https://{CF_DOMAIN}/{S3_KEY}"
        assert extract_s3_key(url) == S3_KEY

    def test_cloudfront_url_with_trailing_slash_on_domain_setting(self, monkeypatch):
        """CLOUDFRONT_DOMAIN set with trailing slash must still parse correctly."""
        monkeypatch.setattr("utils.s3_utils.settings.CLOUDFRONT_DOMAIN", CF_DOMAIN + "/")
        monkeypatch.setattr("utils.s3_utils.settings.AWS_REGION", REGION)

        url = f"https://{CF_DOMAIN}/{S3_KEY}"
        assert extract_s3_key(url) == S3_KEY

    def test_cloudfront_url_without_domain_configured(self, monkeypatch):
        """Handles CloudFront URLs stored in DB after CLOUDFRONT_DOMAIN is cleared (rollback)."""
        monkeypatch.setattr("utils.s3_utils.settings.CLOUDFRONT_DOMAIN", "")
        monkeypatch.setattr("utils.s3_utils.settings.AWS_REGION", REGION)

        url = f"https://{CF_DOMAIN}/{S3_KEY}"
        assert extract_s3_key(url) == S3_KEY

    def test_direct_s3_url(self, monkeypatch):
        monkeypatch.setattr("utils.s3_utils.settings.CLOUDFRONT_DOMAIN", "")
        monkeypatch.setattr("utils.s3_utils.settings.AWS_REGION", REGION)
        monkeypatch.setattr("utils.s3_utils.settings.AWS_S3_BUCKET_NAME", BUCKET)

        url = f"https://{BUCKET}.s3.{REGION}.amazonaws.com/{S3_KEY}"
        assert extract_s3_key(url) == S3_KEY

    def test_direct_s3_url_with_cloudfront_domain_configured(self, monkeypatch):
        """Legacy S3 URLs in DB still parsed correctly after CloudFront is enabled."""
        monkeypatch.setattr("utils.s3_utils.settings.CLOUDFRONT_DOMAIN", CF_DOMAIN)
        monkeypatch.setattr("utils.s3_utils.settings.AWS_REGION", REGION)

        url = f"https://{BUCKET}.s3.{REGION}.amazonaws.com/{S3_KEY}"
        assert extract_s3_key(url) == S3_KEY

    def test_legacy_local_path(self, monkeypatch):
        """Pre-S3 records stored as /assets/posts/image.jpg."""
        monkeypatch.setattr("utils.s3_utils.settings.CLOUDFRONT_DOMAIN", "")
        monkeypatch.setattr("utils.s3_utils.settings.AWS_REGION", REGION)

        assert extract_s3_key("/assets/posts/image.jpg") == "assets/posts/image.jpg"

    def test_legacy_local_path_with_cloudfront_configured(self, monkeypatch):
        monkeypatch.setattr("utils.s3_utils.settings.CLOUDFRONT_DOMAIN", CF_DOMAIN)
        monkeypatch.setattr("utils.s3_utils.settings.AWS_REGION", REGION)

        assert extract_s3_key("/assets/profiles/avatar.png") == "assets/profiles/avatar.png"
