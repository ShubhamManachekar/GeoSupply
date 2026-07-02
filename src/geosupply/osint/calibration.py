"""
GeoSupply AI — Adaptive threshold calibrator (self-reinforcement).

Chokepoint stress bands (ELEVATED / HIGH / CRITICAL) were fixed constants
(0.25 / 0.50 / 0.75). This calibrator learns them from the *empirical
distribution* of observed stress indices: cutoffs drift toward the rolling
60th / 80th / 93rd percentiles, blended with the static defaults by sample
count, so a persistently noisy world doesn't stay permanently "CRITICAL"
and a quiet one still escalates on genuine spikes.

Deterministic, CPU-only, ₹0. State round-trips through the aggregator's
learning-state file like every other learner.
"""
from __future__ import annotations

from collections import deque

DEFAULT_BANDS: tuple[float, float, float] = (0.25, 0.50, 0.75)
QUANTILES: tuple[float, float, float] = (0.60, 0.80, 0.93)
WINDOW = 500              # rolling stress observations (all chokepoints)
MIN_SAMPLES = 40          # below this, defaults are used unblended
FULL_TRUST_SAMPLES = 200  # at/above this, learned quantiles get full weight
# Bands may never drift outside these guard rails (epistemic safety)
BAND_MIN = (0.10, 0.30, 0.55)
BAND_MAX = (0.40, 0.65, 0.90)


def _quantile(sorted_values: list[float], q: float) -> float:
    """Linear-interpolated quantile of a pre-sorted list."""
    if not sorted_values:
        return 0.0
    pos = q * (len(sorted_values) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_values) - 1)
    frac = pos - lo
    return sorted_values[lo] * (1 - frac) + sorted_values[hi] * frac


class ThresholdCalibrator:
    """Learns stress-band cutoffs from observed chokepoint stress indices."""

    def __init__(self) -> None:
        self._window: deque[float] = deque(maxlen=WINDOW)

    @property
    def samples(self) -> int:
        return len(self._window)

    def observe(self, stress_values: list[float]) -> None:
        """Feed this cycle's chokepoint stress indices."""
        for v in stress_values:
            try:
                f = float(v)
            except (TypeError, ValueError):
                continue
            if 0.0 <= f <= 1.0:
                self._window.append(f)

    def bands(self) -> tuple[float, float, float]:
        """
        Current ELEVATED/HIGH/CRITICAL cutoffs.
        Defaults until MIN_SAMPLES; then a sample-count-weighted blend of
        defaults and learned quantiles, clamped to guard rails, and forced
        strictly increasing.
        """
        n = len(self._window)
        if n < MIN_SAMPLES:
            return DEFAULT_BANDS
        trust = min(1.0, n / FULL_TRUST_SAMPLES)
        ordered = sorted(self._window)
        out: list[float] = []
        for i, (default, q) in enumerate(zip(DEFAULT_BANDS, QUANTILES, strict=True)):
            learned = _quantile(ordered, q)
            blended = (1 - trust) * default + trust * learned
            out.append(round(min(BAND_MAX[i], max(BAND_MIN[i], blended)), 3))
        # enforce strictly increasing cutoffs
        for i in (1, 2):
            if out[i] <= out[i - 1]:
                out[i] = round(min(BAND_MAX[i], out[i - 1] + 0.05), 3)
        return (out[0], out[1], out[2])

    # ── persistence ───────────────────────────────────────────────────
    def to_state(self) -> list[float]:
        return list(self._window)

    def load_state(self, state: list) -> None:
        if not isinstance(state, list):
            return
        for v in state[-WINDOW:]:
            try:
                f = float(v)
            except (TypeError, ValueError):
                continue
            if 0.0 <= f <= 1.0:
                self._window.append(f)
