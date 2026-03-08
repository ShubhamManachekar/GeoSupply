"""
GeoSupply AI — Central Configuration
FA v2 | All constants, thresholds, and locked values.
NEVER import API keys directly — use SecurityAgent.get_key()
"""

from __future__ import annotations

import os
from pathlib import Path
from enum import Enum, IntEnum


# ============================================================
# PATHS
# ============================================================
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
CHROMADB_DIR = DATA_DIR / "chromadb"
SQLITE_PATH = DATA_DIR / "geosupply.db"
BACKUP_DIR = DATA_DIR / "backups"
LOG_DIR = DATA_DIR / "logs"

# ============================================================
# LOCKED VALUES — NEVER CHANGE WITHOUT ARCHITECTURE REVIEW
# ============================================================
HALLUCINATION_FLOOR: float = 0.70          # LOCKED — minimum confidence
BUDGET_CAP_INR: float = 500.0             # LOCKED — monthly max spend
COST_ALERT_WARN_DAILY_INR: float = 250.0
COST_ALERT_CRITICAL_DAILY_INR: float = 270.0
COST_ALERT_WARN_MONTHLY_INR: float = 400.0
COST_ALERT_CRITICAL_MONTHLY_INR: float = 450.0

# ============================================================
# LLM TIER ROUTING
# ============================================================
class LLMTier(IntEnum):
    """Three-tier LLM routing: Tier 1 (3b) → Tier 2 (14b) → Tier 3 (20b)"""
    CPU_ONLY = 0     # No LLM — ingestion, ML, dashboard workers
    SMALL_3B = 1     # llama3.2:3b + STATIC decoder — schema-strict
    MEDIUM_14B = 2   # qwen2.5:14b — translation, network, propaganda
    LARGE_20B = 3    # GPT-OSS:20b — verification, RAG, briefs


LLM_MODELS: dict[int, str] = {
    LLMTier.SMALL_3B: "llama3.2:3b",
    LLMTier.MEDIUM_14B: "qwen2.5:14b",
    LLMTier.LARGE_20B: "gpt-oss:20b",
}

GROQ_MODELS: dict[int, str] = {
    LLMTier.SMALL_3B: "llama-3.2-3b-preview",
    LLMTier.MEDIUM_14B: "qwen-2.5-14b",
    LLMTier.LARGE_20B: "llama-3.3-70b-versatile",
}

# ============================================================
# STATIC DECODER CONFIG
# ============================================================
STATIC_INPUT_TOKEN_LIMIT: int = 2048      # Hard limit for Tier-1
STATIC_INPUT_TOKEN_WARN: int = 1500       # Warning threshold
STATIC_MANDATORY_WORKERS: frozenset[str] = frozenset({
    "SentimentWorker", "NERWorker", "ClaimWorker",
    "SourceCredWorker", "CyberThreatWorker", "SupplierWorker",
    "SanctionsWorker",
})
STATIC_MANDATORY_SUBAGENTS: frozenset[str] = frozenset({
    "SourceFeedbackSubAgent", "AuditSampleSubAgent",
})

# ============================================================
# WORKER CONFIG
# ============================================================
WORKER_MAX_RETRIES: int = 3
WORKER_DEFAULT_TIMEOUT_S: int = 60
CIRCUIT_BREAKER_FAILURES: int = 5
CIRCUIT_BREAKER_OPEN_S: int = 60
CIRCUIT_BREAKER_HALF_OPEN_PROBE_S: int = 300

INTERNAL_BREAKER_TIMEOUT_MAP: dict[str, int] = {
    "FactCheckAgent": 30,
    "AuditorAgent": 20,
    "BriefSynthSubAgent": 60,
}
INTERNAL_BREAKER_MAX_FAILURES: int = 3

# ============================================================
# AGENT STATE MACHINE (FA v1 G2)
# ============================================================
class AgentState(str, Enum):
    IDLE = "IDLE"
    BUSY = "BUSY"
    DONE = "DONE"
    ERROR = "ERROR"
    RECOVERY = "RECOVERY"


VALID_STATE_TRANSITIONS: dict[str, set[str]] = {
    AgentState.IDLE: {AgentState.BUSY},
    AgentState.BUSY: {AgentState.DONE, AgentState.ERROR},
    AgentState.DONE: {AgentState.IDLE},
    AgentState.ERROR: {AgentState.RECOVERY},
    AgentState.RECOVERY: {AgentState.IDLE},
}

# ============================================================
# KNOWLEDGE GRAPH (FA v1 G5)
# ============================================================
KG_WRITE_BUFFER_BATCH_SIZE: int = 50
KG_WRITE_BUFFER_MAX_DEPTH: int = 500
KG_DEDUP_WINDOW_SECONDS: int = 3600       # 1-hour sliding window
KG_CANARY_SAMPLE_SIZE: int = 10           # Queries for canary check
KG_BACKUP_INTERVAL_HOURS: int = 6         # RPO = 6hr

# ============================================================
# CHANNEL FINGERPRINT (FA v1 G6)
# ============================================================
CHANNEL_BASELINE_MIN_MESSAGES: int = 100
CHANNEL_KL_WARN_THRESHOLD: float = 0.30
CHANNEL_KL_SUSPEND_THRESHOLD: float = 0.60
CHANNEL_SILENT_ALERT_DAYS: int = 7

