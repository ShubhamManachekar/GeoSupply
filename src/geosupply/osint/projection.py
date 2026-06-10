"""
GeoSupply AI — Self-improving risk projections.

Per-country next-cycle risk forecast via exponential smoothing whose
smoothing factor is *learned online*: every cycle the projector scores its
previous forecasts against what actually happened and shifts probability
mass toward the alpha that has been making the smallest errors.

This is the deterministic, ₹0 counterpart of the v8 XGBoost+Platt pipeline:
isolated from LLMs, honest about its own error (projection_mae is exposed
on the System panel). Pure CPU — cost_inr = 0.
"""
from __future__ import annotations

from collections import deque

ALPHA_GRID = (0.2, 0.4, 0.6, 0.8)
ERROR_WINDOW = 24           # rolling forecast-error window per alpha
MIN_SAMPLES = 3             # forecasts published only after some history


class RiskProjector:
    """Online-learning exponential smoother for country risk scores."""

    def __init__(self) -> None:
        # per-alpha smoothed level per country: {alpha: {iso2: level}}
        self._levels: dict[float, dict[str, float]] = {a: {} for a in ALPHA_GRID}
        # per-alpha rolling absolute errors (across countries)
        self._errors: dict[float, deque[float]] = {
            a: deque(maxlen=ERROR_WINDOW) for a in ALPHA_GRID
        }
        # last published forecast per country (from the best alpha)
        self._last_forecast: dict[str, float] = {}
        self._samples = 0

    # ── learning ──────────────────────────────────────────────────────
    @property
    def best_alpha(self) -> float:
        """Alpha with the lowest rolling MAE; middle of grid until data."""
        scored = [
            (sum(errs) / len(errs), a)
            for a, errs in self._errors.items() if errs
        ]
        if not scored:
            return ALPHA_GRID[len(ALPHA_GRID) // 2]
        return min(scored)[1]

    @property
    def mae(self) -> float | None:
        errs = self._errors[self.best_alpha]
        return round(sum(errs) / len(errs), 2) if errs else None

    @property
    def samples(self) -> int:
        return self._samples

    def observe(self, actual_scores: dict[str, float]) -> dict[str, float]:
        """
        Feed this cycle's actual scores: score the previous forecasts
        (learning step), update every alpha's level, and return the next-cycle
        forecast per country from the currently-best alpha.
        """
        # 1. learn: score what each alpha would have predicted
        for alpha, levels in self._levels.items():
            for iso2, actual in actual_scores.items():
                if iso2 in levels:
                    self._errors[alpha].append(abs(levels[iso2] - actual))

        # 2. update levels for every candidate alpha
        for alpha, levels in self._levels.items():
            for iso2, actual in actual_scores.items():
                prev = levels.get(iso2)
                levels[iso2] = (actual if prev is None
                                else alpha * actual + (1 - alpha) * prev)

        self._samples += 1

        # 3. forecast from the best-performing alpha
        if self._samples < MIN_SAMPLES:
            self._last_forecast = {}
            return {}
        best = self._levels[self.best_alpha]
        self._last_forecast = {
            iso2: round(min(100.0, max(0.0, level)), 1)
            for iso2, level in best.items() if iso2 in actual_scores
        }
        return dict(self._last_forecast)

    def forecast_for(self, iso2: str) -> float | None:
        return self._last_forecast.get(iso2)

    # ── persistence ───────────────────────────────────────────────────
    def to_state(self) -> dict:
        return {
            "levels": {str(a): dict(v) for a, v in self._levels.items()},
            "errors": {str(a): list(v) for a, v in self._errors.items()},
            "samples": self._samples,
        }

    def load_state(self, state: dict) -> None:
        try:
            for a_str, levels in (state.get("levels") or {}).items():
                alpha = float(a_str)
                if alpha in self._levels and isinstance(levels, dict):
                    self._levels[alpha] = {k: float(v) for k, v in levels.items()}
            for a_str, errs in (state.get("errors") or {}).items():
                alpha = float(a_str)
                if alpha in self._errors and isinstance(errs, list):
                    self._errors[alpha] = deque(
                        (float(e) for e in errs), maxlen=ERROR_WINDOW)
            self._samples = int(state.get("samples", 0))
        except (TypeError, ValueError):
            return
