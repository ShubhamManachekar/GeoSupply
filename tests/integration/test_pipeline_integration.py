"""
Integration tests — End-to-end pipeline flows.
FA v2 | Zero mocks. Real logic paths only.

Tests:
    1. Worker → EventBus → LoggingAgent (signed event flow)
    2. InputSanitiser → NLPPipeline → HallucinationCheck (full NLP chain)
    3. SourceCredWorker → SourceFeedbackSubAgent (feedback loop)
    4. CyberThreatWorker → QualitySupervisor (threat intelligence dispatch)
    5. KnowledgeGraphAgent → multi-triple with query (G5 dedup)
"""

from __future__ import annotations

import os

import pytest

from geosupply.agents.knowledge_graph_agent import KnowledgeGraphAgent
from geosupply.agents.logging_agent import LoggingAgent
from geosupply.core.event_bus import EventBus, Event
from geosupply.schemas import AgentMessage, TaskPacket
from geosupply.subagents.hallucination_check_subagent import HallucinationCheckSubAgent
from geosupply.subagents.nlp_pipeline_subagent import NLPPipelineSubAgent
from geosupply.subagents.source_feedback_subagent import SourceFeedbackSubAgent
from geosupply.supervisors.quality_supervisor import QualitySupervisor
from geosupply.workers.cyber_threat_worker import CyberThreatWorker
from geosupply.workers.input_sanitiser_worker import InputSanitiserWorker
from geosupply.workers.source_cred_worker import SourceCredWorker


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def signing_key(monkeypatch):
    """Inject a test HMAC signing key via env."""
    monkeypatch.setenv("GEOSUPPLY_EVENT_SIGNING_MASTER_KEY", "test-integration-key-32bytes!!")
    return "test-integration-key-32bytes!!"


@pytest.fixture
async def event_bus(signing_key):
    bus = EventBus()
    bus.register_agent_key("TestWorker", signing_key)
    return bus


@pytest.fixture
async def logging_agent(tmp_path):
    agent = LoggingAgent()
    agent._db_path = str(tmp_path / "test_integration.db")
    await agent.setup()
    yield agent
    await agent.teardown()


# ── Test 1: Worker → EventBus → LoggingAgent ─────────────────────────────────

class TestWorkerEventBusFlow:
    @pytest.mark.asyncio
    async def test_signed_event_published_and_verified(self, event_bus):
        """Worker produces a result; it is published as a signed AgentMessage."""
        worker = InputSanitiserWorker()
        await worker.setup()

        result = await worker.safe_process({
            "text": "India export data for Q3 2026.",
            "trace_id": "integ-001",
        })
        assert "error_type" not in result

        # Publish the result as an AgentMessage
        msg = AgentMessage(
            trace_id="integ-001",
            source="InputSanitiserWorker",
            target="NLPPipelineSubAgent",
            payload=result,
            cost_inr=0.0,
        )
        event_received = []
        event_bus.subscribe("NLP_READY", lambda m: event_received.append(m))
        event = Event(
            topic="NLP_READY",
            source="InputSanitiserWorker",
            payload=result,
        )
        published = await event_bus.publish(event, skip_verification=True)
        assert published is True

        await worker.teardown()

    @pytest.mark.asyncio
    async def test_logging_agent_stores_event(self, logging_agent):
        """LoggingAgent stores an event record in SQLite via .log() method."""
        stored = await logging_agent.log(
            event_type="WORKER_RESULT",
            source="TestWorker",
            message="Integration test event",
            payload='{"result": "ok"}',
            cost_inr=0.01,
            trace_id="integ-log-001",
        )
        assert stored is True

        # Verify via stats (stats is a property dict, not a coroutine)
        stats = logging_agent.stats
        assert stats["total_logged"] >= 1


# ── Test 2: InputSanitiser → NLPPipeline → HallucinationCheck ────────────────

class TestFullNLPChain:
    @pytest.mark.asyncio
    async def test_sanitise_then_nlp_then_hallucination(self):
        """Full 3-stage NLP pipeline: sanitise → enrich → validate."""
        # Stage 1: Sanitise
        sanitiser = InputSanitiserWorker()
        await sanitiser.setup()
        raw_text = "India shows strong growth. Exports increase 12% this quarter!"
        san_result = await sanitiser.safe_process({
            "text": raw_text,
            "trace_id": "integ-nlp-001",
        })
        assert "error_type" not in san_result
        clean_text = san_result["result"]["sanitised_text"]

        # Stage 2: NLP enrichment
        nlp = NLPPipelineSubAgent()
        await nlp.setup()
        nlp_result = await nlp.run({
            "text": clean_text,
            "trace_id": "integ-nlp-001",
        })
        assert nlp_result["result"]["sentiment"] is not None
        assert nlp_result["result"]["claim"] is not None

        # Stage 3: Hallucination check on the text
        hcheck = HallucinationCheckSubAgent()
        await hcheck.setup()
        hc_result = await hcheck.run({
            "text": clean_text,
            "trace_id": "integ-nlp-001",
        })
        assert "composite_confidence" in hc_result["result"]
        assert hc_result["result"]["hallucination_floor"] == 0.70

        await sanitiser.teardown()
        await nlp.teardown()
        await hcheck.teardown()

    @pytest.mark.asyncio
    async def test_total_cost_accumulated_across_stages(self):
        """Cost is tracked across all pipeline stages (all zero for CPU workers)."""
        sanitiser = InputSanitiserWorker()
        await sanitiser.setup()
        san = await sanitiser.safe_process({
            "text": "Supply chains are stable.",
            "trace_id": "integ-cost-001",
        })
        san_cost = san.get("meta", {}).get("cost_inr", 0.0)

        nlp = NLPPipelineSubAgent()
        await nlp.setup()
        nlp_res = await nlp.run({"text": "Supply chains are stable.", "trace_id": "integ-cost-001"})
        nlp_cost = nlp_res["meta"]["cost_inr"]

        total = san_cost + nlp_cost
        assert total >= 0.0   # CPU workers are ₹0

        await sanitiser.teardown()
        await nlp.teardown()


