"""Tech domain agents — Layer 3 wrappers for TechSupervisor."""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone

from geosupply.core.base_agent import BaseAgent
from geosupply.config import SQLITE_PATH

logger = logging.getLogger(__name__)


class APIHealthAgent(BaseAgent):
    name = "APIHealthAgent"
    domain = "tech"
    capabilities = {"TECH_API_HEALTH"}

    async def execute(self, task: dict) -> dict:
        trace_id = task.get("trace_id", "")
        payload = task.get("payload", task)
        endpoints: list[str] = payload.get("endpoints", [])
        results: dict[str, dict] = {}
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                for url in endpoints:
                    try:
                        resp = await client.head(url)
                        results[url] = {"reachable": True, "status_code": resp.status_code}
                    except httpx.RequestError as exc:
                        results[url] = {"reachable": False, "status_code": None, "error": str(exc)}
        except ImportError:
            logger.warning("APIHealthAgent: httpx not available, skipping health checks")
            for url in endpoints:
                results[url] = {"reachable": False, "status_code": None, "error": "httpx not installed"}
        return {
            "result": {"endpoints": results, "checked": len(results)},
            "meta": {
                "agent": self.name,
                "cost_inr": 0.0,
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }


class DBCheckAgent(BaseAgent):
    name = "DBCheckAgent"
    domain = "tech"
    capabilities = {"TECH_DB_CHECK"}

    async def execute(self, task: dict) -> dict:
        trace_id = task.get("trace_id", "")
        journal_mode = "unknown"
        tables: list[dict] = []
        healthy = False
        try:
            with sqlite3.connect(str(SQLITE_PATH), timeout=5.0) as conn:
                row = conn.execute("PRAGMA journal_mode").fetchone()
                journal_mode = row[0] if row else "unknown"
                healthy = journal_mode == "wal"
                table_rows = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
                for (tname,) in table_rows:
                    try:
                        count_row = conn.execute(f"SELECT COUNT(*) FROM {tname}").fetchone()
                        tables.append({"table": tname, "rows": int(count_row[0] or 0)})
                    except sqlite3.OperationalError:
                        tables.append({"table": tname, "rows": -1})
        except sqlite3.OperationalError as exc:
            logger.warning("DBCheckAgent: SQLite check failed: %s", exc)
        return {
            "result": {
                "journal_mode": journal_mode,
                "healthy": healthy,
                "tables": tables,
            },
            "meta": {
                "agent": self.name,
                "cost_inr": 0.0,
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }


class CacheFlushAgent(BaseAgent):
    name = "CacheFlushAgent"
    domain = "tech"
    capabilities = {"TECH_CACHE_FLUSH"}

    async def execute(self, task: dict) -> dict:
        trace_id = task.get("trace_id", "")
        cleared: list[str] = []
        try:
            from geosupply.api import dependencies
            for attr_name in dir(dependencies):
                fn = getattr(dependencies, attr_name, None)
                if fn is not None and hasattr(fn, "cache_clear"):
                    try:
                        fn.cache_clear()
                        cleared.append(attr_name)
                    except (TypeError, AttributeError) as exc:
                        logger.warning("CacheFlushAgent: cache_clear failed for %s: %s", attr_name, exc)
        except ImportError as exc:
            logger.warning("CacheFlushAgent: import failed: %s", exc)
        return {
            "result": {"cleared_functions": cleared, "cleared_count": len(cleared)},
            "meta": {
                "agent": self.name,
                "cost_inr": 0.0,
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }
