"""
GeoSupply AI — Shared Test Fixtures (FA v1 G10)
Test configuration and common fixtures.
"""

import pytest

from tests.fixtures.mock_eventbus import InMemoryEventBus


@pytest.fixture
def event_bus():
    """InMemoryEventBus for testing without side effects."""
    return InMemoryEventBus()


@pytest.fixture
def trace_id():
    """Standard trace ID for tests."""
    return "test-trace-001"


@pytest.fixture
def sample_agent_message():
    """Sample AgentMessage dict for testing."""
    from geosupply.schemas import AgentMessage
    return AgentMessage(
        trace_id="test-trace-001",
        source="TestSourceAgent",
        target="TestTargetAgent",
        payload={"action": "test"},
        cost_inr=0.0,
    )
