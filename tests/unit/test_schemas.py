"""Unit tests for all 23 Pydantic schemas — validation, schema_version, dedup_key."""

import pytest
from datetime import datetime
from geosupply.schemas import (
    ALL_SCHEMAS,
    AgentMessage, TaskPacket, GeoRiskScore, CyberThreatScore,
    SentimentOutput, NEROutput, NEREntity, ClaimOutput,
    SourceCredOutput, SupplierScore, SanctionsOutput,
    SourceFeedbackScore, AuditSample, OverrideRecord,
    LoopholeFinding, LoopholeReport, TweetOutput,
    PredictionRecord, BackupRecord, ChannelFingerprint,
    KnowledgeUpdateRequest, CostProjection, Event, WorkerError,
)


class TestSchemaCount:
    def test_23_schemas_registered(self):
        assert len(ALL_SCHEMAS) == 23


class TestSchemaVersion:
    """G4: Every schema MUST have schema_version field."""

    def test_all_schemas_have_version(self):
        for name, cls in ALL_SCHEMAS.items():
            fields = cls.model_fields
            assert "schema_version" in fields, f"{name} missing schema_version"

    def test_default_version_is_1(self):
        for name, cls in ALL_SCHEMAS.items():
            default = cls.model_fields["schema_version"].default
            assert default == 1, f"{name} schema_version default is {default}, not 1"


class TestAgentMessage:
    def test_required_fields(self):
        msg = AgentMessage(trace_id="t1", source="A", target="B", payload={})
        assert msg.source == "A"
        assert msg.cost_inr == 0.0

    def test_timestamp_auto(self):
        msg = AgentMessage(trace_id="t1", source="A", target="B", payload={})
        assert msg.timestamp is not None


class TestScoreValidators:
    def test_geo_risk_score_bounds(self):
        s = GeoRiskScore(country="IN", score=0.5, ci_low=0.3, ci_high=0.7)
        assert s.score == 0.5

    def test_geo_risk_rejects_over_1(self):
        with pytest.raises(Exception):
            GeoRiskScore(country="IN", score=1.5, ci_low=0.0, ci_high=1.0)

    def test_sentiment_output_range(self):
        s = SentimentOutput(polarity=-0.5, subjectivity=0.8, confidence=0.9)
        assert s.polarity == -0.5

    def test_sentiment_rejects_invalid(self):
        with pytest.raises(Exception):
            SentimentOutput(polarity=-2.0, subjectivity=0.5, confidence=0.5)


class TestLiteralConstraints:
    def test_cyber_threat_valid_type(self):
        t = CyberThreatScore(
            threat_type="RANSOMWARE", affected_sector="energy", severity=0.8
        )
        assert t.threat_type == "RANSOMWARE"

    def test_cyber_threat_invalid_type(self):
        with pytest.raises(Exception):
            CyberThreatScore(
                threat_type="INVALID_TYPE", affected_sector="x", severity=0.5
            )

    def test_worker_error_types(self):
        e = WorkerError(
            error_type="TIMEOUT", message="test", worker_name="W",
            trace_id="t1",
        )
        assert e.error_type == "TIMEOUT"

    def test_worker_error_invalid_type(self):
        with pytest.raises(Exception):
            WorkerError(
                error_type="NOT_A_TYPE", message="test", worker_name="W",
                trace_id="t1",
            )


class TestDedupKey:
    """G5: KnowledgeUpdateRequest dedup_key property."""

    def test_dedup_key_tuple(self):
        k = KnowledgeUpdateRequest(
            entity_source="India", entity_target="China",
            relation_type="BORDER_TENSION", confidence=0.85,
        )
        assert k.dedup_key == ("India", "China", "BORDER_TENSION")

    def test_dedup_key_equality(self):
        k1 = KnowledgeUpdateRequest(
            entity_source="A", entity_target="B",
            relation_type="R", confidence=0.5,
        )
        k2 = KnowledgeUpdateRequest(
            entity_source="A", entity_target="B",
            relation_type="R", confidence=0.9,
        )
        assert k1.dedup_key == k2.dedup_key

    def test_dedup_key_inequality(self):
        k1 = KnowledgeUpdateRequest(
            entity_source="A", entity_target="B",
            relation_type="R1", confidence=0.5,
        )
        k2 = KnowledgeUpdateRequest(
            entity_source="A", entity_target="B",
            relation_type="R2", confidence=0.5,
        )
        assert k1.dedup_key != k2.dedup_key


class TestChannelFingerprint:
    """G6: Status literals."""

    def test_valid_statuses(self):
        for status in ("PROVISIONAL", "BASELINE_COMPLETE", "DRIFT_WARN", "SUSPENDED"):
            cf = ChannelFingerprint(channel_id="ch1", status=status)
            assert cf.status == status


class TestTweetOutput:
    def test_max_length(self):
        t = TweetOutput(text="x" * 280, content_type="INSIGHT", confidence=0.9)
        assert len(t.text) == 280

    def test_exceeds_max_length(self):
        with pytest.raises(Exception):
            TweetOutput(text="x" * 281, content_type="INSIGHT", confidence=0.9)
