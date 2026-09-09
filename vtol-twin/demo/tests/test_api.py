import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from demo import app as demo_app


@pytest.fixture()
def client():
    demo_app.ctl.speed = 200.0
    with TestClient(demo_app.app) as c:
        c.post("/api/reset")
        yield c


def wait_for_sortie_end(client, timeout=60):
    import time
    deadline = time.time() + timeout
    while time.time() < deadline:
        if client.get("/api/state").json()["sortie"] is None:
            return
        time.sleep(0.2)
    raise AssertionError("sortie did not finish")


def test_health_and_state(client):
    assert client.get("/health").json()["status"] == "ok"
    s = client.get("/api/state").json()
    assert s["thing"]["thingId"] == "vtol.fleet:VTOL-1" and s["sortie"] is None
    assert "vibration" in s["degradations"]


def test_start_conflict_and_validation(client):
    assert client.post("/api/sortie/start", json={"degradation": "bogus"}).status_code == 422
    r = client.post("/api/sortie/start", json={"degradation": "none", "cruiseSeconds": 30})
    assert r.status_code == 200 and r.json()["phase"] == "preflight"
    assert client.post("/api/sortie/start", json={}).status_code == 409
    client.post("/api/sortie/abort")
    assert client.get("/api/state").json()["sortie"] is None


def test_degraded_sortie_end_to_end_via_api(client):
    r = client.post("/api/sortie/start", json={"degradation": "servo", "severity": 1.5, "cruiseSeconds": 30})
    assert r.status_code == 200
    wait_for_sortie_end(client)
    state = client.get("/api/state").json()
    assert state["sorties"][-1]["degradation"] == "servo"
    wos = client.get("/api/workorders", params={"status": "open"}).json()
    assert [w["component"] for w in wos] == ["servo3"]
    assert state["thing"]["features"]["health"]["properties"]["aircraft"]["releaseStatus"] != "serviceable"
    r = client.post(f"/api/workorders/{wos[0]['id']}/signoff",
                    json={"action": "repaired", "signedOffBy": "tech", "manHours": 2})
    assert r.status_code == 200 and r.json()["status"] == "closed"
    assert client.post(f"/api/workorders/{wos[0]['id']}/signoff", json={}).status_code == 409
    assert client.post("/api/workorders/WO-0099/signoff", json={}).status_code == 404
    rel = client.get("/api/state").json()["thing"]["features"]["health"]["properties"]["aircraft"]["releaseStatus"]
    assert rel == "serviceable"


def test_broadcast_feeds_subscribers_and_drops_oldest_when_full():
    async def run():
        q = asyncio.Queue(maxsize=2)
        demo_app.ctl.subscribers.append(q)
        try:
            for kind in ("a", "b", "c"):
                await demo_app.ctl.broadcast(kind)
            kinds = [json.loads(q.get_nowait())["kind"] for _ in range(2)]
        finally:
            demo_app.ctl.subscribers.remove(q)
        return kinds
    assert asyncio.run(run()) == ["b", "c"]
