"""Pydantic models mirroring ``schemas/events.proto`` and ``common.proto``.

The JSON shape produced by these models is the canonical protobuf JSON mapping
of ``cdsim.v1.Event`` (oneof members appear as a single key, enums as their
names), so the same document can be parsed by generated protobuf code. A unit
test (tests/test_events.py) compiles the .proto files and checks that field
names stay in sync — change both together.

Semantics of each event family: docs/06_ASSESSMENT_ENGINE.md.
"""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


# --------------------------------------------------------------------- common


class Source(str, Enum):
    SOURCE_UNSPECIFIED = "SOURCE_UNSPECIFIED"
    SOURCE_SIM_CLIENT = "SOURCE_SIM_CLIENT"
    SOURCE_SIM_SERVER = "SOURCE_SIM_SERVER"
    SOURCE_AUTOPILOT = "SOURCE_AUTOPILOT"
    SOURCE_INSTRUCTOR = "SOURCE_INSTRUCTOR"
    SOURCE_ASSESSMENT = "SOURCE_ASSESSMENT"
    SOURCE_SCENARIO = "SOURCE_SCENARIO"
    SOURCE_RL = "SOURCE_RL"
    SOURCE_AUDIO = "SOURCE_AUDIO"


class Header(_Model):
    sim_time_us: int = Field(ge=0, alias="simTimeUs")
    wall_time_us: int = Field(default=0, ge=0, alias="wallTimeUs")
    session_id: str = Field(min_length=1, alias="sessionId")
    actor_id: str = Field(min_length=1, alias="actorId")
    source: Source = Source.SOURCE_UNSPECIFIED
    seq: int = Field(default=0, ge=0)


class Vec3(_Model):
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


class GeoPoint(_Model):
    lat_deg: float = Field(default=0.0, ge=-90, le=90, alias="latDeg")
    lon_deg: float = Field(default=0.0, ge=-180, le=180, alias="lonDeg")
    alt_msl_m: float = Field(default=0.0, alias="altMslM")


# ------------------------------------------------------------------- stimulus


class StimulusKind(str, Enum):
    KIND_UNSPECIFIED = "KIND_UNSPECIFIED"
    KIND_INSTRUCTOR_INJECT = "KIND_INSTRUCTOR_INJECT"
    KIND_SYSTEM_FAILURE = "KIND_SYSTEM_FAILURE"
    KIND_TARGET_APPEARANCE = "KIND_TARGET_APPEARANCE"
    KIND_ALARM = "KIND_ALARM"


class Stimulus(_Model):
    kind: StimulusKind
    code: str = ""
    description: str = ""
    broadcast_id: str = Field(default="", alias="broadcastId")
    expected_response_codes: list[str] = Field(
        default_factory=list, alias="expectedResponseCodes"
    )
    params: dict[str, str] = Field(default_factory=dict)


# ------------------------------------------------------------------- response


class ResponseKind(str, Enum):
    KIND_UNSPECIFIED = "KIND_UNSPECIFIED"
    KIND_CONTROL_INPUT = "KIND_CONTROL_INPUT"
    KIND_MODE_CHANGE = "KIND_MODE_CHANGE"
    KIND_VOICE_COMMAND = "KIND_VOICE_COMMAND"
    KIND_MENU_ACTION = "KIND_MENU_ACTION"


class Response(_Model):
    kind: ResponseKind
    code: str = ""
    description: str = ""
    magnitude: float = 0.0
    params: dict[str, str] = Field(default_factory=dict)


# -------------------------------------------------------------------- outcome


class LandingTouchdown(_Model):
    pad_id: str = Field(default="", alias="padId")
    radial_error_m: float = Field(ge=0, alias="radialErrorM")
    position_error_m: Vec3 = Field(default_factory=Vec3, alias="positionErrorM")
    velocity_mps: Vec3 = Field(default_factory=Vec3, alias="velocityMps")
    roll_deg: float = Field(default=0.0, alias="rollDeg")
    pitch_deg: float = Field(default=0.0, alias="pitchDeg")
    yaw_error_deg: float = Field(default=0.0, alias="yawErrorDeg")


