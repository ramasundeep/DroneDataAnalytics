import httpx
import pytest
from fastapi.testclient import TestClient

from cdsim_api.main import create_app
from cdsim_api.system import probe_all
from cdsim_common.config import Settings


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(Settings(), with_infra_checks=False))


def test_health_and_ready(client: TestClient) -> None:
    assert client.get("/health").json()["service"] == "api"
    ready = client.get("/ready")
    assert ready.status_code == 200, ready.json()
    assert ready.json()["checks"]["manifests"]["ok"]


def test_catalogue(client: TestClient) -> None:
    platforms = client.get("/v1/platforms").json()
    assert {"id": "cdpl_quad_01", "class": "multirotor"}.items() <= platforms[0].items()
    areas = {a["id"]: a for a in client.get("/v1/areas").json()}
    assert areas["hyd_demo_01"]["landing_pads"] == 3
    scenarios = client.get("/v1/scenarios").json()
    assert any(s["id"] == "sitl_core_loop" for s in scenarios)
    assert client.get("/v1/platforms/cdpl_quad_01").json()["identity"]["id"] == "cdpl_quad_01"
    assert client.get("/v1/areas/nope").status_code == 404
    assert client.get("/v1/rubrics").status_code == 200


def test_later_phase_routes_are_explicit_501(client: TestClient) -> None:
    r = client.get("/v1/sessions/abc/score")
    assert r.status_code == 501
    assert "Phase 3" in r.json()["detail"]


def test_system_health_empty(client: TestClient) -> None:
    body = client.get("/v1/system/health").json()
    assert body == {"status": "ok", "services": []}


async def test_probe_all_classifies() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        host = req.url.host
        if host == "good":
            return httpx.Response(200, json={"status": "ok"})
        if host == "bad":
            return httpx.Response(
                503, json={"status": "degraded", "checks": {"postgres": {"ok": False}}}
            )
        raise httpx.ConnectError("refused")

    result = await probe_all(
        {"a": "http://good", "b": "http://bad", "c": "http://down"},
        transport=httpx.MockTransport(handler),
    )
    by = {s.name: s for s in result.services}
    assert result.status == "degraded"
    assert by["a"].status == "ok"
    assert by["b"].status == "degraded" and "postgres" in by["b"].detail
    assert by["c"].status == "unreachable"