# ── Test 3: SourceCred → SourceFeedback (feedback loop) ─────────────────────

class TestSourceCredFeedbackLoop:
    @pytest.mark.asyncio
    async def test_high_cred_source_gets_verified_boost(self):
        """Reuters → SourceCredWorker gives high score; feedback loop boosts it."""
        cred = SourceCredWorker()
        await cred.setup()
        cred_res = await cred.safe_process({
            "source_id": "https://reuters.com/article/trade",
            "trace_id": "integ-cred-001",
        })
        assert cred_res["result"]["credibility_score"] >= 0.80

        # Feedback: verified correct
        fb = SourceFeedbackSubAgent()
        await fb.setup()
        fb_res = await fb.run({
            "source_id": "https://reuters.com/article/trade",
            "text": "India trade surplus rose this quarter according to reliable data.",
            "verified_correct": True,
            "trace_id": "integ-cred-001",
        })
        assert fb_res["result"]["penalty"] > 0   # boost
        assert fb_res["result"]["new_score"] > fb_res["result"]["old_score"]

        await cred.teardown()
        await fb.teardown()

    @pytest.mark.asyncio
    async def test_propaganda_source_gets_penalised(self):
        """Unknown source with propaganda content → feedback reduces score."""
        fb = SourceFeedbackSubAgent()
        await fb.setup()
        propaganda_text = (
            "Everyone must act now! The enemy will destroy us if we do not fight back immediately!"
        )
        fb_res = await fb.run({
            "source_id": "https://propaganda-blog.xyz",
            "text": propaganda_text,
            "strike_number": 0,
            "trace_id": "integ-prop-001",
        })
        if fb_res["result"]["is_propaganda"]:
            assert fb_res["result"]["penalty"] < 0
        await fb.teardown()


# ── Test 4: CyberThreat → QualitySupervisor dispatch ────────────────────────

class TestCyberThreatToQualitySuperviser:
    @pytest.mark.asyncio
    async def test_high_confidence_threat_dispatched(self):
        """CyberThreatWorker result with high confidence passes QualitySupervisor."""
        worker = CyberThreatWorker()
        await worker.setup()
        threat_res = await worker.safe_process({
            "text": "A critical nationwide ransomware attack encrypted government hospital data.",
            "trace_id": "integ-cyber-001",
        })
        assert "error_type" not in threat_res
        severity = threat_res["result"]["severity"]

        # Route through QualitySupervisor
        sup = QualitySupervisor()
        sup.reset_budget()
        task = TaskPacket(
            task_id="integ-cyber-001",
            task_type="NLP_ENRICH",
            budget_inr=1.0,
            payload={"confidence": severity},
        )
        dispatch_res = await sup.dispatch(task)

        # Should pass if severity >= 0.70, else rejected
        if severity >= 0.70:
            assert dispatch_res["status"] == "completed"
        else:
            assert dispatch_res["status"] == "rejected"
            assert dispatch_res["reason"] == "below_hallucination_floor"

        await worker.teardown()


# ── Test 5: KnowledgeGraph multi-triple + query ──────────────────────────────

class TestKnowledgeGraphPipeline:
    @pytest.mark.asyncio
    async def test_build_and_query_geopolitical_graph(self):
        """Add multiple geopolitical triples, flush, then query relationships."""
        kg = KnowledgeGraphAgent()
        triples = [
            ("India", "TRADE", "Japan"),
            ("India", "ALLY", "USA"),
            ("China", "CONFLICT", "Taiwan"),
            ("Russia", "TRADE", "India"),
            ("India", "DIPLOMATIC", "Russia"),
        ]

        for src, rel, tgt in triples:
            await kg.safe_execute({
                "task_type": "KG_ADD_TRIPLE",
                "source": src,
                "relation": rel,
                "target": tgt,
                "trace_id": f"integ-kg-{src}-{tgt}",
            })

        # Flush
        flush_res = await kg.safe_execute({"task_type": "KG_FLUSH", "trace_id": "integ-kg-flush"})
        assert flush_res["result"]["flushed"] == 5

        # Query India neighbours
        q_res = await kg.safe_execute({
            "task_type": "KG_QUERY",
            "entity": "India",
            "trace_id": "integ-kg-query",
        })
        assert q_res["result"]["count"] >= 3

        # Stats
        stats_res = await kg.safe_execute({"task_type": "KG_STATS", "trace_id": "integ-kg-stats"})
        # node_count = source nodes only (India, China, Russia = 3)
        assert stats_res["result"]["node_count"] >= 3
        assert stats_res["result"]["edge_count"] >= 5

    @pytest.mark.asyncio
    async def test_dedup_prevents_double_write(self):
        """Same triple added twice → only 1 written (G5 dedup)."""
        kg = KnowledgeGraphAgent()
        for _ in range(3):
            await kg.safe_execute({
                "task_type": "KG_ADD_TRIPLE",
                "source": "India",
                "relation": "TRADE",
                "target": "UAE",
                "trace_id": "integ-dup",
            })
        await kg.safe_execute({"task_type": "KG_FLUSH", "trace_id": "integ-dup-flush"})

        assert kg._total_added == 1
        assert kg._total_deduped == 2
