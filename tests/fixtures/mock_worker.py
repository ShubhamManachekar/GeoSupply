"""
GeoSupply AI — Mock Worker Factory (FA v1 G10)
Creates mock workers with sensible defaults for unit testing.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

from geosupply.core.base_worker import BaseWorker


def create_mock_worker(
    name: str = "TestWorker",
    tier: int = 0,
    capabilities: set[str] | None = None,
    process_result: dict | None = None,
    use_static: bool = False,
) -> AsyncMock:
    """
    Factory for mock workers with architecture-compliant defaults.

    Args:
        name: Worker name
        tier: LLM tier (0-3)
        capabilities: Set of capability strings
        process_result: Custom return value for process()
        use_static: Whether STATIC decoder is mandatory

    Returns:
        AsyncMock with BaseWorker spec
    """
    mock = AsyncMock(spec=BaseWorker)
    mock.name = name
    mock.tier = tier
    mock.use_static = use_static
    mock.capabilities = capabilities or {"TEST_CAP"}
    mock._is_setup = True

    mock.process.return_value = process_result or {
        "result": {"test": True},
        "meta": {
            "worker": name,
            "tier": tier,
            "cost_inr": 0.0,
        },
    }

    mock.advertise_capabilities.return_value = {
        "name": name,
        "tier": tier,
        "capabilities": sorted(capabilities or {"TEST_CAP"}),
        "use_static": use_static,
    }

    return mock
