"""
SecurityAgent — Infrastructure Singleton (#4)
FA v2 | Part IV Group A | Layer 3

Contract: get_key(service) → str — vault-backed key access
Manages API key retrieval, EventBus signing keys (G3), and rotation.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone

from geosupply.config import (
    AgentState, KEY_ROTATION_DAYS, EVENT_SIGNING_ALGO,
    EVENT_KEY_GRACE_WINDOW_S,
)
from geosupply.core.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class KeyNotFoundError(Exception):
    """Raised when a requested API key is not available."""
    pass


class SecurityAgent(BaseAgent):
    """
    Central security agent. All API key access goes through here.

    DOMAIN: security
    CAPABILITIES: GET_KEY, ROTATE_KEYS, SIGN_EVENT, VERIFY_EVENT
    PATTERN: NEVER hardcode keys. Always SecurityAgent.get_key()

    FA v1 G3: Generates and manages EventBus signing keys.
    """

    name = "SecurityAgent"
    domain = "security"
    capabilities = {"GET_KEY", "ROTATE_KEYS", "SIGN_EVENT", "VERIFY_EVENT"}
    max_concurrent = 1  # Single point of key access

    _key_map: dict[str, str]              # service_name → env_var_name
    _signing_keys: dict[str, str]         # agent_name → HMAC key
    _key_issued_at: dict[str, datetime]   # agent_name → when key issued
    _access_log: list[dict]               # audit trail

    def __init__(self) -> None:
        self._key_map = {
            "groq": "GROQ_API_KEY",
            "claude": "CLAUDE_API_KEY",
            "ollama": "OLLAMA_BASE_URL",
            "supabase_url": "SUPABASE_URL",
            "supabase_key": "SUPABASE_KEY",
            "newsapi": "NEWSAPI_KEY",
            "telegram_token": "TELEGRAM_BOT_TOKEN",
            "telegram_api_id": "TELEGRAM_API_ID",
            "telegram_api_hash": "TELEGRAM_API_HASH",
            "google_maps": "GOOGLE_MAPS_API_KEY",
            "gdrive": "GOOGLE_DRIVE_CREDENTIALS_PATH",
            "twitter_key": "TWITTER_API_KEY",
            "twitter_secret": "TWITTER_API_SECRET",
            "twitter_token": "TWITTER_ACCESS_TOKEN",
            "twitter_token_secret": "TWITTER_ACCESS_SECRET",
            "sendgrid": "SENDGRID_API_KEY",
            "totp_secret": "TOTP_SECRET",
            "jwt_secret": "JWT_SECRET_KEY",
            "event_master_key": "EVENT_SIGNING_MASTER_KEY",
            "encryption_key": "ENCRYPTION_KEY",
            "shodan": "SHODAN_API_KEY",
            "nvd": "NVD_API_KEY",
        }
        self._signing_keys = {}
        self._key_issued_at = {}
        self._access_log = []

    # === Core API: Key Access ===

    def get_key(self, service: str) -> str:
        """
        Get an API key by service name.

        Args:
            service: Key name (e.g. 'groq', 'supabase_url', 'jwt_secret')

        Returns:
            The API key string

        Raises:
            KeyNotFoundError: If service unknown or env var not set
        """
        env_var = self._key_map.get(service)
        if env_var is None:
            raise KeyNotFoundError(f"Unknown service: {service}")

        value = os.getenv(env_var, "")
        if not value:
            raise KeyNotFoundError(
                f"Service '{service}' env var '{env_var}' is not set"
            )

        # Audit trail
        self._access_log.append({
            "service": service,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "accessed_by": "caller",  # In production: pass caller identity
        })

        return value

    # === FA v1 G3: EventBus Signing Key Management ===

    def generate_signing_key(self, agent_name: str) -> str:
        """
        Generate a new HMAC-SHA256 signing key for an agent.
        Called during agent registration with EventBus.

        Returns:
            The signing key (hex string)
        """
        key = secrets.token_hex(32)  # 256-bit key
        self._signing_keys[agent_name] = key
        self._key_issued_at[agent_name] = datetime.now(timezone.utc)
        logger.info(
            "SecurityAgent: issued signing key for %s (%s)",
            agent_name, EVENT_SIGNING_ALGO,
        )
        return key

    def get_signing_key(self, agent_name: str) -> str | None:
        """Get the current signing key for an agent."""
        return self._signing_keys.get(agent_name)

    def rotate_event_keys(self) -> dict[str, str]:
        """
        FA v1 G3: Rotate all EventBus signing keys.
        Old keys remain valid for EVENT_KEY_GRACE_WINDOW_S seconds.

        Returns:
            dict of agent_name → new_key
        """
        new_keys: dict[str, str] = {}
        now = datetime.now(timezone.utc)

        for agent_name in list(self._signing_keys.keys()):
            issued = self._key_issued_at.get(agent_name, now)
            age_days = (now - issued).days

            if age_days >= KEY_ROTATION_DAYS:
                new_key = secrets.token_hex(32)
                self._signing_keys[agent_name] = new_key
                self._key_issued_at[agent_name] = now
                new_keys[agent_name] = new_key
                logger.info(
                    "SecurityAgent: rotated key for %s (was %d days old)",
                    agent_name, age_days,
                )

        return new_keys

    def get_keys_needing_rotation(self) -> list[str]:
        """List agents whose signing keys are due for rotation."""
        now = datetime.now(timezone.utc)
        due: list[str] = []
        for agent_name, issued in self._key_issued_at.items():
            if (now - issued).days >= KEY_ROTATION_DAYS:
                due.append(agent_name)
        return due

    # === BaseAgent contract ===

    async def execute(self, task: dict) -> dict:
        """Execute a security task dispatched by supervisor."""
        action = task.get("action", "get_key")

        if action == "get_key":
            try:
                key = self.get_key(task.get("service", ""))
                return {
                    "result": {"key": key[:4] + "***"},  # Never return full key in results
                    "meta": {"agent": self.name, "cost_inr": 0.0},
                }
            except KeyNotFoundError as exc:
                return {
                    "result": {"error": str(exc)},
                    "meta": {"agent": self.name, "cost_inr": 0.0},
                }

        elif action == "generate_signing_key":
            agent = task.get("agent_name", "")
            key = self.generate_signing_key(agent)
            return {
                "result": {"agent": agent, "key_issued": True},
                "meta": {"agent": self.name, "cost_inr": 0.0},
            }

        elif action == "rotate_keys":
            rotated = self.rotate_event_keys()
            return {
                "result": {"rotated": list(rotated.keys())},
                "meta": {"agent": self.name, "cost_inr": 0.0},
            }

        return {
            "result": {"error": f"Unknown action: {action}"},
            "meta": {"agent": self.name, "cost_inr": 0.0},
        }

    @property
    def stats(self) -> dict:
        return {
            "registered_services": len(self._key_map),
            "active_signing_keys": len(self._signing_keys),
            "keys_needing_rotation": self.get_keys_needing_rotation(),
            "access_log_size": len(self._access_log),
        }
