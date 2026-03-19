"""Tests for CyberThreatWorker."""

import pytest

from geosupply.workers.cyber_threat_worker import CyberThreatWorker


@pytest.fixture
async def worker():
    w = CyberThreatWorker()
    await w.setup()
    yield w
    await w.teardown()


class TestCyberThreatWorkerProcess:
    @pytest.mark.asyncio
    async def test_detects_ransomware(self, worker):
        text = "A ransomware attack encrypted hospital files and demanded payment."
        res = await worker.process({"text": text, "trace_id": "t-rw"})
        assert "error_type" not in res
        assert res["result"]["threat_type"] == "RANSOMWARE"
        assert res["result"]["mitre_attack_id"] == "T1486"

    @pytest.mark.asyncio
    async def test_detects_gps_jamming(self, worker):
        text = "GPS signal spoofing near the Strait of Hormuz disrupted navigation."
        res = await worker.process({"text": text, "trace_id": "t-gps"})
        assert "error_type" not in res
        assert res["result"]["threat_type"] == "GPS_JAMMING"

    @pytest.mark.asyncio
    async def test_detects_state_apt(self, worker):
        text = "An advanced persistent threat group linked to a nation-state attacked the power grid."
        res = await worker.process({"text": text, "trace_id": "t-apt"})
        assert "error_type" not in res
        assert res["result"]["threat_type"] == "STATE_APT"
        assert res["result"]["mitre_attack_id"] == "T1566"

    @pytest.mark.asyncio
    async def test_detects_ddos(self, worker):
        text = "A massive DDoS attack flooded banking servers with traffic."
        res = await worker.process({"text": text, "trace_id": "t-ddos"})
        assert "error_type" not in res
        assert res["result"]["threat_type"] == "DDoS"

    @pytest.mark.asyncio
    async def test_detects_data_breach(self, worker):
        text = "A major data breach exposed credential leaks from a finance database dump."
        res = await worker.process({"text": text, "trace_id": "t-db"})
        assert "error_type" not in res
        assert res["result"]["threat_type"] == "DATA_BREACH"

    @pytest.mark.asyncio
    async def test_detects_scada(self, worker):
        text = "A SCADA system used by an electricity utility was compromised via OT network."
        res = await worker.process({"text": text, "trace_id": "t-scada"})
        assert "error_type" not in res
        assert res["result"]["threat_type"] == "SCADA"

    @pytest.mark.asyncio
    async def test_india_impact_flagged_when_india_mentioned(self, worker):
        text = "A ransomware attack hit critical infrastructure in India causing widespread disruption."
        res = await worker.process({"text": text, "trace_id": "t-india"})
        assert "error_type" not in res
        assert "IN" in res["result"]["geographic_scope"]
        assert "HIGH" in res["result"]["india_impact"]

    @pytest.mark.asyncio
    async def test_no_threat_pattern_returns_error(self, worker):
        text = "The weather in Mumbai was pleasant today with light showers."
        res = await worker.process({"text": text, "trace_id": "t-none"})
        assert res["error_type"] == "INPUT_INVALID"
        assert "No recognisable cyber threat" in res["message"]

    @pytest.mark.asyncio
    async def test_missing_text_returns_error(self, worker):
        res = await worker.process({"trace_id": "t-miss"})
        assert res["error_type"] == "INPUT_INVALID"
        assert res["worker_name"] == "CyberThreatWorker"

    @pytest.mark.asyncio
    async def test_sanitised_text_preferred(self, worker):
        res = await worker.process({
            "text": "no threat here",
            "sanitised_text": "A DDoS attack flooded the server with botnet flood traffic.",
            "trace_id": "t-san",
        })
        assert "error_type" not in res
        assert res["result"]["threat_type"] == "DDoS"

    @pytest.mark.asyncio
    async def test_result_fields_complete(self, worker):
        res = await worker.process({
            "text": "Ransomware encrypted files across major Indian hospitals.",
            "trace_id": "t-fields",
        })
        result = res["result"]
        for field in ("threat_type", "affected_sector", "severity",
                      "geographic_scope", "india_impact", "mitre_attack_id"):
            assert field in result

    @pytest.mark.asyncio
    async def test_severity_amplified_by_critical_keywords(self, worker):
        text = "A critical and severe nationwide ransomware attack crippled government and military hospitals."
        res = await worker.process({"text": text, "trace_id": "t-sev"})
        assert "error_type" not in res
        assert res["result"]["severity"] > 0.50


class TestCyberThreatWorkerMeta:
    def test_capabilities(self):
        w = CyberThreatWorker()
        caps = w.advertise_capabilities()
        assert caps["tier"] == 1
        assert caps["use_static"] is True
        assert "CYBER_THREAT_SCORE" in caps["capabilities"]
        assert "MITRE_MAP" in caps["capabilities"]
