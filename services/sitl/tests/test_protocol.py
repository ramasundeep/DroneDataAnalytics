import json

import pytest

from cdsim_sitl_bridge.protocol import (
    MAGIC_16,
    FrameTracker,
    PhysicsState,
    ProtocolError,
    build_servo_packet,
    encode_state,
    parse_servo_packet,
)


def test_roundtrip_16_and_32() -> None:
    for n in (16, 32):
        pwm = [1000 + i * 10 for i in range(n)]
        pkt = parse_servo_packet(build_servo_packet(400, 7, pwm))
        assert pkt.pwm == tuple(pwm) and pkt.frame_rate == 400 and pkt.frame_count == 7


def test_wire_layout_is_little_endian() -> None:
    raw = build_servo_packet(400, 1, [1500] * 16)
    assert raw[:2] == MAGIC_16.to_bytes(2, "little")
    assert len(raw) == 8 + 32


@pytest.mark.parametrize("raw", [b"", b"\x00" * 7, b"\x01\x00" + b"\x00" * 38])
def test_rejects_bad_packets(raw: bytes) -> None:
    with pytest.raises(ProtocolError):
        parse_servo_packet(raw)


def test_wrong_length_rejected() -> None:
    with pytest.raises(ProtocolError):
        parse_servo_packet(build_servo_packet(400, 1, [1500] * 16) + b"\x00\x00")


def test_normalised() -> None:
    pkt = parse_servo_packet(build_servo_packet(400, 1, [1000, 1500, 2000, 2500] + [0] * 12))
    assert pkt.normalised()[:5] == [0.0, 0.5, 1.0, 1.0, 0.0]


def test_encode_state_framing_and_timestamp() -> None:
    raw = encode_state(
        PhysicsState(
            sim_time_us=2_500,
            gyro_radps=(0, 0, 0),
            accel_body_mps2=(0, 0, -9.80665),
            position_ned_m=(0, 0, 0),
            velocity_ned_mps=(0, 0, 0),
            quaternion_wxyz=(1, 0, 0, 0),
            extras={"rng_1": 0.1},
        )
    )
    assert raw.startswith(b"\n") and raw.endswith(b"\n")
    doc = json.loads(raw)
    assert doc["timestamp"] == 0.0025
    assert doc["imu"]["accel_body"][2] == pytest.approx(-9.80665)
    assert doc["rng_1"] == 0.1


def test_frame_tracker() -> None:
    t = FrameTracker()
    assert [t.observe(c) for c in (1, 2, 2, 5, 1)] == [True, True, False, True, True]
    assert (t.duplicates, t.lost, t.resets) == (1, 2, 1)
