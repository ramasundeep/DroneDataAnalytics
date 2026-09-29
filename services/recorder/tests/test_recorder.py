from typing import Any

from fastapi.testclient import TestClient

from cdsim_common.config import Settings
from cdsim_recorder.main import create_app
from cdsim_recorder.store import InMemoryEventStore, ListPublisher, channel_for


def _ev(t: int, seq: int, eid: str, **payload: Any) -> dict[str, Any]:
    return {
        "eventId": eid,
        "header": {"simTimeUs": t, "sessionId": "S1", "actorId": "p1", "seq": seq},
        **payload,
    }


def _client() -> tuple[TestClient, ListPublisher]:
    pub = ListPublisher()
    app = create_app(Settings(), store=InMemoryEventStore(), publisher=pub)
    return TestClient(app), pub


def test_ingest_and_ordered_readback() -> None:
    c, pub = _client()
    batch = {
        "events": [
            _ev(2_000, 0, "e3", response={"kind": "KIND_CONTROL_INPUT", "code": "stick.pitch"}),
            _ev(1_000, 1, "e2", annotation={"text": "b"}),
            _ev(1_000, 0, "e1", stimulus={"kind": "KIND_SYSTEM_FAILURE", "code": "gps_loss"}),
        ]
    }
    r = c.post("/v1/events", json=batch)
    assert r.json() == {"received": 3, "stored": 3}
    ids = [e["eventId"] for e in c.get("/v1/sessions/S1/events").json()]
    assert ids == ["e1", "e2", "e3"]
    assert len(pub.published) == 3


def test_ingest_is_idempotent() -> None:
    c, _ = _client()
    batch = {"events": [_ev(1, 0, "dup", annotation={"text": "x"})]}
    c.post("/v1/events", json=batch)
    assert c.post("/v1/events", json=batch).json()["stored"] == 0


def test_filters() -> None:
    c, _ = _client()
    c.post(
        "/v1/events",
        json={
            "events": [
                _ev(10, 0, "a", stimulus={"kind": "KIND_ALARM"}),
                _ev(20, 0, "b", annotation={"text": "x"}),
                _ev(30, 0, "c", stimulus={"kind": "KIND_ALARM"}),
            ]
        },
    )
    got = c.get("/v1/sessions/S1/events", params={"family": "stimulus", "from_us": 15}).json()
    assert [e["eventId"] for e in got] == ["c"]


def test_invalid_event_rejected() -> None:
    c, _ = _client()
    r = c.post("/v1/events", json={"events": [_ev(-5, 0, "bad", annotation={"text": "x"})]})
    assert r.status_code == 422


def test_channel_name() -> None:
    assert channel_for("abc") == "cdsim.session.abc.events"
