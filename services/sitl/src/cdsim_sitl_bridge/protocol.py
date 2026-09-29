"""ArduPilot SITL "JSON" physics backend wire format.

Flow (one exchange per physics step; UE5 owns physics — ADR 0003):

1. SITL (``arducopter --model JSON:<sim_host>``) sends a binary *servo packet*
   over UDP to ``<sim_host>:9002``.
2. The physics side steps the vehicle using the PWM outputs and replies from
   the same socket with one JSON *state* object, preceded and followed by a
   newline.

Servo packet (little-endian)::

    uint16 magic        18458 (16 channels) or 29569 (32 channels)
    uint16 frame_rate   SITL loop rate, Hz
    uint32 frame_count  increments each packet; repeats/gaps mean lost/duplicate
    uint16 pwm[16|32]   microseconds

State JSON (SI units; NED world frame, FRD body frame)::

    {"timestamp": s, "imu": {"gyro": [p,q,r], "accel_body": [x,y,z]},
     "position": [n,e,d], "attitude": [roll,pitch,yaw] | "quaternion": [w,x,y,z],
     "velocity": [vn,ve,vd], ...optional "rng_1", "airspeed", "windvane"...}

``timestamp`` is physics time in seconds and MUST advance monotonically; we
derive it from ``sim_time_us`` so SITL and the recorder share one clock.
"""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass, field

MAGIC_16 = 18458
MAGIC_32 = 29569
SITL_JSON_PORT = 9002

_HEADER = struct.Struct("<HHI")


class ProtocolError(ValueError):
    pass


@dataclass(frozen=True)
class ServoPacket:
    frame_rate: int
    frame_count: int
    pwm: tuple[int, ...]

    def normalised(self, pwm_min: int = 1000, pwm_max: int = 2000) -> list[float]:
        """PWM → [0, 1] commands, clamped. 0 PWM (output disabled) → 0."""
        span = pwm_max - pwm_min
        return [0.0 if p == 0 else min(1.0, max(0.0, (p - pwm_min) / span)) for p in self.pwm]


def parse_servo_packet(data: bytes) -> ServoPacket:
    if len(data) < _HEADER.size:
        raise ProtocolError(f"packet too short: {len(data)} bytes")
    magic, frame_rate, frame_count = _HEADER.unpack_from(data)
    if magic == MAGIC_16:
        n = 16
    elif magic == MAGIC_32:
        n = 32
    else:
        raise ProtocolError(f"bad magic {magic}")
    expected = _HEADER.size + 2 * n
    if len(data) != expected:
        raise ProtocolError(f"expected {expected} bytes for {n} channels, got {len(data)}")
    pwm = struct.unpack_from(f"<{n}H", data, _HEADER.size)
    return ServoPacket(frame_rate=frame_rate, frame_count=frame_count, pwm=tuple(pwm))


def build_servo_packet(frame_rate: int, frame_count: int, pwm: list[int]) -> bytes:
    """Inverse of parse_servo_packet (used by tests and the mock autopilot)."""
    if len(pwm) not in (16, 32):
        raise ProtocolError("pwm must have 16 or 32 channels")
    magic = MAGIC_16 if len(pwm) == 16 else MAGIC_32
    return _HEADER.pack(magic, frame_rate, frame_count & 0xFFFFFFFF) + struct.pack(
        f"<{len(pwm)}H", *pwm
    )


Vec3 = tuple[float, float, float]


@dataclass(frozen=True)
class PhysicsState:
    sim_time_us: int
    gyro_radps: Vec3
    accel_body_mps2: Vec3
    position_ned_m: Vec3
    velocity_ned_mps: Vec3
    quaternion_wxyz: tuple[float, float, float, float]
    extras: dict[str, float] = field(default_factory=dict)


def encode_state(state: PhysicsState) -> bytes:
    """State → newline-framed JSON bytes, as SITL expects."""
    doc: dict[str, object] = {
        "timestamp": state.sim_time_us / 1e6,
        "imu": {"gyro": list(state.gyro_radps), "accel_body": list(state.accel_body_mps2)},
        "position": list(state.position_ned_m),
        "quaternion": list(state.quaternion_wxyz),
        "velocity": list(state.velocity_ned_mps),
        **state.extras,
    }
    return b"\n" + json.dumps(doc, separators=(",", ":")).encode() + b"\n"


class FrameTracker:
    """Detects lost/duplicate/reset servo frames (SITL restart ⇒ count resets)."""

    def __init__(self) -> None:
        self.last: int | None = None
        self.lost = 0
        self.duplicates = 0
        self.resets = 0

    def observe(self, frame_count: int) -> bool:
        """Return True if this frame should be processed (not a duplicate)."""
        if self.last is None:
            self.last = frame_count
            return True
        if frame_count == self.last:
            self.duplicates += 1
            return False
        if frame_count < self.last:
            self.resets += 1
        elif frame_count > self.last + 1:
            self.lost += frame_count - self.last - 1
        self.last = frame_count
        return True
