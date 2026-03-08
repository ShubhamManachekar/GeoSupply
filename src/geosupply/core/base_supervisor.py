"""
GeoSupply AI — BaseSupervisor
FA v2 | Part V | Layer 2

Supervisors enforce budgets, priorities, and phase gates.
They schedule agent work and manage backpressure.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections import deque

from geosupply.config import SUPERVISOR_MAX_QUEUE_DEPTH
from geosupply.schemas import TaskPacket

logger = logging.getLogger(__name__)


class BaseSupervisor(ABC):
    """
    Abstract base for all 14 supervisors.

    RESPONSIBILITIES:
        1. Budget gating (INR cap per cycle)
        2. Priority scheduling (critical tasks first)
        3. Backpressure (reject if queue full)
        4. Phase gate enforcement
    """

    name: str = "BaseSupervisor"
    domain: str = "default"
    budget_inr: float = 10.0               # Max INR per pipeline cycle
    max_queue_depth: int = SUPERVISOR_MAX_QUEUE_DEPTH
    agents: list[str] = []                 # Agent names managed

    _budget_remaining: float = 0.0
    _queue: deque = deque()
    _is_paused: bool = False

    def reset_budget(self) -> None:
        """Reset budget for new pipeline cycle."""
        self._budget_remaining = self.budget_inr

    @property
    def queue_depth(self) -> int:
        return len(self._queue)

    @property
    def is_budget_exhausted(self) -> bool:
        return self._budget_remaining <= 0

    async def dispatch(self, task: TaskPacket) -> dict:
        """
        Route task to best available agent.

        Returns:
            dict with 'status' ('completed', 'rejected') and result/reason.
        """
        # Backpressure check
        if self.queue_depth >= self.max_queue_depth:
            logger.warning(
                "%s: queue full (%d), rejecting task %s",
                self.name, self.queue_depth, task.task_id,
            )
            return {"status": "rejected", "reason": "queue_full"}

        # Budget check
        if self.is_budget_exhausted:
            logger.warning(
                "%s: budget exhausted (₹%.2f remaining), rejecting task %s",
                self.name, self._budget_remaining, task.task_id,
            )
            return {"status": "rejected", "reason": "budget_exhausted"}

        # Pause check
        if self._is_paused:
            return {"status": "rejected", "reason": "supervisor_paused"}

        # Task budget check
        if task.budget_inr > self._budget_remaining:
            logger.warning(
                "%s: task budget ₹%.2f exceeds remaining ₹%.2f",
                self.name, task.budget_inr, self._budget_remaining,
            )
            return {"status": "rejected", "reason": "task_over_budget"}

        # Execute
        self._queue.append(task.task_id)
        try:
            agent = await self._select_agent(task)
            result = await agent.safe_execute(task.model_dump())
            cost = result.get("meta", {}).get("cost_inr", 0.0)
            self._budget_remaining -= cost
            return {
                "status": "completed",
                "result": result,
                "cost_inr": cost,
                "budget_remaining": self._budget_remaining,
            }
        except Exception as exc:
            logger.error("%s: dispatch failed: %s", self.name, exc)
            return {"status": "error", "reason": str(exc)}
        finally:
            if task.task_id in self._queue:
                self._queue.remove(task.task_id)

    @abstractmethod
    async def _select_agent(self, task: TaskPacket):
        """Select the best agent for this task. Must return a BaseAgent."""
        ...

    def pause(self) -> None:
        """Pause supervisor — reject all tasks."""
        self._is_paused = True
        logger.info("%s: PAUSED", self.name)

    def resume(self) -> None:
        """Resume supervisor — accept tasks."""
        self._is_paused = False
        logger.info("%s: RESUMED", self.name)

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} name={self.name} "
            f"budget_remaining=₹{self._budget_remaining:.2f} "
            f"queue={self.queue_depth}>"
        )
