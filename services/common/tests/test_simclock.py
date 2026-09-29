import pytest

from cdsim_common.simclock import PHYSICS_STEP_US, ClockMode, SimClock


class FakeMonotonic:
    def __init__(self) -> None:
        self.ns = 1_000_000_000

    def __call__(self) -> int:
        return self.ns

    def advance_s(self, s: float) -> None:
        self.ns += int(s * 1e9)


def test_starts_paused_at_zero() -> None:
    clk = SimClock(monotonic_ns=FakeMonotonic())
    assert clk.now_us() == 0
    assert not clk.running


def test_realtime_advances_with_host_clock() -> None:
    mono = FakeMonotonic()
    clk = SimClock(monotonic_ns=mono)
    clk.start()
    mono.advance_s(1.5)
    assert clk.now_us() == 1_500_000


def test_pause_freezes_time() -> None:
    mono = FakeMonotonic()
    clk = SimClock(monotonic_ns=mono)
    clk.start()
    mono.advance_s(1.0)
    clk.pause()
    mono.advance_s(10.0)
    assert clk.now_us() == 1_000_000
    clk.start()
    mono.advance_s(0.5)
    assert clk.now_us() == 1_500_000


def test_rate_change_is_continuous_and_scaled() -> None:
    mono = FakeMonotonic()
    clk = SimClock(monotonic_ns=mono)
    clk.start()
    mono.advance_s(1.0)
    clk.set_rate(10.0)
    assert clk.now_us() == 1_000_000  # no jump at the switch
    mono.advance_s(1.0)
    assert clk.now_us() == 11_000_000
    clk.set_rate(0.1)
    mono.advance_s(1.0)
    assert clk.now_us() == 11_100_000


@pytest.mark.parametrize("rate", [0.0, 0.09, 10.01, -1.0])
def test_rate_bounds(rate: float) -> None:
    with pytest.raises(ValueError):
        SimClock(rate=rate)


def test_stepped_clock_is_deterministic() -> None:
    a = SimClock(mode=ClockMode.STEPPED)
    b = SimClock(mode=ClockMode.STEPPED)
    for _ in range(400):
        a.step()
    b.advance(400 * PHYSICS_STEP_US)
    assert a.now_us() == b.now_us() == 1_000_000


def test_stepped_rejects_negative_and_realtime_rejects_advance() -> None:
    with pytest.raises(ValueError):
        SimClock(mode=ClockMode.STEPPED).advance(-1)
    with pytest.raises(RuntimeError):
        SimClock().advance(1)


def test_stamp_carries_wall_clock_separately() -> None:
    clk = SimClock(mode=ClockMode.STEPPED, wall_us=lambda: 42)
    clk.advance(7)
    s = clk.stamp()
    assert (s.sim_time_us, s.wall_time_us) == (7, 42)
