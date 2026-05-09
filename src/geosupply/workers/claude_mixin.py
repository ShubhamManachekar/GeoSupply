"""
ClaudeWorkerMixin — Anthropic SDK integration for Tier-2/3 workers.

Provides a shared AsyncAnthropic client (class-level, one per worker class),
ephemeral prompt caching on system prompts, INR cost calculation, and a
graceful no-op fallback when the SDK / API key is unavailable.

Usage:
    class MyWorker(ClaudeWorkerMixin, BaseWorker):
        _model = "claude-haiku-4-5"
        _max_tokens = 512

        async def process(self, input_data: dict) -> dict:
            text, cost = await self._call_claude(SYSTEM, user_msg)
            ...
"""
from __future__ import annotations

import logging
import os
from functools import cached_property
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import anthropic as _anthropic

logger = logging.getLogger(__name__)

# Pricing (USD per 1M tokens) — Haiku 4.5
_INPUT_USD_PER_M = 1.00
_OUTPUT_USD_PER_M = 5.00
_CACHE_WRITE_USD_PER_M = 1.25   # 25% surcharge for writing cache
_CACHE_READ_USD_PER_M = 0.10    # 90% discount for reading cache
_USD_TO_INR = 85.0


def _tokens_to_inr(
    input_tokens: int,
    output_tokens: int,
    cache_creation_tokens: int = 0,
    cache_read_tokens: int = 0,
) -> float:
    usd = (
        input_tokens * _INPUT_USD_PER_M / 1_000_000
        + output_tokens * _OUTPUT_USD_PER_M / 1_000_000
        + cache_creation_tokens * _CACHE_WRITE_USD_PER_M / 1_000_000
        + cache_read_tokens * _CACHE_READ_USD_PER_M / 1_000_000
    )
    return round(usd * _USD_TO_INR, 6)


class ClaudeWorkerMixin:
    """
    Mix into any BaseWorker subclass to get a shared AsyncAnthropic client
    with ephemeral prompt caching and INR cost reporting.

    Class attributes (override in subclass as needed):
        _model       — Anthropic model alias (default: claude-haiku-4-5)
        _max_tokens  — per-call token ceiling (default: 1024)
    """

    _model: str = "claude-haiku-4-5"
    _max_tokens: int = 1024

    @cached_property
    def _claude_client(self) -> "_anthropic.AsyncAnthropic | None":
        """Lazy-init the Anthropic async client. Returns None if SDK absent or no key."""
        if not os.getenv("ANTHROPIC_API_KEY"):
            logger.debug("ClaudeWorkerMixin: ANTHROPIC_API_KEY not set — Claude disabled")
            return None
        try:
            import anthropic
            return anthropic.AsyncAnthropic()
        except ImportError:
            logger.debug("ClaudeWorkerMixin: anthropic package not installed — Claude disabled")
            return None

    async def _call_claude(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int | None = None,
    ) -> tuple[str, float]:
        """
        Call the Anthropic Messages API with ephemeral system-prompt caching.

        Returns:
            (response_text, cost_inr) — both are "" / 0.0 on any failure.
        """
        client = self._claude_client
        if client is None:
            return "", 0.0

        try:
            import anthropic

            response = await client.messages.create(
                model=self._model,
                max_tokens=max_tokens or self._max_tokens,
                system=[
                    {
                        "type": "text",
                        "text": system_prompt,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[{"role": "user", "content": user_message}],
            )

            text = response.content[0].text if response.content else ""
            usage = response.usage
            cost = _tokens_to_inr(
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cache_creation_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
                cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
            )
            return text, cost

        except anthropic.AuthenticationError:
            logger.warning("ClaudeWorkerMixin: invalid ANTHROPIC_API_KEY")
            return "", 0.0
        except anthropic.APIError as exc:
            logger.warning("ClaudeWorkerMixin: API error — %s", exc)
            return "", 0.0
        except Exception as exc:
            logger.warning("ClaudeWorkerMixin: unexpected error — %s", exc)
            return "", 0.0