# ============================================================
# SOURCE CREDIBILITY
# ============================================================
SOURCE_PENALTY_LEVELS: list[float] = [-0.05, -0.10, -0.20]  # 3 strikes
SOURCE_PENALTY_WINDOW_DAYS: int = 30
SOURCE_PERMANENT_FLAG_STRIKES: int = 4

# ============================================================
# SUMMARIZATION VERIFICATION
# ============================================================
SEVERITY_BANDS: dict[str, tuple[float, float]] = {
    "minimal": (0.0, 0.30),
    "low": (0.30, 0.50),
    "moderate": (0.50, 0.70),
    "high": (0.70, 0.85),
    "critical": (0.85, 1.00),
}

# ============================================================
# MOA FALLBACK (FA v1 G8)
# ============================================================
MOA_SCORING_WEIGHTS: dict[str, float] = {
    "factcheck_score": 0.4,
    "source_credibility_avg": 0.3,
    "claim_evidence_ratio": 0.3,
}
MOA_MERGE_THRESHOLD: float = 0.05         # If top 2 within this, merge
MOA_ESCALATE_THRESHOLD: float = 0.50      # Below this → Level 3 manual

# ============================================================
# SECURITY (FA v1 G3)
# ============================================================
KEY_ROTATION_DAYS: int = 30
EVENT_SIGNING_ALGO: str = "HMAC-SHA256"
EVENT_KEY_GRACE_WINDOW_S: int = 60        # Old key valid during rotation
ADMIN_CLI_MAX_ATTEMPTS: int = 5
ADMIN_CLI_LOCKOUT_MINUTES: int = 30

# ============================================================
# JWT (FA v1 G7)
# ============================================================
JWT_ALGORITHM: str = "HS256"
JWT_DEFAULT_EXPIRY_S: int = 900           # 15 min
JWT_OVERRIDE_EXPIRY_S: int = 300          # 5 min for override page
JWT_SCOPES: frozenset[str] = frozenset({
    "portal", "portal:read", "portal:admin",
})

# ============================================================
# SCHEMA VERSIONING (FA v1 G4)
# ============================================================
SCHEMA_VERSIONS: dict[str, dict[str, int]] = {
    "AgentMessage": {"current": 1, "min_supported": 1},
    "TaskPacket": {"current": 1, "min_supported": 1},
    "GeoRiskScore": {"current": 1, "min_supported": 1},
    "CyberThreatScore": {"current": 1, "min_supported": 1},
    "SentimentOutput": {"current": 1, "min_supported": 1},
    "NEROutput": {"current": 1, "min_supported": 1},
    "ClaimOutput": {"current": 1, "min_supported": 1},
    "SourceCredOutput": {"current": 1, "min_supported": 1},
    "SupplierScore": {"current": 1, "min_supported": 1},
    "SanctionsOutput": {"current": 1, "min_supported": 1},
    "SourceFeedbackScore": {"current": 1, "min_supported": 1},
    "AuditSample": {"current": 1, "min_supported": 1},
    "OverrideRecord": {"current": 1, "min_supported": 1},
    "LoopholeFinding": {"current": 1, "min_supported": 1},
    "LoopholeReport": {"current": 1, "min_supported": 1},
    "TweetOutput": {"current": 1, "min_supported": 1},
    "PredictionRecord": {"current": 1, "min_supported": 1},
    "BackupRecord": {"current": 1, "min_supported": 1},
    "ChannelFingerprint": {"current": 1, "min_supported": 1},
    "KnowledgeUpdateRequest": {"current": 1, "min_supported": 1},
    "CostProjection": {"current": 1, "min_supported": 1},
    "Event": {"current": 1, "min_supported": 1},
    "WorkerError": {"current": 1, "min_supported": 1},
    "GeoEventRecord": {"current": 1, "min_supported": 1},
    "GeoEventTimeline": {"current": 1, "min_supported": 1},
    # Phase 2 workers don't define new schemas (Tier 0 raw output)
    # Phase 15 schemas (#26-28): DisasterEvent, AviationTrack, MarketSignal
}

# ============================================================
# PIPELINE & OPERATIONS
# ============================================================
PIPELINE_SLA_MINUTES: int = 12
PIPELINE_DEFAULT_INTERVAL_HOURS: int = 4
MAX_PARALLEL_SESSIONS: int = 6
SUPERVISOR_MAX_QUEUE_DEPTH: int = 50

# ============================================================
# OVERRIDE MONITORING
# ============================================================
OVERRIDE_ALERT_WEEKLY_LIMIT: int = 5
OVERRIDE_SOURCE_FAVOURITISM_LIMIT: int = 3
OVERRIDE_TIME_CLUSTER_LIMIT: int = 3       # In 1 hour
OVERRIDE_FACTCHECK_BYPASS_LIMIT: float = 0.20  # 20%

# ============================================================
# BACKUP & DR
# ============================================================
BACKUP_ENCRYPTION_ALGO: str = "AES-256"
DR_RTO_HOURS: int = 4
DR_RPO_HOURS: int = 6

# ============================================================
# ENVIRONMENT HELPERS
# ============================================================
def get_env() -> str:
    """Get current environment: development, staging, production."""
    return os.getenv("GEOSUPPLY_ENV", "development")


def is_production() -> bool:
    return get_env() == "production"


def get_log_level() -> str:
    return os.getenv("GEOSUPPLY_LOG_LEVEL", "INFO")
