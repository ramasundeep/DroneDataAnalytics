import importlib
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from cdsim_common.events import (
    Event,
    EventBatch,
    EventFamily,
    Header,
    Outcome,
    Stimulus,
    StimulusKind,
)
from cdsim_common.paths import repo_root


def _header(t: int = 1000, seq: int = 0) -> Header:
    return Header(sim_time_us=t, session_id="s1", actor_id="trainee-1", seq=seq)


def test_stimulus_event_roundtrip() -> None:
    ev = Event(
        header=_header(),
        stimulus=Stimulus(kind=StimulusKind.KIND_SYSTEM_FAILURE, code="motor_m2_out"),
    )
    assert ev.family is EventFamily.STIMULUS
    assert ev.code == "motor_m2_out"
    again = Event.model_validate(ev.to_proto_json())
    assert again == ev


def test_payload_is_exactly_one() -> None:
    with pytest.raises(ValidationError):
        Event(header=_header())
    with pytest.raises(ValidationError):
        Event.model_validate(
            {
                "header": _header().model_dump(),
                "stimulus": {"kind": "KIND_ALARM"},
                "annotation": {"text": "x"},
            }
        )


def test_outcome_oneof() -> None:
    with pytest.raises(ValidationError):
        Outcome()
    ev = Event.model_validate(
        {
            "header": {"simTimeUs": 5, "sessionId": "s", "actorId": "a"},
            "outcome": {"landingTouchdown": {"radialErrorM": 0.3, "padId": "pad_alpha"}},
        }
    )
    assert ev.code == "landing_touchdown"


def test_negative_sim_time_rejected() -> None:
    with pytest.raises(ValidationError):
        Header(sim_time_us=-1, session_id="s", actor_id="a")


def test_sort_key_orders_by_sim_time_then_seq() -> None:
    evs = [
        Event(header=_header(t=10, seq=2), annotation={"text": "c"}),  # type: ignore[arg-type]
        Event(header=_header(t=10, seq=1), annotation={"text": "b"}),  # type: ignore[arg-type]
        Event(header=_header(t=5, seq=9), annotation={"text": "a"}),  # type: ignore[arg-type]
    ]
    texts = [e.annotation.text for e in sorted(evs, key=Event.sort_key) if e.annotation]
    assert texts == ["a", "b", "c"]


def _compile_protos(out: Path) -> Any:
    root = repo_root()
    assert root is not None
    pytest.importorskip("grpc_tools")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "grpc_tools.protoc",
            f"-I{root / 'schemas'}",
            f"--python_out={out}",
            *[str(p) for p in sorted((root / "schemas").glob("*.proto"))],
        ],
        check=True,
    )
    sys.path.insert(0, str(out))
    try:
        return importlib.import_module("events_pb2")
    finally:
        sys.path.remove(str(out))


def test_pydantic_json_parses_as_protobuf(tmp_path: Path) -> None:
    """The Pydantic JSON must be valid proto3 JSON for cdsim.v1.Event."""
    events_pb2 = _compile_protos(tmp_path)
    from google.protobuf import json_format

    ev = Event(
        header=_header(t=123_456, seq=3),
        stimulus=Stimulus(
            kind=StimulusKind.KIND_INSTRUCTOR_INJECT,
            code="gps_loss",
            expected_response_codes=["mode.LAND"],
            params={"severity": "high"},
        ),
    )
    msg = json_format.ParseDict(ev.to_proto_json(), events_pb2.Event())
    assert msg.header.sim_time_us == 123_456
    assert msg.stimulus.code == "gps_loss"
    assert msg.WhichOneof("payload") == "stimulus"
    # And back: proto JSON → pydantic
    back = Event.model_validate(json_format.MessageToDict(msg))
    assert back == ev


def test_batch() -> None:
    b = EventBatch.model_validate({"events": []})
    assert b.events == []
