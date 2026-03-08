"""
GeoSupply AI — BaseSubAgent
FA v2 | Part III | Layer 4

SubAgents compose workers into directed pipelines.
FA v1 G1: Added setup()/teardown() lifecycle hooks.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BaseSubAgent(ABC):
    """
    Abstract base for all 13 subagents.

    PIPELINE PATTERN:
        step 1 → step 2a ─┐
                  step 2b ─┤ → step 3 (fuse) → result
                  step 2c ─┘

    INVARIANTS:
        - SubAgents NEVER call other SubAgents (no nesting)
        - SubAgents can call Workers and infrastructure Agents
        - Results are Pydantic models (type-safe)
        - Cost aggregated from all worker calls
    """

    name: str = "BaseSubAgent"
    pipeline_steps: list[str] = []
    parallel_steps: set[str] = set()       # Steps that can run concurrently

    _is_setup: bool = False

    async def setup(self) -> None:
        """FA v1 G1: Called once before first run(). Initialise worker pools."""
        self._is_setup = True

    @abstractmethod
    async def run(self, input_data: dict) -> dict:
        """
        Execute the pipeline and return aggregated result.

        Returns:
            dict with 'result' and 'meta' (including cost_inr)
        """
        ...

    async def teardown(self) -> None:
        """FA v1 G1: Called on graceful shutdown. Release worker pools."""
        self._is_setup = False

    async def run_parallel(
        self,
        steps: list,
        inputs: list[dict],
    ) -> list[dict]:
        """Run multiple worker calls in parallel."""
        if len(steps) != len(inputs):
            raise ValueError(
                f"Steps ({len(steps)}) and inputs ({len(inputs)}) count mismatch"
            )
        return await asyncio.gather(
            *[step(inp) for step, inp in zip(steps, inputs)],
            return_exceptions=False,
        )

    async def safe_run(self, input_data: dict) -> dict:
        """Wrapper with setup guard and error handling."""
        if not self._is_setup:
            await self.setup()

        try:
            return await self.run(input_data)
        except Exception as exc:
            logger.error("%s: pipeline failed: %s", self.name, exc)
            return {
                "result": None,
                "meta": {
                    "subagent": self.name,
                    "cost_inr": 0.0,
                    "error": str(exc),
                    "steps_completed": 0,
                },
            }

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name} steps={self.pipeline_steps}>"
