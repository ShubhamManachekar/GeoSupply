"""Test domain agents — Layer 3 wrappers for TestSupervisor."""
from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone

from geosupply.core.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class UnitTestAgent(BaseAgent):
    name = "UnitTestAgent"
    domain = "test"
    capabilities = {"TEST_UNIT"}

    async def execute(self, task: dict) -> dict:
        trace_id = task.get("trace_id", "")
        passed = 0
        failed = 0
        exit_code = 0
        try:
            proc = await asyncio.create_subprocess_exec(
                "python", "-m", "pytest", "tests/unit/", "-q", "--tb=no",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            exit_code = proc.returncode or 0
            output = stdout.decode("utf-8", errors="replace")
            m = re.search(r"(\d+) passed", output)
            if m:
                passed = int(m.group(1))
            m2 = re.search(r"(\d+) failed", output)
            if m2:
                failed = int(m2.group(1))
        except OSError as exc:
            logger.warning("UnitTestAgent: pytest failed: %s", exc)
        return {
            "result": {"passed": passed, "failed": failed, "exit_code": exit_code},
            "meta": {
                "agent": self.name,
                "cost_inr": 0.0,
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }


class IntegrationTestAgent(BaseAgent):
    name = "IntegrationTestAgent"
    domain = "test"
    capabilities = {"TEST_INTEGRATION"}

    async def execute(self, task: dict) -> dict:
        trace_id = task.get("trace_id", "")
        passed = 0
        failed = 0
        exit_code = 0
        try:
            proc = await asyncio.create_subprocess_exec(
                "python", "-m", "pytest", "tests/integration/", "-q", "--tb=no",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            exit_code = proc.returncode or 0
            output = stdout.decode("utf-8", errors="replace")
            m = re.search(r"(\d+) passed", output)
            if m:
                passed = int(m.group(1))
            m2 = re.search(r"(\d+) failed", output)
            if m2:
                failed = int(m2.group(1))
        except OSError as exc:
            logger.warning("IntegrationTestAgent: pytest failed: %s", exc)
        return {
            "result": {"passed": passed, "failed": failed, "exit_code": exit_code},
            "meta": {
                "agent": self.name,
                "cost_inr": 0.0,
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }


class CoverageAgent(BaseAgent):
    name = "CoverageAgent"
    domain = "test"
    capabilities = {"TEST_COVERAGE"}

    async def execute(self, task: dict) -> dict:
        trace_id = task.get("trace_id", "")
        percent_covered: float = 0.0
        exit_code = 0
        try:
            proc = await asyncio.create_subprocess_exec(
                "python", "-m", "pytest", "tests/", "--cov=geosupply",
                "--cov-report=json", "--tb=no", "-q",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, _ = await proc.communicate()
            exit_code = proc.returncode or 0
            try:
                with open("coverage.json") as f:
                    cov_data = json.load(f)
                percent_covered = float(cov_data.get("totals", {}).get("percent_covered", 0.0))
            except (OSError, json.JSONDecodeError, KeyError):
                pass
        except OSError as exc:
            logger.warning("CoverageAgent: pytest --cov failed: %s", exc)
        return {
            "result": {"percent_covered": percent_covered, "exit_code": exit_code},
            "meta": {
                "agent": self.name,
                "cost_inr": 0.0,
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }
