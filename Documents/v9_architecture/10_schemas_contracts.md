# Chapter 10: Pydantic Schemas & Message Contracts

## Universal Message Contract

Every inter-agent message in GeoSupply v9 MUST follow this schema:

```python
from pydantic import BaseModel, Field
from typing import Any, Optional, Literal
from datetime import datetime

class AgentMeta(BaseModel):
    agent: str                          # Agent name that produced this
    ts: float                          # Unix timestamp
    cost_inr: float = 0.0             # Cost in INR for this operation
    session_id: str                    # Trace session identifier
    trace_id: Optional[str] = None     # Distributed trace ID (v9)
    span_id: Optional[str] = None      # Span within trace (v9)

class AgentMessage(BaseModel):
    """Universal message contract — all inter-agent communication."""
    status: Literal["success", "error"]
    data: dict[str, Any]
    meta: AgentMeta

# RULE: Never raise exceptions to callers. Always return AgentMessage.
```

---

## Core Domain Schemas

```python
class TaskPacket(BaseModel):
    """Routed by MoE Gating Network to Supervisors."""
    task_id: str
    task_type: str                     # From MoE routing table
    priority: int = 5                  # 0=P0_CRITICAL, 3=P3_LOW
    payload: dict[str, Any]
    estimated_cost_inr: float = 0.0
    tier: Optional[int] = None         # Set by MoE gate
    use_static: bool = False           # Set by MoE gate
    depends_on: list[str] = []         # Task IDs this depends on
    created_at: datetime = Field(default_factory=datetime.utcnow)
    deadline_ms: Optional[float] = None

class GeoRiskScore(BaseModel):
    """Extended in v8 with CI propagation — LOCKED."""
    point: float                       # Calibrated probability
    ci_low: float                      # 90% CI lower bound
    ci_high: float                     # 90% CI upper bound
    data_density: Literal["HIGH", "MEDIUM", "LOW", "SPARSE"]
    cyber_risk_modifier: float = 0.0   # NEW v9: cyber threat impact

class SourcePenaltyRecord(BaseModel):
    source_id: str
    old_score: float
    penalty: float                     # -0.05 per quarantine
    new_score: float
    reason: str
    timestamp: datetime
    floor: float = 0.10               # Never fully excluded

class RoutingAdvisorRecord(BaseModel):
    task_type: str
    language_code: Optional[str] = None
    topic_cluster: Optional[str] = None
    recommended: str                   # "escalate_to_tier3"
    confidence: float
    created_at: datetime
    expires_at: datetime               # 30-day expiry

class AuditRecord(BaseModel):
    worker_name: str
    schema_compliance: float
    confidence_calibration: float
    factual_consistency: float
    latency_sla: float
    data_completeness: float
    drift_vector: Literal["up", "flat", "down"]  # v8 addition
    sampling_rate: float               # 100%/30%/10%
    timestamp: datetime

class IncidentRecord(BaseModel):
    incident_type: str
    severity: Literal["INFO", "WARN", "ALERT", "CRITICAL"]
    cold_start: bool = False
    run_count: Optional[int] = None
    vector_store_size: Optional[int] = None
    degraded_mode_reason: Optional[str] = None
    resolved: bool = False
    timestamp: datetime

class CyberThreatScore(BaseModel):
    """NEW v9 — cyber threat assessment."""
    threat_id: str
    threat_type: str
    category: Literal["supply_chain", "state_sponsored", "logic_gap"]
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    confidence: float
    affected_sectors: list[str]
    affected_countries: list[str]
    attack_vector: str
    supply_chain_impact: float
    geo_risk_modifier: float
    first_seen: datetime
    last_updated: datetime

class OverrideRecord(BaseModel):
    """NEW v9 — admin manual override audit trail."""
    override_id: str
    admin_user: str
    action: str
    target: str
    old_value: str
    new_value: str
    justification: str
    auto_revert_at: Optional[datetime] = None
    timestamp: datetime
```
