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

SEND_TIMEOUT_S = 5.0  # a client that can't accept a frame in 5s is treated as dead


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

    async def _send_one(self, ws: WebSocket, message: dict[str, Any]) -> bool:
        """Send to one client with a timeout; True on success."""
        try:
            await asyncio.wait_for(ws.send_json(message), timeout=SEND_TIMEOUT_S)
            return True
        except Exception:  # noqa: BLE001 — timeout/closed/error all mean unusable client
            return False

    async def broadcast(self, message: dict[str, Any]) -> int:
        """
        Send to all clients concurrently with a per-client timeout, then prune
        the dead. A single slow/backpressured client cannot block the others.
        """
        async with self._lock:
            clients = list(self._clients)
        if not clients:
            return 0
        results = await asyncio.gather(*(self._send_one(ws, message) for ws in clients))
        dead = [ws for ws, ok in zip(clients, results) if not ok]
        if dead:
            async with self._lock:
                for ws in dead:
                    self._clients.discard(ws)
            logger.info("OSINT WS pruned %d dead clients", len(dead))
        return sum(results)
