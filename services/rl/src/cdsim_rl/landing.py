"""Precision-landing task: observation/action spaces, reward, curriculum.

Everything here is pure and deterministic so it can be unit-tested without a
simulator. The environment that drives UE5 over gRPC (``env.py``) uses these.

Reward (per step, shaped; weights in ``RewardWeights``)::

    r = - w_radial * radial_error_m
        - w_descent * max(0, descent_rate_mps - safe_descent_mps)
        - w_attitude * tilt_rad
        - w_time
    terminal: + success_bonus if touchdown within pad radius, gently, level
              - crash_penalty on collision / hard touchdown / leaving the arena

Design rationale and tuning notes: docs/08_AUTONOMY_TRAINING.md.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class RewardWeights:
    radial: float = 1.0
    descent: float = 2.0
    attitude: float = 0.5
    time: float = 0.01
    success_bonus: float = 100.0
    crash_penalty: float = 100.0
    safe_descent_mps: float = 0.7


@dataclass(frozen=True)
class LandingObs:
    """Low-dimensional part of the observation (the camera frame is separate)."""

    rel_pad_enu_m: tuple[float, float, float]  # pad position relative to vehicle
    vel_enu_mps: tuple[float, float, float]
    roll_rad: float
    pitch_rad: float
    yaw_rate_radps: float
    pad_visible: bool


@dataclass(frozen=True)
class Touchdown:
    radial_error_m: float
    vertical_speed_mps: float
    tilt_deg: float


class Termination(str, Enum):
    NONE = "none"
    SUCCESS = "success"
    HARD_LANDING = "hard_landing"
    OFF_PAD = "off_pad"
    CRASH = "crash"
    TIMEOUT = "timeout"


# Action: velocity setpoint (ENU m/s) + yaw rate, clipped to these limits and
# sent via MAVLink SET_POSITION_TARGET_LOCAL_NED in GUIDED mode.
ACTION_LIMITS = (2.0, 2.0, 1.5, 0.5)  # vx, vy, vz, yaw_rate


def clip_action(action: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    vx, vy, vz, wz = (max(-lim, min(lim, a)) for a, lim in zip(action, ACTION_LIMITS, strict=True))
    return (vx, vy, vz, wz)


def step_reward(obs: LandingObs, w: RewardWeights = RewardWeights()) -> float:
    dx, dy, _ = obs.rel_pad_enu_m
    radial = math.hypot(dx, dy)
    descent_rate = max(0.0, -obs.vel_enu_mps[2])
    tilt = math.hypot(obs.roll_rad, obs.pitch_rad)
    return (
        -w.radial * radial
        - w.descent * max(0.0, descent_rate - w.safe_descent_mps)
        - w.attitude * tilt
        - w.time
    )


def classify_touchdown(
    td: Touchdown, pad_radius_m: float, max_vspeed_mps: float = 1.0, max_tilt_deg: float = 10.0
) -> Termination:
    if td.vertical_speed_mps > max_vspeed_mps or td.tilt_deg > max_tilt_deg:
        return Termination.HARD_LANDING
    if td.radial_error_m > pad_radius_m:
        return Termination.OFF_PAD
    return Termination.SUCCESS


def terminal_reward(term: Termination, w: RewardWeights = RewardWeights()) -> float:
    if term is Termination.SUCCESS:
        return w.success_bonus
    if term in (Termination.CRASH, Termination.HARD_LANDING):
        return -w.crash_penalty
    if term is Termination.OFF_PAD:
        return -0.25 * w.crash_penalty
    return 0.0


@dataclass(frozen=True)
class CurriculumStage:
    name: str
    wind_mps: float
    gust_mps: float
    pad_motion: str  # "static" | "linear" | "circular"
    pad_speed_mps: float
    promote_at_success_rate: float


CURRICULUM: tuple[CurriculumStage, ...] = (
    CurriculumStage("static_calm", 0.0, 0.0, "static", 0.0, 0.9),
    CurriculumStage("static_wind", 4.0, 2.0, "static", 0.0, 0.85),
    CurriculumStage("moving_linear", 3.0, 1.0, "linear", 1.0, 0.8),
    CurriculumStage("moving_circular_wind", 5.0, 3.0, "circular", 1.5, 0.75),
)


def next_stage(current: int, success_rate: float) -> int:
    """Advance one stage when the rolling success rate clears the bar."""
    stage = CURRICULUM[current]
    if success_rate >= stage.promote_at_success_rate and current + 1 < len(CURRICULUM):
        return current + 1
    return current
