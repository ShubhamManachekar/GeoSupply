# SubAgent Template — Pipeline Composition

## Template

```python
"""
[SubAgentName] — [one-line description]
Part of: GeoSupply AI FA v1
Layer: 4 (SubAgent)
Phase: [build phase number]
"""

import asyncio
from abc import ABC, abstractmethod
from geosupply.core.base_subagent import BaseSubAgent
from geosupply.core.decorators import tracer, cost_tracker


class [SubAgentName](BaseSubAgent):
    """
    [Detailed description of the pipeline this subagent composes]

    PIPELINE: step1 → step2(×N parallel) → step3(fuse) → result
    WORKERS USED: [list of workers called]
    """

    name = "[SubAgentName]"
    pipeline_steps = ["step_1", "step_2", "step_3"]
    parallel_steps = {"step_2"}  # steps that can run concurrently

    async def setup(self):
        """FA v1 G1: Called once before first run(). Initialise worker pools."""
        # self.worker_a = SomeWorker()
        # await self.worker_a.setup()
        pass

    @tracer
    @cost_tracker
    async def run(self, input_data: dict) -> dict:
        """Execute pipeline and return aggregated result."""
        total_cost = 0.0

        # Step 1: Sequential step
        step1_result = await self._step_1(input_data)
        total_cost += step1_result["meta"]["cost_inr"]

        # Step 2: Parallel step
        parallel_inputs = self._prepare_parallel(step1_result)
        step2_results = await self.run_parallel(
            [self._step_2] * len(parallel_inputs),
            parallel_inputs
        )
        total_cost += sum(r["meta"]["cost_inr"] for r in step2_results)

        # Step 3: Fusion step
        final = await self._step_3(step2_results)
        total_cost += final["meta"]["cost_inr"]

        return {
            "result": final["result"],
            "meta": {
                "subagent": self.name,
                "cost_inr": total_cost,
                "steps_completed": len(self.pipeline_steps),
            }
        }

    async def teardown(self):
        """FA v1 G1: Called on graceful shutdown."""
        pass

    # --- Private step implementations ---
    async def _step_1(self, data: dict) -> dict: ...
    async def _step_2(self, data: dict) -> dict: ...
    async def _step_3(self, data: list[dict]) -> dict: ...
```

## Key Rule
SubAgents **NEVER** call other SubAgents (no nesting). They only call Workers and infrastructure Agents.
