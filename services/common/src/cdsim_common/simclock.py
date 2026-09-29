"""Unified simulation clock (``sim_time_us``).

Every telemetry frame, event, control input, audio chunk and video keyframe in
CD Sim is stamped with ``sim_time_us``: integer microseconds since the session
started, monotonic, never derived from wall-clock. Wall-clock is carried
alongside for reference only. See docs/02_ARCHITECTURE.md §"Unified time base"
and docs/ADR/0015-unified-sim-time-base.md.

The *authoritative* clock during a live session is the UE5 simulation (physics
tick count x fixed step). This Python implementation exists so that services,
the scenario runner, the RL harness and tests share the exact same semantics:

* ``ClockMode.REALTIME`` — sim time advances with the host monotonic clock,
  scaled by ``rate`` (0.1x .. 10x). Used by tools that pace themselves.
* ``ClockMode.STEPPED`` — sim time only advances when ``advance()`` is called.
  Used for lock-step RL, deterministic replay and unit tests.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

MIN_RATE = 0.1
MAX_RATE = 10.0

# 400 Hz physics step (docs/05_SITL_INTEGRATION.md) expressed in microseconds.
PHYSICS_STEP_US = 2_500


class ClockMode(str, Enum):
    REALTIME = "realtime"
    STEPPED = "stepped"


@dataclass(frozen=True)
class Stamp:
    """A pair of timestamps attached to every recorded message."""

    sim_time_us: int
    wall_time_us: int


def _default_monotonic_ns() -> int:
    return time.monotonic_ns()


def _default_wall_us() -> int:
    return time.time_ns() // 1_000


class SimClock:
    """Monotonic, rate-scalable simulation clock.

    The clock starts paused at ``sim_time_us == 0``. Rate changes are applied
    piecewise: time already elapsed is banked at the old rate, so changing the
    rate never makes sim time jump or run backwards.
    """

    def __init__(
        self,
        mode: ClockMode = ClockMode.REALTIME,
        rate: float = 1.0,
        monotonic_ns: Callable[[], int] = _default_monotonic_ns,
        wall_us: Callable[[], int] = _default_wall_us,
    ) -> None:
        self._validate_rate(rate)
        self._mode = mode
        self._rate = rate
        self._monotonic_ns = monotonic_ns
        self._wall_us = wall_us
        self._banked_us = 0
        self._running = False
        self._segment_start_ns = 0

    # ------------------------------------------------------------------ state
    @property
    def mode(self) -> ClockMode:
        return self._mode

    @property
    def rate(self) -> float:
        return self._rate

    @property
    def running(self) -> bool:
        return self._running

    # --------------------------------------------------------------- controls
    def start(self) -> None:
        """Start (or resume) advancing sim time. Idempotent."""
        if self._running:
            return
        self._running = True
        self._segment_start_ns = self._monotonic_ns()

    def pause(self) -> None:
        """Freeze sim time. Idempotent."""
        if not self._running:
            return
        self._banked_us = self.now_us()
        self._running = False

    def set_rate(self, rate: float) -> None:
        """Change the real-time multiplier without discontinuity."""
        self._validate_rate(rate)
        if self._running and self._mode is ClockMode.REALTIME:
            self._banked_us = self.now_us()
            self._segment_start_ns = self._monotonic_ns()
        self._rate = rate

    def advance(self, delta_us: int) -> int:
        """Advance a STEPPED clock by ``delta_us`` and return the new time."""
        if self._mode is not ClockMode.STEPPED:
            raise RuntimeError("advance() is only valid on a STEPPED clock")
        if delta_us < 0:
            raise ValueError("sim time is monotonic; delta_us must be >= 0")
        self._banked_us += delta_us
        return self._banked_us

    def step(self, ticks: int = 1) -> int:
        """Advance a STEPPED clock by ``ticks`` physics steps (400 Hz)."""
        return self.advance(ticks * PHYSICS_STEP_US)

    # ----------------------------------------------------------------- reads
    def now_us(self) -> int:
        """Current sim time in integer microseconds."""
        if self._mode is ClockMode.STEPPED or not self._running:
            return self._banked_us
        elapsed_ns = self._monotonic_ns() - self._segment_start_ns
        return self._banked_us + int(elapsed_ns * self._rate) // 1_000

    def stamp(self) -> Stamp:
        """Sim time plus reference wall-clock, for a message header."""
        return Stamp(sim_time_us=self.now_us(), wall_time_us=self._wall_us())

    @staticmethod
    def _validate_rate(rate: float) -> None:
        if not (MIN_RATE <= rate <= MAX_RATE):
            raise ValueError(f"sim rate {rate} outside [{MIN_RATE}, {MAX_RATE}]")
