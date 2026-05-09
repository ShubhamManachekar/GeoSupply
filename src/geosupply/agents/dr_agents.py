"""Disaster Recovery domain agents — Layer 3 wrappers for DisasterRecoverySupervisor."""
from __future__ import annotations

import logging
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from geosupply.core.base_agent import BaseAgent
from geosupply.config import SQLITE_PATH, DATA_DIR, BUDGET_CAP_INR

logger = logging.getLogger(__name__)


class BackupAgent(BaseAgent):
    name = "BackupAgent"
    domain = "disaster_recovery"
    capabilities = {"DR_BACKUP"}

    async def execute(self, task: dict) -> dict:
        trace_id = task.get("trace_id", "")
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = DATA_DIR / f"swarm_backup_{timestamp}.db"
        backup_created = False
        error: str | None = None
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(SQLITE_PATH), str(backup_path))
            backup_created = True
        except (OSError, shutil.Error) as exc:
            error = str(exc)
            logger.warning("BackupAgent: backup failed: %s", exc)
        return {
            "result": {
                "backup_created": backup_created,
                "backup_path": str(backup_path),
                "error": error,
            },
            "meta": {
                "agent": self.name,
                "cost_inr": 0.0,
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }


class CostProjectionAgent(BaseAgent):
    name = "CostProjectionAgent"
    domain = "disaster_recovery"
    capabilities = {"DR_COST_PROJECTION"}

    async def execute(self, task: dict) -> dict:
        trace_id = task.get("trace_id", "")
        daily_avg: float = 0.0
        projected_monthly: float = 0.0
        over_budget: bool = False
        try:
            with sqlite3.connect(str(SQLITE_PATH), timeout=5.0) as conn:
                row = conn.execute(
                    "SELECT AVG(daily_cost) FROM ("
                    "  SELECT DATE(timestamp) as day, SUM(cost_inr) as daily_cost "
                    "  FROM swarm_logs "
                    "  WHERE timestamp >= datetime('now', '-7 days') "
                    "  GROUP BY day"
                    ")"
                ).fetchone()
                daily_avg = float(row[0] or 0.0)
                projected_monthly = round(daily_avg * 30, 4)
                over_budget = projected_monthly > BUDGET_CAP_INR
        except sqlite3.OperationalError as exc:
            logger.warning("CostProjectionAgent: SQLite query failed: %s", exc)
        return {
            "result": {
                "daily_avg_inr": daily_avg,
                "projected_monthly_inr": projected_monthly,
                "over_budget": over_budget,
                "budget_cap_inr": BUDGET_CAP_INR,
            },
            "meta": {
                "agent": self.name,
                "cost_inr": 0.0,
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }


class RestoreAgent(BaseAgent):
    name = "RestoreAgent"
    domain = "disaster_recovery"
    capabilities = {"DR_RESTORE"}

    async def execute(self, task: dict) -> dict:
        trace_id = task.get("trace_id", "")
        payload = task.get("payload", task)
        backup_path: str = payload.get("backup_path", "")
        restored = False
        error: str | None = None
        try:
            bp = Path(backup_path)
            if not bp.exists():
                error = f"Backup path does not exist: {backup_path}"
            else:
                shutil.copy2(str(bp), str(SQLITE_PATH))
                restored = True
        except (OSError, shutil.Error) as exc:
            error = str(exc)
            logger.warning("RestoreAgent: restore failed: %s", exc)
        return {
            "result": {"restored": restored, "backup_path": backup_path, "error": error},
            "meta": {
                "agent": self.name,
                "cost_inr": 0.0,
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }


class FailoverAgent(BaseAgent):
    name = "FailoverAgent"
    domain = "disaster_recovery"
    capabilities = {"DR_FAILOVER"}

    async def execute(self, task: dict) -> dict:
        trace_id = task.get("trace_id", "")
        backup_result = await BackupAgent().execute({"trace_id": trace_id})
        return {
            "result": {
                "failover_triggered": True,
                "backup_result": backup_result.get("result", {}),
            },
            "meta": {
                "agent": self.name,
                "cost_inr": backup_result.get("meta", {}).get("cost_inr", 0.0),
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }
