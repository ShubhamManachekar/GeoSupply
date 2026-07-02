"""
GeoSupply AI — RAG feedback learner (self-reinforcement over agentic RAG).

Closes the loop on `/osint/ask`: users vote ↑ / ↓ on individual citations,
and the retriever's per-source weight is nudged with a bounded exponential
moving average toward the observed usefulness. Sources whose citations are
consistently helpful float their retrieval score; consistently unhelpful
ones are downweighted (never silenced — floor `FEEDBACK_FLOOR`).

Design mirrors the existing bias handler & projector:
  - CPU-only, ₹0
  - JSON-serialisable state, persisted through OsintAggregator.save_state()
  - Deterministic (no randomness), so tests can pin behaviour exactly
"""
from __future__ import annotations

from dataclasses import dataclass

FEEDBACK_LR = 0.20         # EMA learning rate — 20% pull per vote
FEEDBACK_FLOOR = 0.20      # a source is never fully silenced
FEEDBACK_CAP = 2.0         # can climb up to 2× baseline retrieval score
DEFAULT_WEIGHT = 1.0
MIN_VOTES_FOR_TRUST = 3    # panel needs at least N votes before reporting


@dataclass(frozen=True)
class FeedbackEvent:
    """One user vote against one citation returned by `answer_query`."""
    source: str
    kind: str           # "news" | "event" | "risk" | ...
    vote: int           # +1 helpful, -1 unhelpful

    @staticmethod
    def normalise_vote(raw: int) -> int:
        try:
            v = int(raw)
        except (TypeError, ValueError):
            return 0
        if v > 0:
            return 1
        if v < 0:
            return -1
        return 0


class RagFeedback:
    """Per-source retrieval-weight learner for agentic RAG."""

    def __init__(self) -> None:
        self._weights: dict[str, float] = {}
        self._votes: dict[str, int] = {}      # net votes per source
        self._observations: dict[str, int] = {}

    # ── learning ─────────────────────────────────────────────────────
    def apply(self, events: list[FeedbackEvent]) -> int:
        """
        Fold a batch of votes into per-source weights.
        Returns the number of accepted (non-empty, non-zero) events.
        """
        accepted = 0
        for ev in events:
            vote = FeedbackEvent.normalise_vote(ev.vote)
            if vote == 0 or not ev.source:
                continue
            target = FEEDBACK_CAP if vote > 0 else FEEDBACK_FLOOR
            current = self._weights.get(ev.source, DEFAULT_WEIGHT)
            # Bounded EMA: monotonic pull toward target, capped at CAP/FLOOR
            new = current + FEEDBACK_LR * (target - current)
            self._weights[ev.source] = round(
                min(FEEDBACK_CAP, max(FEEDBACK_FLOOR, new)), 3)
            self._votes[ev.source] = self._votes.get(ev.source, 0) + vote
            self._observations[ev.source] = self._observations.get(ev.source, 0) + 1
            accepted += 1
        return accepted

    # ── retrieval integration ────────────────────────────────────────
    def weight(self, source: str) -> float:
        """
        Multiplier retrieval scoring applies to a source's citations.
        Sources without feedback history return DEFAULT_WEIGHT (== 1.0),
        so behaviour is unchanged until users start voting.
        """
        return self._weights.get(source, DEFAULT_WEIGHT)

    # ── introspection ────────────────────────────────────────────────
    @property
    def trained_sources(self) -> int:
        return sum(1 for n in self._observations.values() if n >= MIN_VOTES_FOR_TRUST)

    def summary(self) -> list[dict]:
        """Compact readable view for the /osint/ask/feedback dashboard chip."""
        rows = []
        for src, w in self._weights.items():
            n = self._observations.get(src, 0)
            if n < MIN_VOTES_FOR_TRUST:
                continue
            rows.append({
                "source": src,
                "weight": w,
                "net_votes": self._votes.get(src, 0),
                "observations": n,
            })
        rows.sort(key=lambda r: r["weight"], reverse=True)
        return rows

    # ── persistence (round-trips through aggregator state file) ──────
    def to_state(self) -> dict:
        return {
            "weights": dict(self._weights),
            "votes": dict(self._votes),
            "observations": dict(self._observations),
        }

    def load_state(self, state: dict) -> None:
        if not isinstance(state, dict):
            return
        try:
            for k, v in (state.get("weights") or {}).items():
                self._weights[str(k)] = min(
                    FEEDBACK_CAP, max(FEEDBACK_FLOOR, float(v)))
            for k, v in (state.get("votes") or {}).items():
                self._votes[str(k)] = int(v)
            for k, v in (state.get("observations") or {}).items():
                self._observations[str(k)] = int(v)
        except (TypeError, ValueError):
            # Malformed state: refuse to load rather than corrupt in-flight learners.
            self._weights.clear()
            self._votes.clear()
            self._observations.clear()
