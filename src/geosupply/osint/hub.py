"""
GeoSupply AI — OSINT WebSocket hub.

Fan-out of live snapshot updates to connected dashboard clients.
Dead connections are pruned on send failure — a slow/closed client
must never block the broadcast loop.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class OsintHub:
    """Tracks connected WebSocket clients and broadcasts JSON payloads."""

    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    @property
    def client_count(self) -> int:
        return len(self._clients)

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._clients.add(ws)
        logger.info("OSINT WS client connected (%d total)", len(self._clients))

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)
        logger.info("OSINT WS client disconnected (%d total)", len(self._clients))

    async def broadcast(self, message: dict[str, Any]) -> int:
        """Send to all clients; prune the dead. Returns delivered count."""
        async with self._lock:
            clients = list(self._clients)
        delivered = 0
        dead: list[WebSocket] = []
        for ws in clients:
            try:
                await ws.send_json(message)
                delivered += 1
            except Exception:  # noqa: BLE001 — any send failure means a dead client
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._clients.discard(ws)
            logger.info("OSINT WS pruned %d dead clients", len(dead))
        return delivered
