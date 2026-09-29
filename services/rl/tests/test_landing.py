import pytest

from cdsim_rl.env import EnvConfig, PrecisionLandingEnv
from cdsim_rl.landing import (
    CURRICULUM,
    LandingObs,
    Termination,
    Touchdown,
    classify_touchdown,
    clip_action,
    next_stage,
    step_reward,
    terminal_reward,
)


def _obs(dx: float = 0, dy: float = 0, vz: float = 0, roll: float = 0) -> LandingObs:
    return LandingObs((dx, dy, -5.0), (0.0, 0.0, vz), roll, 0.0, 0.0, True)


def test_reward_prefers_centred_gentle_level() -> None:
    best = step_reward(_obs())
    assert step_reward(_obs(dx=3, dy=4)) < best
    assert step_reward(_obs(vz=-2.0)) < best
    assert step_reward(_obs(vz=-0.5)) == best  # within safe descent: no penalty
    assert step_reward(_obs(roll=0.3)) < best


def test_touchdown_classification() -> None:
    assert classify_touchdown(Touchdown(0.2, 0.3, 2), 1.0) is Termination.SUCCESS
    assert classify_touchdown(Touchdown(0.2, 2.0, 2), 1.0) is Termination.HARD_LANDING
    assert classify_touchdown(Touchdown(1.5, 0.3, 2), 1.0) is Termination.OFF_PAD
    assert terminal_reward(Termination.SUCCESS) > 0 > terminal_reward(Termination.CRASH)


def test_clip_action() -> None:
    assert clip_action((5, -5, 5, -5)) == (2.0, -2.0, 1.5, -0.5)


def test_curriculum_progression() -> None:
    assert next_stage(0, 0.5) == 0
    assert next_stage(0, 0.95) == 1
    last = len(CURRICULUM) - 1
    assert next_stage(last, 1.0) == last


def test_env_config_validation_and_phase_marker() -> None:
    with pytest.raises(ValueError):
        EnvConfig(control_hz=30)
    env = PrecisionLandingEnv()
    with pytest.raises(NotImplementedError, match="Phase 7"):
        env.reset(seed=0)
