"""Unit tests for SecurityAgent — key vault, G3 signing keys, rotation."""

import os
import pytest
from unittest.mock import patch
from geosupply.agents.security_agent import SecurityAgent, KeyNotFoundError


@pytest.fixture
def agent():
    return SecurityAgent()


class TestKeyAccess:
    def test_get_key_success(self, agent):
        with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_test123"}):
            key = agent.get_key("groq")
            assert key == "gsk_test123"

    def test_get_key_unknown_service(self, agent):
        with pytest.raises(KeyNotFoundError, match="Unknown service"):
            agent.get_key("nonexistent_service")

    def test_get_key_env_not_set(self, agent):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(KeyNotFoundError, match="not set"):
                agent.get_key("groq")

    def test_access_log_tracked(self, agent):
        with patch.dict(os.environ, {"GROQ_API_KEY": "test"}):
            agent.get_key("groq")
            assert len(agent._access_log) == 1
            assert agent._access_log[0]["service"] == "groq"


class TestSigningKeys:
    def test_generate_signing_key(self, agent):
        key = agent.generate_signing_key("TestAgent")
        assert len(key) == 64  # 32 bytes = 64 hex chars
        assert agent.get_signing_key("TestAgent") == key

    def test_generate_multiple_keys(self, agent):
        k1 = agent.generate_signing_key("AgentA")
        k2 = agent.generate_signing_key("AgentB")
        assert k1 != k2

    def test_get_nonexistent_key(self, agent):
        assert agent.get_signing_key("NoSuchAgent") is None


class TestKeyRotation:
    def test_rotate_fresh_keys_nothing_rotated(self, agent):
        agent.generate_signing_key("AgentA")
        rotated = agent.rotate_event_keys()
        assert len(rotated) == 0  # Just issued, not due

    def test_keys_needing_rotation_fresh(self, agent):
        agent.generate_signing_key("AgentA")
        due = agent.get_keys_needing_rotation()
        assert len(due) == 0


class TestExecuteContract:
    @pytest.mark.asyncio
    async def test_execute_get_key(self, agent):
        with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_xxx123"}):
            result = await agent.execute({"action": "get_key", "service": "groq"})
            assert "***" in result["result"]["key"]  # Masked

    @pytest.mark.asyncio
    async def test_execute_get_key_error(self, agent):
        result = await agent.execute({"action": "get_key", "service": "bad"})
        assert "error" in result["result"]

    @pytest.mark.asyncio
    async def test_execute_generate_signing_key(self, agent):
        result = await agent.execute({
            "action": "generate_signing_key", "agent_name": "NewAgent"
        })
        assert result["result"]["key_issued"] is True

    @pytest.mark.asyncio
    async def test_execute_rotate_keys(self, agent):
        result = await agent.execute({"action": "rotate_keys"})
        assert "rotated" in result["result"]

    @pytest.mark.asyncio
    async def test_execute_unknown(self, agent):
        result = await agent.execute({"action": "bad_action"})
        assert "error" in result["result"]


class TestStats:
    def test_stats(self, agent):
        agent.generate_signing_key("X")
        s = agent.stats
        assert s["active_signing_keys"] == 1
        assert s["registered_services"] > 0


class TestAgedKeyRotation:
    """L155-159, L172: Test rotation logic with keys old enough to trigger."""

    def test_rotate_aged_keys_actually_rotates(self, agent):
        """Keys issued 31+ days ago MUST be rotated."""
        from datetime import timedelta, timezone
        agent.generate_signing_key("OldAgent")
        old_key = agent.get_signing_key("OldAgent")
        # Backdate the issued_at by 31 days
        from datetime import datetime
        agent._key_issued_at["OldAgent"] = datetime.now(timezone.utc) - timedelta(days=31)
        rotated = agent.rotate_event_keys()
        assert "OldAgent" in rotated
        new_key = agent.get_signing_key("OldAgent")
        assert new_key != old_key  # Actually changed
        assert len(new_key) == 64

    def test_rotate_mixed_ages(self, agent):
        """Only old keys rotate; fresh keys stay."""
        from datetime import timedelta, datetime, timezone
        agent.generate_signing_key("FreshAgent")
        agent.generate_signing_key("StaleAgent")
        agent._key_issued_at["StaleAgent"] = datetime.now(timezone.utc) - timedelta(days=35)
        fresh_key = agent.get_signing_key("FreshAgent")
        rotated = agent.rotate_event_keys()
        assert "StaleAgent" in rotated
        assert "FreshAgent" not in rotated
        assert agent.get_signing_key("FreshAgent") == fresh_key

    def test_keys_needing_rotation_with_aged_key(self, agent):
        """L172: get_keys_needing_rotation finds aged keys."""
        from datetime import timedelta, datetime, timezone
        agent.generate_signing_key("AgentX")
        agent._key_issued_at["AgentX"] = datetime.now(timezone.utc) - timedelta(days=30)
        due = agent.get_keys_needing_rotation()
        assert "AgentX" in due

    def test_rotation_updates_issued_at(self, agent):
        """After rotation, issued_at is reset to now."""
        from datetime import timedelta, datetime, timezone
        agent.generate_signing_key("AgentY")
        agent._key_issued_at["AgentY"] = datetime.now(timezone.utc) - timedelta(days=40)
        agent.rotate_event_keys()
        # After rotation, key should no longer need rotation
        due = agent.get_keys_needing_rotation()
        assert "AgentY" not in due
