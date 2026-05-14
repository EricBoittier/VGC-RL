from __future__ import annotations

import os

import httpx
import pytest

from vgc_rl.oracle_client import OracleClient


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "oracle: requires a reachable oracle HTTP server (ORACLE_URL or default 127.0.0.1:8765)")


@pytest.fixture
def oracle_client_or_skip() -> OracleClient:
    base = (os.environ.get("ORACLE_URL") or "http://127.0.0.1:8765").rstrip("/")

    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(f"{base}/health")
            response.raise_for_status()
    except Exception:
        pytest.skip(f"Oracle unreachable at {base}")

    return OracleClient(base_url=base)
