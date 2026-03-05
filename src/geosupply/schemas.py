"""
GeoSupply AI — All 23 Pydantic v2 Schemas (FA v1)
Part X: Registry — every schema used by the swarm.

Schema #1-22: v10 base schemas
Schema #23: WorkerError (FA v1 G9)

Every schema has schema_version field (FA v1 G4 — SchemaVersionManager).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    """Timezone-aware UTC now (Python 3.14+ compatible)."""
    return datetime.now(timezone.utc)


# ============================================================
# Schema #1: AgentMessage — Universal inter-agent communication
# Used by: ALL components
# ============================================================
class AgentMessage(BaseModel):
    """Every message between agents uses this envelope."""
    schema_version: int = 1
    trace_id: str
    source: str                          # sending agent/worker name
    target: str                          # receiving agent/worker name
    payload: dict                        # task-specific data
    cost_inr: float = 0.0               # cost attributed to this message
    timestamp: datetime = Field(default_factory=_utcnow)


# ============================================================
# Schema #2: TaskPacket — SwarmMaster task dispatch
# Used by: SwarmMaster orchestrator
# ============================================================
class TaskPacket(BaseModel):
    schema_version: int = 1
    task_id: str
    task_type: str                       # matches MoE routing table key
    priority: Literal["P0", "P1", "P2", "P3"] = "P1"
    budget_inr: float = 10.0            # max spend for this task
    timeout_s: int = 60
    payload: dict = Field(default_factory=dict)
    dependencies: list[str] = Field(default_factory=list)  # task_ids


# ============================================================
# Schema #3: GeoRiskScore — Geopolitical risk output
# Used by: Intel workers
# ============================================================
class GeoRiskScore(BaseModel):
    schema_version: int = 1
    country: str
    score: float = Field(ge=0.0, le=1.0)
    ci_low: float = Field(ge=0.0, le=1.0)    # confidence interval
    ci_high: float = Field(ge=0.0, le=1.0)
    data_density: int = 0                      # number of sources used
    timestamp: datetime = Field(default_factory=_utcnow)


# ============================================================
# Schema #4: CyberThreatScore — Cyber threat intelligence
# Used by: CyberThreatWorker
# ============================================================
class CyberThreatScore(BaseModel):
    schema_version: int = 1
    threat_type: Literal[
        "RANSOMWARE", "GPS_JAMMING", "STATE_APT", "DDoS",
        "DATA_BREACH", "SUPPLY_CHAIN_ATTACK", "CABLE_CUT", "SCADA",
    ]
    affected_sector: str
    severity: float = Field(ge=0.0, le=1.0)
    geographic_scope: list[str] = Field(default_factory=list)
    india_impact: str = ""
    mitigation_status: str = ""
    mitre_attack_id: str = ""


# ============================================================
# Schema #5: SentimentOutput — STATIC decoder mandatory
# Used by: SentimentWorker
# ============================================================
class SentimentOutput(BaseModel):
    schema_version: int = 1
    polarity: float = Field(ge=-1.0, le=1.0)
    subjectivity: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)


# ============================================================
# Schema #6: NEROutput — STATIC decoder mandatory
# Used by: NERWorker
# ============================================================
class NEREntity(BaseModel):
    """Single named entity."""
    text: str
    entity_type: str                     # PERSON, ORG, GPE, LOC, etc.
    span_start: int
    span_end: int
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)


class NEROutput(BaseModel):
    schema_version: int = 1
    entities: list[NEREntity] = Field(default_factory=list)


# ============================================================
# Schema #7: ClaimOutput — STATIC decoder mandatory
# Used by: ClaimWorker
# ============================================================
class ClaimOutput(BaseModel):
    schema_version: int = 1
    claim_text: str
    claim_type: Literal[
        "FACTUAL", "PREDICTIVE", "CAUSAL", "OPINION", "STATISTICAL",
    ]
    evidence_needed: bool = True


# ============================================================
# Schema #8: SourceCredOutput — STATIC decoder mandatory
# Used by: SourceCredWorker
# ============================================================
class SourceCredOutput(BaseModel):
    schema_version: int = 1
    source_id: str
    credibility_score: float = Field(ge=0.0, le=1.0)
    history: list[str] = Field(default_factory=list)  # recent events


# ============================================================
# Schema #9: SupplierScore — STATIC decoder mandatory
# Used by: SupplierWorker
# ============================================================
class SupplierScore(BaseModel):
    schema_version: int = 1
    supplier_id: str
    risk_score: float = Field(ge=0.0, le=1.0)
    dependencies: list[str] = Field(default_factory=list)


# ============================================================
# Schema #10: SanctionsOutput — STATIC decoder mandatory
# Used by: SanctionsWorker
# ============================================================
class SanctionsOutput(BaseModel):
    schema_version: int = 1
    entity_name: str
    sanctioned_by: list[str] = Field(default_factory=list)
    sanction_type: str = ""


# ============================================================
# Schema #11: SourceFeedbackScore
# Used by: SourceFeedbackSubAgent
# ============================================================
class SourceFeedbackScore(BaseModel):
    schema_version: int = 1
    source_id: str
    old_score: float = Field(ge=0.0, le=1.0)
    new_score: float = Field(ge=0.0, le=1.0)
    penalty: float = 0.0
    reason: str = ""


# ============================================================
# Schema #12: AuditSample
# Used by: AuditorAgent
# ============================================================
class AuditSample(BaseModel):
    schema_version: int = 1
    sample_id: str
    pipeline_output: dict = Field(default_factory=dict)
    audit_result: Literal["PASS", "FAIL", "WARN"] = "PASS"
    sampling_rate: float = Field(ge=0.0, le=1.0, default=0.05)


# ============================================================
# Schema #13: OverrideRecord
# Used by: Admin CLI
# ============================================================
class OverrideRecord(BaseModel):
    schema_version: int = 1
    admin_id: str
    action: str                          # halt, release, approve, rollback, etc.
    target: str                          # what was overridden
    reason: str
    timestamp: datetime = Field(default_factory=_utcnow)
    totp_verified: bool = False


# ============================================================
# Schema #14: LoopholeFinding
# Used by: LoopholeHunterAgent
# ============================================================
class LoopholeFinding(BaseModel):
    schema_version: int = 1
    check_id: str                        # e.g. "LOGIC-001", "SEC-003"
    name: str
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    layer: str
    details: str = ""
    recommendation: str = ""


# ============================================================
# Schema #15: LoopholeReport
# Used by: LoopholeHunterAgent
# ============================================================
class LoopholeReport(BaseModel):
    schema_version: int = 1
    timestamp: datetime = Field(default_factory=_utcnow)
    total_checks: int = 24
    passed: int = 0
    failed: int = 0
    findings: list[LoopholeFinding] = Field(default_factory=list)


# ============================================================
# Schema #16: TweetOutput
# Used by: ContentGeneratorAgent
# ============================================================
class TweetOutput(BaseModel):
    schema_version: int = 1
    text: str = Field(max_length=280)
    content_type: Literal["PREDICTION", "INSIGHT", "DATA_VIZ", "THREAD"]
    confidence: float = Field(ge=0.0, le=1.0)
    hashtags: list[str] = Field(default_factory=list)


# ============================================================
# Schema #17: PredictionRecord
# Used by: PredictionAgent
# ============================================================
class PredictionRecord(BaseModel):
    schema_version: int = 1
    prediction: str
    confidence: float = Field(ge=0.0, le=1.0)
    target_date: datetime
    category: Literal[
        "GEOPOLITICAL_RISK", "SUPPLY_CHAIN_STRESS",
        "TRADE_FLOW", "COMMODITY_PRICE",
    ]
    actual_outcome: str | None = None    # filled after target_date


# ============================================================
# Schema #18: BackupRecord
# Used by: BackupWorker
# ============================================================
class BackupRecord(BaseModel):
    schema_version: int = 1
    target: str                          # what was backed up
    timestamp: datetime = Field(default_factory=_utcnow)
    size_mb: float = 0.0
    encrypted: bool = True               # AES-256 always
    gcs_path: str = ""                   # Google Drive path


# ============================================================
# Schema #19: ChannelFingerprint (FA v1 G6)
# Used by: ChannelFingerprintWorker
# ============================================================
class ChannelFingerprint(BaseModel):
    schema_version: int = 1
    channel_id: str
    dimensions: dict = Field(default_factory=dict)  # fingerprint vectors
    baseline_hash: str = ""
    drift_score: float = 0.0             # KL divergence from baseline
    status: Literal[
        "PROVISIONAL", "BASELINE_COMPLETE", "DRIFT_WARN", "SUSPENDED",
    ] = "PROVISIONAL"


# ============================================================
# Schema #20: KnowledgeUpdateRequest (FA v1 G5 dedup key)
# Used by: KnowledgeGraphAgent
# ============================================================
class KnowledgeUpdateRequest(BaseModel):
    schema_version: int = 1
    entity_source: str                   # ┐
    entity_target: str                   # ├ dedup key (G5)
    relation_type: str                   # ┘
    confidence: float = Field(ge=0.0, le=1.0)
    timestamp: datetime = Field(default_factory=_utcnow)

    @property
    def dedup_key(self) -> tuple[str, str, str]:
        """FA v1 G5: Dedup key for write-buffer batching."""
        return (self.entity_source, self.entity_target, self.relation_type)


# ============================================================
# Schema #21: CostProjection
# Used by: CostProjectionAgent
# ============================================================
class CostProjection(BaseModel):
    schema_version: int = 1
    daily_inr: float = 0.0
    weekly_inr: float = 0.0
    monthly_inr: float = 0.0
    alert_level: Literal["NORMAL", "WARN", "ALERT", "CRITICAL"] = "NORMAL"


# ============================================================
# Schema #22: Event (FA v1 G3 — signed)
# Used by: EventBus
# ============================================================
class Event(BaseModel):
    schema_version: int = 1
    topic: str
    source: str                          # agent/worker name
    payload: dict = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=_utcnow)
    signature: str = ""                  # HMAC-SHA256 (G3)


# ============================================================
# Schema #23: WorkerError (FA v1 G9)
# Used by: ALL workers on failure
# ============================================================
class WorkerError(BaseModel):
    """Returned by any worker on failure instead of raw exceptions.
    Ensures all errors are typed, costed, and traceable."""
    schema_version: int = 1
    error_type: Literal[
        "TIMEOUT", "API_FAILURE", "SCHEMA_VIOLATION",
        "INPUT_INVALID", "BUDGET_EXCEEDED", "INTERNAL",
    ]
    message: str
    worker_name: str
    retry_count: int = 0
    cost_inr: float = 0.0
    trace_id: str = ""
    timestamp: datetime = Field(default_factory=_utcnow)


# ============================================================
# ALL SCHEMAS — export list for schema version manager
# ============================================================
ALL_SCHEMAS: dict[str, type[BaseModel]] = {
    "AgentMessage": AgentMessage,
    "TaskPacket": TaskPacket,
    "GeoRiskScore": GeoRiskScore,
    "CyberThreatScore": CyberThreatScore,
    "SentimentOutput": SentimentOutput,
    "NEROutput": NEROutput,
    "ClaimOutput": ClaimOutput,
    "SourceCredOutput": SourceCredOutput,
    "SupplierScore": SupplierScore,
    "SanctionsOutput": SanctionsOutput,
    "SourceFeedbackScore": SourceFeedbackScore,
    "AuditSample": AuditSample,
    "OverrideRecord": OverrideRecord,
    "LoopholeFinding": LoopholeFinding,
    "LoopholeReport": LoopholeReport,
    "TweetOutput": TweetOutput,
    "PredictionRecord": PredictionRecord,
    "BackupRecord": BackupRecord,
    "ChannelFingerprint": ChannelFingerprint,
    "KnowledgeUpdateRequest": KnowledgeUpdateRequest,
    "CostProjection": CostProjection,
    "Event": Event,
    "WorkerError": WorkerError,
}
