"""Gym-style precision-landing environment over the SimControl gRPC API.

Interface follows the Gymnasium ``Env`` contract (``reset(seed) -> (obs,
info)``, ``step(action) -> (obs, reward, terminated, truncated, info)``) so
it drops into standard training code in Phase 7. It does not import
gymnasium yet to keep Phase 0 dependency-free.

Connection to the simulator (schemas/control.proto ``SimControl``) arrives in
Phase 7 — see docs/08_AUTONOMY_TRAINING.md. Until then construction works
(so configuration can be tested) but ``reset``/``step`` raise.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar

from cdsim_rl.landing import CURRICULUM, LandingObs, RewardWeights, clip_action

PHASE = "Phase 7 (docs/10_ROADMAP.md)"


@dataclass(frozen=True)
class EnvConfig:
    sim_endpoint: str = "localhost:50051"
    scenario_id: str = "rl_precision_landing"
    area_id: str = "flat_test"
    pad_id: str = "pad_target"
    control_hz: float = 20.0
    physics_ticks_per_step: int = 20  # 400 Hz / 20 Hz
    max_episode_s: float = 60.0
    curriculum_stage: int = 0
    reward: RewardWeights = field(default_factory=RewardWeights)

    def __post_init__(self) -> None:
        if not 0 <= self.curriculum_stage < len(CURRICULUM):
            raise ValueError("curriculum_stage out of range")
        if self.physics_ticks_per_step * self.control_hz != 400:
            raise ValueError("physics_ticks_per_step * control_hz must equal 400 Hz")


class PrecisionLandingEnv:
    metadata: ClassVar[dict[str, Any]] = {"render_modes": []}

    def __init__(self, config: EnvConfig | None = None) -> None:
        self.config = config or EnvConfig()

    def reset(
        self, seed: int | None = None, options: dict[str, Any] | None = None
    ) -> tuple[LandingObs, dict[str, Any]]:
        raise NotImplementedError(PHASE)

    def step(
        self, action: tuple[float, float, float, float]
    ) -> tuple[LandingObs, float, bool, bool, dict[str, Any]]:
        clip_action(action)
        raise NotImplementedError(PHASE)

    def close(self) -> None:
        return None
