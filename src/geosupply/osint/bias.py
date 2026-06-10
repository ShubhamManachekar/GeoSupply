"""
GeoSupply AI — News analysis & source bias handler.

Per-outlet profiling over the live wire with a *learned* credibility weight,
closing the v8 SourceFeedback loop deterministically:

  - sensationalism: share of an outlet's headlines in ALERT/FLASH bands
  - corroboration:  a high-priority claim is corroborated when another
    outlet reports overlapping entities within the same window
  - credibility:    -0.05 per uncorroborated flash batch, +0.02 recovery
    when corroborated, floor 0.10 / cap 1.0 — downweighted, never silenced

Credibility weights feed back into country-risk scoring, so a chronically
sensationalist single-source outlet stops moving the risk index.
Pure CPU — cost_inr = 0.
"""
from __future__ import annotations

from collections import defaultdict

from geosupply.osint.models import NewsItem, SourceBias

PENALTY = 0.05            # v8 SourceFeedback: -0.05 per uncorroborated batch
RECOVERY = 0.02           # +0.02 when an outlet's claims are corroborated
FLOOR = 0.10
CAP = 1.0
DEFAULT_CREDIBILITY = 0.5
SENSATIONAL_FLAG = 0.6    # >60% of output in ALERT/FLASH bands
LONE_WOLF_FLAG = 0.25     # <25% of high-priority claims corroborated


class SourceBiasTracker:
    """Learns per-source credibility from corroboration across outlets."""

    def __init__(self) -> None:
        self._credibility: dict[str, float] = {}
        self._profiles: dict[str, SourceBias] = {}

    # ── learning cycle ───────────────────────────────────────────────
    def analyze(self, news: list[NewsItem]) -> list[SourceBias]:
        """Profile this cycle's wire and update credibility weights."""
        by_source: dict[str, list[NewsItem]] = defaultdict(list)
        for item in news:
            by_source[item.source].append(item)

        profiles: list[SourceBias] = []
        for source, items in by_source.items():
            hot = [n for n in items if n.priority >= 2]
            corroborated = sum(
                1 for n in hot if self._is_corroborated(n, news)
            )
            corr_rate = corroborated / len(hot) if hot else 1.0
            sensationalism = len(hot) / len(items) if items else 0.0

            cred = self._credibility.get(source, DEFAULT_CREDIBILITY)
            if hot:
                if corr_rate < 0.5:
                    cred -= PENALTY        # uncorroborated flash batch
                else:
                    cred += RECOVERY       # corroborated — recover
            else:
                cred += RECOVERY / 2       # calm cycle drifts back to neutral
            cred = min(CAP, max(FLOOR, round(cred, 3)))
            self._credibility[source] = cred

            flags: list[str] = []
            if sensationalism >= SENSATIONAL_FLAG and len(items) >= 3:
                flags.append("SENSATIONALIST")
            if hot and corr_rate <= LONE_WOLF_FLAG:
                flags.append("UNCORROBORATED")
            if cred <= 0.25:
                flags.append("LOW_TRUST")

            profile = SourceBias(
                source=source,
                items=len(items),
                avg_priority=round(sum(n.priority for n in items) / len(items), 2),
                sensationalism=round(sensationalism, 3),
                corroboration_rate=round(corr_rate, 3),
                credibility=cred,
                bias_flags=flags,
            )
            self._profiles[source] = profile
            profiles.append(profile)

        profiles.sort(key=lambda p: p.credibility)
        return profiles

    @staticmethod
    def _is_corroborated(item: NewsItem, wire: list[NewsItem]) -> bool:
        """Another outlet reports ≥1 shared entity at priority ≥1."""
        if not item.entities:
            return True  # nothing checkable — don't penalise
        ents = set(item.entities)
        return any(
            other.source != item.source
            and other.priority >= 1
            and ents & set(other.entities)
            for other in wire
        )

    # ── consumers ─────────────────────────────────────────────────────
    def weight(self, source: str) -> float:
        return self._credibility.get(source, DEFAULT_CREDIBILITY)

    @property
    def penalised_count(self) -> int:
        return sum(1 for c in self._credibility.values() if c < DEFAULT_CREDIBILITY)

    # ── persistence ───────────────────────────────────────────────────
    def to_state(self) -> dict[str, float]:
        return dict(self._credibility)

    def load_state(self, state: dict[str, float]) -> None:
        for source, cred in state.items():
            try:
                self._credibility[source] = min(CAP, max(FLOOR, float(cred)))
            except (TypeError, ValueError):
                continue