class Collision(_Model):
    other_object_id: str = Field(default="", alias="otherObjectId")
    impact_speed_mps: float = Field(default=0.0, ge=0, alias="impactSpeedMps")
    location: GeoPoint = Field(default_factory=GeoPoint)


class GeofenceBreach(_Model):
    volume_id: str = Field(alias="volumeId")
    location: GeoPoint = Field(default_factory=GeoPoint)
    entered: bool = True


class ProcedureResult(str, Enum):
    RESULT_UNSPECIFIED = "RESULT_UNSPECIFIED"
    RESULT_STARTED = "RESULT_STARTED"
    RESULT_COMPLETED = "RESULT_COMPLETED"
    RESULT_FAILED = "RESULT_FAILED"
    RESULT_SKIPPED = "RESULT_SKIPPED"


class ProcedureStep(_Model):
    procedure_id: str = Field(alias="procedureId")
    step_id: str = Field(alias="stepId")
    result: ProcedureResult
    tool_id: str = Field(default="", alias="toolId")
    failure_reason: str = Field(default="", alias="failureReason")


class Outcome(_Model):
    """Exactly one of the detail fields is set (proto ``oneof detail``)."""

    landing_touchdown: LandingTouchdown | None = Field(default=None, alias="landingTouchdown")
    collision: Collision | None = None
    geofence_breach: GeofenceBreach | None = Field(default=None, alias="geofenceBreach")
    procedure_step: ProcedureStep | None = Field(default=None, alias="procedureStep")

    @model_validator(mode="after")
    def _exactly_one(self) -> Self:
        _require_exactly_one(
            self, ("landing_touchdown", "collision", "geofence_breach", "procedure_step")
        )
        return self


# ----------------------------------------------------------------- annotation


class Annotation(_Model):
    text: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------- event


class EventFamily(str, Enum):
    STIMULUS = "stimulus"
    RESPONSE = "response"
    OUTCOME = "outcome"
    ANNOTATION = "annotation"


_PAYLOAD_FIELDS = ("stimulus", "response", "outcome", "annotation")


class Event(_Model):
    """One session event. Exactly one payload field is set (proto ``oneof``)."""

    header: Header
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()), alias="eventId")
    related_event_id: str = Field(default="", alias="relatedEventId")
    stimulus: Stimulus | None = None
    response: Response | None = None
    outcome: Outcome | None = None
    annotation: Annotation | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> Self:
        _require_exactly_one(self, _PAYLOAD_FIELDS)
        return self

    @property
    def family(self) -> EventFamily:
        for name in _PAYLOAD_FIELDS:
            if getattr(self, name) is not None:
                return EventFamily(name)
        raise AssertionError("validated event has no payload")  # pragma: no cover

    @property
    def code(self) -> str:
        """Machine code of stimulus/response events; outcome kind otherwise."""
        if self.stimulus is not None:
            return self.stimulus.code
        if self.response is not None:
            return self.response.code
        if self.outcome is not None:
            for name in ("landing_touchdown", "collision", "geofence_breach", "procedure_step"):
                if getattr(self.outcome, name) is not None:
                    return name
        return ""

    def sort_key(self) -> tuple[int, int]:
        """Canonical ordering: (sim_time_us, seq). Used by recorder and replay."""
        return (self.header.sim_time_us, self.header.seq)

    def to_proto_json(self) -> dict[str, object]:
        """Serialise using protobuf JSON field names, omitting unset payloads."""
        return self.model_dump(mode="json", by_alias=True, exclude_none=True)


class EventBatch(_Model):
    events: list[Event] = Field(default_factory=list)


def _require_exactly_one(model: BaseModel, fields: tuple[str, ...]) -> None:
    present = [f for f in fields if getattr(model, f) is not None]
    if len(present) != 1:
        raise ValueError(f"exactly one of {fields} must be set, got {present or 'none'}")
