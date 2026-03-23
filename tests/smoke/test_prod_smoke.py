# tests/smoke/test_prod_smoke.py
"""Prod 스모크 테스트 — 배포 후 핵심 엔드포인트 자동 검증.

실행: pytest tests/smoke/ --base-url=https://api.my-community.shop --no-cov -v
"""

import socket
import ssl

import pytest

pytestmark = pytest.mark.smoke

# 엔드포인트별 기대값을 테이블로 관리하여 DRY 유지
_API_ENDPOINTS = [
    ("/health", 200, {"status": "ok", "database": "connected"}),
    ("/v1/posts/", 200, None),
    ("/v1/categories/", 200, None),
]


@pytest.mark.parametrize("path,expected_status,expected_body", _API_ENDPOINTS, ids=[e[0] for e in _API_ENDPOINTS])
def test_api_endpoint(http, api_url, path, expected_status, expected_body):
    """API 엔드포인트 접근 가능 + 응답 구조 검증"""
    resp = http.get(f"{api_url}{path}")
    assert resp.status_code == expected_status, f"{path}: {resp.status_code}"
    if expected_body:
        body = resp.json()
        for key, val in expected_body.items():
            assert body.get(key) == val, f"{path}: {key}={body.get(key)}, expected={val}"


def test_frontend_and_tls(http, fe_url, api_url):
    """프론트엔드 접근 + TLS 인증서 유효성을 한 번에 검증"""
    resp = http.get(fe_url)
    assert resp.status_code == 200
    assert "html" in resp.headers.get("content-type", "").lower()

    if not api_url.startswith("https"):
        return
    hostname = api_url.replace("https://", "").split("/")[0]
    ctx = ssl.create_default_context()
    with ctx.wrap_socket(
        socket.create_connection((hostname, 443), timeout=5),
        server_hostname=hostname,
    ) as sock:
        cert = sock.getpeercert()
        assert cert is not None
        san = [entry[1] for entry in cert.get("subjectAltName", [])]
        assert any(hostname in s for s in san), f"{hostname} not in SAN: {san}"
