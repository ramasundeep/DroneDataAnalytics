"""Integration tests against a running `make dev` stack (pytest -m integration)."""

import os
import uuid

import httpx
import pytest

pytestmark = pytest.mark.integration

API = f"http://127.0.0.1:{os.environ.get('CDSIM_API_PORT', '8000')}"
RECORDER = f"http://127.0.0.1:{os.environ.get('CDSIM_RECORDER_PORT', '8001')}"


def test_system_health_all_ok() -> None:
    body = httpx.get(f"{API}/v1/system/health", timeout=10).json()
    assert body["status"] == "ok", body


def test_event_roundtrip_is_sim_time_ordered() -> None:
    sid = f"it-{uuid.uuid4()}"

    def ev(t: int, code: str) -> dict[str, object]:
        return {
            "header": {"simTimeUs": t, "sessionId": sid, "actorId": "it"},
            "stimulus": {"kind": "KIND_ALARM", "code": code},
        }

    r = httpx.post(f"{RECORDER}/v1/events", json={"events": [ev(300, "c"), ev(100, "a")]})
    assert r.json()["stored"] == 2
    got = httpx.get(f"{RECORDER}/v1/sessions/{sid}/events").json()
    assert [e["stimulus"]["code"] for e in got] == ["a", "c"]
