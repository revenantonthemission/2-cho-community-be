# tests/test_ws_app.py
import pytest

pytest.importorskip("redis", reason="redis는 K8s optional dependency")

from fastapi.testclient import TestClient

from ws_app import app


def test_ws_app_health():
    """ws_app health 엔드포인트 테스트"""
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["service"] == "websocket"
