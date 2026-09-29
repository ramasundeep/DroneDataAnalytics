"""Assessment metrics v1 — definitions and signatures.

Each function below is the single definition of a metric. The docstrings are
normative (docs/06_ASSESSMENT_ENGINE.md repeats them with worked examples).
All inputs are ordered by (sim_time_us, seq) and all times are sim time.

Implementations arrive in **Phase 3** (docs/10_ROADMAP.md); until then each
raises ``NotImplementedError`` so nothing can silently report a fake score.
``landing_*`` metrics are already computable because the touchdown outcome
event carries the measured values directly.
"""

from __future__ import annotations

from collections.abc import Sequence

from cdsim_common.events import Event

PHASE = "Phase 3 (docs/10_ROADMAP.md)"

# A control input counts as "meaningful" when a normalised stick axis moves
# more than this from its value at the stimulus (tunable per rubric params).
MEANINGFUL_DEFLECTION = 0.10


def reaction_time_s(stimulus: Event, responses: Sequence[Event]) -> float | None:
    """Stimulus → first *meaningful* response by the same actor, in seconds.

    First response event (any kind) with ``sim_time_us >= stimulus`` and, for
    control inputs, ``magnitude >= MEANINGFUL_DEFLECTION``. None if no
    response within the rubric's window (default 30 s).
    """
    raise NotImplementedError(PHASE)


def decision_latency_s(stimulus: Event, responses: Sequence[Event]) -> float | None:
    """Stimulus → first response whose code is in ``expected_response_codes``."""
    raise NotImplementedError(PHASE)


def hesitation_s(stimulus: Event, responses: Sequence[Event]) -> float | None:
    """decision_latency - reaction_time: time spent acting before acting correctly."""
    raise NotImplementedError(PHASE)


def control_jerk_rms(samples_us: Sequence[int], axis_values: Sequence[float]) -> float:
    """RMS of the second time-derivative of a normalised stick axis (1/s²)."""
    raise NotImplementedError(PHASE)


def procedure_adherence(procedure_steps: Sequence[str], step_events: Sequence[Event]) -> float:
    """Fraction of steps completed, in order, with the declared tool. 0..1."""
    raise NotImplementedError(PHASE)


def recovery_time_s(failure: Event, stable_since_us: int | None) -> float | None:
    """Injected failure → vehicle back inside the stability envelope for ≥ 2 s."""
    raise NotImplementedError(PHASE)


def comms_onset_s(stimulus: Event, voice_onsets: Sequence[Event]) -> float | None:
    """Stimulus → first voice-activity onset (audio energy above threshold)."""
    raise NotImplementedError(PHASE)


def landing_radial_error_m(touchdown: Event) -> float:
    """Horizontal distance from pad centre at touchdown, from the outcome event."""
    if touchdown.outcome is None or touchdown.outcome.landing_touchdown is None:
        raise ValueError("not a landing_touchdown outcome")
    return touchdown.outcome.landing_touchdown.radial_error_m


def landing_vertical_speed_mps(touchdown: Event) -> float:
    """Magnitude of vertical velocity at touchdown (m/s, positive)."""
    if touchdown.outcome is None or touchdown.outcome.landing_touchdown is None:
        raise ValueError("not a landing_touchdown outcome")
    return abs(touchdown.outcome.landing_touchdown.velocity_mps.z)


def landing_attitude_deg(touchdown: Event) -> float:
    """Max of |roll|, |pitch| at touchdown (degrees)."""
    if touchdown.outcome is None or touchdown.outcome.landing_touchdown is None:
        raise ValueError("not a landing_touchdown outcome")
    td = touchdown.outcome.landing_touchdown
    return max(abs(td.roll_deg), abs(td.pitch_deg))
