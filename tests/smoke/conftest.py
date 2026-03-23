import os

import httpx
import pytest


def pytest_addoption(parser):
    parser.addoption("--base-url", default=os.getenv("BASE_URL", "http://127.0.0.1:8000"))
    parser.addoption("--fe-url", default=os.getenv("FE_URL", "https://my-community.shop"))


@pytest.fixture(scope="module")
def api_url(request):
    return request.config.getoption("--base-url")


@pytest.fixture(scope="module")
def fe_url(request):
    return request.config.getoption("--fe-url")


@pytest.fixture(scope="module")
def http():
    with httpx.Client(timeout=10, verify=False, follow_redirects=True) as client:
        yield client
