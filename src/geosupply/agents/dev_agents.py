"""Dev domain agents — Layer 3 wrappers for DevSupervisor."""
from __future__ import annotations

import asyncio
import importlib
import inspect
import json
import logging
import re
from datetime import datetime, timezone

from geosupply.agents.test_agents import _child_env, _guarded_result, _is_nested_run
from geosupply.core.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class SchemaMigrateAgent(BaseAgent):
    name = "SchemaMigrateAgent"
    domain = "dev"
    capabilities = {"DEV_SCHEMA_MIGRATE"}

    async def execute(self, task: dict) -> dict:
        trace_id = task.get("trace_id", "")
        valid_count = 0
        error_count = 0
        schemas: list[dict] = []
        try:
            from pydantic import BaseModel
            schemas_module = importlib.import_module("geosupply.schemas")
            for name, obj in inspect.getmembers(schemas_module, inspect.isclass):
                if issubclass(obj, BaseModel) and obj is not BaseModel:
                    try:
                        schema = obj.model_json_schema()
                        schemas.append({"model": name, "title": schema.get("title", name)})
                        valid_count += 1
                    except (TypeError, ValueError, AttributeError) as exc:
                        logger.warning("SchemaMigrateAgent: %s failed: %s", name, exc)
                        error_count += 1
        except ImportError as exc:
            logger.error("SchemaMigrateAgent: import failed: %s", exc)
            error_count += 1
        return {
            "result": {
                "valid_count": valid_count,
                "error_count": error_count,
                "schemas": schemas,
            },
            "meta": {
                "agent": self.name,
                "cost_inr": 0.0,
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }


class LintCheckAgent(BaseAgent):
    name = "LintCheckAgent"
    domain = "dev"
    capabilities = {"DEV_LINT_CHECK"}

    async def execute(self, task: dict) -> dict:
        trace_id = task.get("trace_id", "")
        payload = task.get("payload", task)
        target: str = payload.get("target", "src/geosupply")
        violations: list[dict] = []
        exit_code = 0
        try:
            proc = await asyncio.create_subprocess_exec(
                "python", "-m", "ruff", "check", target, "--output-format=json",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            exit_code = proc.returncode or 0
            if stdout:
                try:
                    violations = json.loads(stdout.decode("utf-8", errors="replace"))
                except json.JSONDecodeError:
                    pass
        except OSError as exc:
            logger.warning("LintCheckAgent: ruff failed: %s", exc)
        return {
            "result": {
                "violations": violations,
                "violation_count": len(violations),
                "exit_code": exit_code,
            },
            "meta": {
                "agent": self.name,
                "cost_inr": 0.0,
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }


class TestRunAgent(BaseAgent):
    name = "TestRunAgent"
    domain = "dev"
    capabilities = {"DEV_TEST_RUN"}

    async def execute(self, task: dict) -> dict:
        trace_id = task.get("trace_id", "")
        payload = task.get("payload", task)
        path: str = payload.get("path", "tests/")
        passed = 0
        failed = 0
        exit_code = 0
        if _is_nested_run():
            return _guarded_result(self.name, trace_id)
        try:
            proc = await asyncio.create_subprocess_exec(
                "python", "-m", "pytest", path, "-q", "--tb=no",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=_child_env(),
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
            logger.warning("TestRunAgent: pytest failed: %s", exc)
        return {
            "result": {
                "passed": passed,
                "failed": failed,
                "exit_code": exit_code,
            },
            "meta": {
                "agent": self.name,
                "cost_inr": 0.0,
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }
