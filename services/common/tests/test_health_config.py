import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cdsim_common.config import Settings
from cdsim_common.health import health_router


async def _ok() -> None:
    return None


async def _broken() -> None:
    raise ConnectionError("db unreachable")


def test_ready_ok() -> None:
    app = FastAPI()
    app.include_router(health_router("svc", "1.0", {"a": _ok}))
    c = TestClient(app)
    assert c.get("/health").json()["status"] == "ok"
    r = c.get("/ready")
    assert r.status_code == 200 and r.json()["checks"]["a"]["ok"]


def test_ready_degraded_returns_503() -> None:
    app = FastAPI()
    app.include_router(health_router("svc", "1.0", {"a": _ok, "db": _broken}))
    r = TestClient(app).get("/ready")
    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "degraded"
    assert "db unreachable" in body["checks"]["db"]["detail"]


def test_service_url_map(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CDSIM_SERVICE_URLS", "api=http://api:8000/, recorder=http://rec:8001")
    s = Settings()
    assert s.service_url_map() == {"api": "http://api:8000", "recorder": "http://rec:8001"}
    assert "cdsim-dev-only" not in repr(s)  # secrets are masked


def test_bad_service_url_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CDSIM_SERVICE_URLS", "api")
    with pytest.raises(ValueError):
        Settings().service_url_map()
