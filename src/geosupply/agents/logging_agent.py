"""
LoggingAgent — Infrastructure Singleton (#1)
FA v1 | Part IV Group A | Layer 3

Contract: log(event, *, cost_inr, trace_id, severity) → SQLite swarm_logs
Subscribes to EventBus for automatic event logging.
WatchdogAgent monitors this agent every 10 minutes.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from enum import IntEnum
from pathlib import Path
from typing import Any

from geosupply.config import AgentState, SQLITE_PATH, DATA_DIR
from geosupply.core.base_agent import BaseAgent
from geosupply.schemas import Event

logger = logging.getLogger(__name__)


class Severity(IntEnum):
    DEBUG = 0
    INFO = 1
    WARN = 2
    ERROR = 3
    CRITICAL = 4


# SQL for swarm_logs table
_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS swarm_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    severity TEXT NOT NULL,
    source TEXT NOT NULL,
    event_type TEXT NOT NULL,
    trace_id TEXT NOT NULL DEFAULT '',
    cost_inr REAL NOT NULL DEFAULT 0.0,
    message TEXT NOT NULL DEFAULT '',
    payload TEXT NOT NULL DEFAULT '{}'
);
"""

_CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_logs_trace ON swarm_logs(trace_id);
CREATE INDEX IF NOT EXISTS idx_logs_source ON swarm_logs(source);
CREATE INDEX IF NOT EXISTS idx_logs_severity ON swarm_logs(severity);
CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON swarm_logs(timestamp);
"""

_INSERT_SQL = """
INSERT INTO swarm_logs (timestamp, severity, source, event_type, trace_id, cost_inr, message, payload)
VALUES (?, ?, ?, ?, ?, ?, ?, ?);
"""


class LoggingAgent(BaseAgent):
    """
    Central logging agent. All swarm events flow here.

    DOMAIN: infrastructure
    CAPABILITIES: LOG_EVENT, QUERY_LOGS, LOG_COST
    MONITORS: WatchdogAgent checks every 10min

    DATA FLOW:
        Any component → EventBus → LoggingAgent → SQLite swarm_logs
        Admin CLI → LoggingAgent.query() → filtered logs
    """

    name = "LoggingAgent"
    domain = "infrastructure"
    capabilities = {"LOG_EVENT", "QUERY_LOGS", "LOG_COST"}
    max_concurrent = 1  # Single-writer for log DB

    _db_path: Path = SQLITE_PATH
    _conn: sqlite3.Connection | None = None
    _min_severity: Severity = Severity.DEBUG
    _total_logged: int = 0
    _total_cost_inr: float = 0.0

    def __init__(self, db_path: Path | None = None, min_severity: Severity = Severity.DEBUG):
        self._db_path = db_path or SQLITE_PATH
        self._min_severity = min_severity
        self._conn = None
        self._total_logged = 0
        self._total_cost_inr = 0.0

    async def setup(self) -> None:
        """Initialise SQLite connection and create swarm_logs table."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute(_CREATE_TABLE_SQL)
        self._conn.executescript(_CREATE_INDEX_SQL)
        self._conn.commit()
        logger.info("LoggingAgent: initialised at %s", self._db_path)

    async def teardown(self) -> None:
        """Close SQLite connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
        logger.info("LoggingAgent: shut down (logged %d entries)", self._total_logged)

    # === Core API ===

    async def log(
        self,
        event_type: str,
        *,
        source: str = "unknown",
        message: str = "",
        payload: str = "{}",
        cost_inr: float = 0.0,
        trace_id: str = "",
        severity: Severity = Severity.INFO,
    ) -> bool:
        """
        Log an event to swarm_logs.

        Returns True if logged, False if filtered or DB error.
        """
        if severity < self._min_severity:
            return False

        if self._conn is None:
            await self.setup()

        try:
            self._conn.execute(  # type: ignore[union-attr]
                _INSERT_SQL,
                (
                    datetime.now(timezone.utc).isoformat(),
                    severity.name,
                    source,
                    event_type,
                    trace_id,
                    cost_inr,
                    message,
                    payload,
                ),
            )
            self._conn.commit()  # type: ignore[union-attr]
            self._total_logged += 1
            self._total_cost_inr += cost_inr
            return True

        except sqlite3.Error as exc:
            logger.error("LoggingAgent: DB error: %s", exc)
            return False

    async def handle_event(self, event: Event) -> None:
        """EventBus subscriber handler. Auto-logs incoming events."""
        await self.log(
            event_type=event.topic,
            source=event.source,
            payload=str(event.payload),
            cost_inr=0.0,
            trace_id=event.payload.get("trace_id", ""),
            severity=Severity.INFO,
        )

    # === Query API ===

    async def query(
        self,
        *,
        source: str | None = None,
        severity: str | None = None,
        trace_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Query swarm_logs with optional filters."""
        if self._conn is None:
            return []

        conditions: list[str] = []
        params: list[Any] = []

        if source:
            conditions.append("source = ?")
            params.append(source)
        if severity:
            conditions.append("severity = ?")
            params.append(severity)
        if trace_id:
            conditions.append("trace_id = ?")
            params.append(trace_id)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"SELECT * FROM swarm_logs {where} ORDER BY id DESC LIMIT ?"
        params.append(limit)

        cursor = self._conn.execute(sql, params)
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    # === BaseAgent contract ===

    async def execute(self, task: dict) -> dict:
        """Execute a logging task dispatched by supervisor."""
        action = task.get("action", "log")

        if action == "log":
            success = await self.log(
                event_type=task.get("event_type", "UNKNOWN"),
                source=task.get("source", "unknown"),
                message=task.get("message", ""),
                cost_inr=task.get("cost_inr", 0.0),
                trace_id=task.get("trace_id", ""),
                severity=Severity[task.get("severity", "INFO")],
            )
            return {
                "result": {"logged": success},
                "meta": {"agent": self.name, "cost_inr": 0.0},
            }

        elif action == "query":
            rows = await self.query(
                source=task.get("source"),
                severity=task.get("severity"),
                trace_id=task.get("trace_id"),
                limit=task.get("limit", 100),
            )
            return {
                "result": {"rows": rows, "count": len(rows)},
                "meta": {"agent": self.name, "cost_inr": 0.0},
            }

        return {
            "result": {"error": f"Unknown action: {action}"},
            "meta": {"agent": self.name, "cost_inr": 0.0},
        }

    @property
    def stats(self) -> dict:
        return {
            "total_logged": self._total_logged,
            "total_cost_inr": self._total_cost_inr,
            "db_path": str(self._db_path),
        }
