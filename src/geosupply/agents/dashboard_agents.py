"""Dashboard domain agents — Layer 3 wrappers for DashboardSupervisor."""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone

from geosupply.core.base_agent import BaseAgent
from geosupply.config import SQLITE_PATH

logger = logging.getLogger(__name__)


class MetricPullAgent(BaseAgent):
    name = "MetricPullAgent"
    domain = "dashboard"
    capabilities = {"DASH_METRIC_PULL"}

    async def execute(self, task: dict) -> dict:
        trace_id = task.get("trace_id", "")
        metrics: list[dict] = []
        try:
            with sqlite3.connect(str(SQLITE_PATH), timeout=5.0) as conn:
                rows = conn.execute(
                    "SELECT severity, COUNT(*), SUM(cost_inr) FROM swarm_logs GROUP BY severity"
                ).fetchall()
                metrics = [
                    {"severity": row[0], "count": row[1], "total_cost_inr": row[2] or 0.0}
                    for row in rows
                ]
        except sqlite3.OperationalError as exc:
            logger.warning("MetricPullAgent: SQLite query failed: %s", exc)
        return {
            "result": {"metrics": metrics, "metric_count": len(metrics)},
            "meta": {
                "agent": self.name,
                "cost_inr": 0.0,
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }


class AlertRenderAgent(BaseAgent):
    name = "AlertRenderAgent"
    domain = "dashboard"
    capabilities = {"DASH_ALERT_RENDER"}

    async def execute(self, task: dict) -> dict:
        trace_id = task.get("trace_id", "")
        payload = task.get("payload", task)
        minutes_back: int = int(payload.get("minutes", 60))
        alerts: list[dict] = []
        try:
            with sqlite3.connect(str(SQLITE_PATH), timeout=5.0) as conn:
                rows = conn.execute(
                    "SELECT id, severity, message, timestamp, cost_inr FROM swarm_logs "
                    "WHERE severity IN ('CRITICAL','ERROR') "
                    "AND timestamp >= datetime('now', ? || ' minutes') LIMIT 50",
                    (f"-{minutes_back}",),
                ).fetchall()
                alerts = [
                    {
                        "id": row[0],
                        "severity": row[1],
                        "message": row[2],
                        "timestamp": row[3],
                        "cost_inr": row[4] or 0.0,
                    }
                    for row in rows
                ]
        except sqlite3.OperationalError as exc:
            logger.warning("AlertRenderAgent: SQLite query failed: %s", exc)
        return {
            "result": {"alerts": alerts, "alert_count": len(alerts)},
            "meta": {
                "agent": self.name,
                "cost_inr": 0.0,
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }


class KPIUpdateAgent(BaseAgent):
    name = "KPIUpdateAgent"
    domain = "dashboard"
    capabilities = {"DASH_KPI_UPDATE"}

    async def execute(self, task: dict) -> dict:
        trace_id = task.get("trace_id", "")
        monthly_cost_inr: float = 0.0
        total_log_entries: int = 0
        error_rate: float = 0.0
        try:
            with sqlite3.connect(str(SQLITE_PATH), timeout=5.0) as conn:
                row = conn.execute(
                    "SELECT SUM(cost_inr) FROM swarm_logs "
                    "WHERE timestamp >= datetime('now', '-30 days')"
                ).fetchone()
                monthly_cost_inr = float(row[0] or 0.0)

                row2 = conn.execute("SELECT COUNT(*) FROM swarm_logs").fetchone()
                total_log_entries = int(row2[0] or 0)

                row3 = conn.execute(
                    "SELECT COUNT(*) FROM swarm_logs WHERE severity IN ('CRITICAL','ERROR')"
                ).fetchone()
                error_count = int(row3[0] or 0)
                error_rate = round(error_count / max(1, total_log_entries), 4)
        except sqlite3.OperationalError as exc:
            logger.warning("KPIUpdateAgent: SQLite query failed: %s", exc)
        return {
            "result": {
                "monthly_cost_inr": monthly_cost_inr,
                "total_log_entries": total_log_entries,
                "error_rate": error_rate,
            },
            "meta": {
                "agent": self.name,
                "cost_inr": 0.0,
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }
