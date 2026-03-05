# Chapter 8: STATIC Decoder & Static Method Patterns

## Design Philosophy

> **Schema validity is a compile-time guarantee, not a runtime hope.**

STATIC (Sparse Transition Matrix-Accelerated Trie) eliminates JSON schema retry loops. In v9, we extend this with a comprehensive `@staticmethod` pattern for validation, cost enforcement, and contract checking across the entire swarm.

---

## STATIC Decoder — CSR-Matrix Constrained Sampler

### How It Works

```
WITHOUT STATIC (old v7):
  llama3.2:3b generates → JSON parse fails → retry ×3 → timeout
  Average: 2.3 retries per call on complex schemas
  Wasted GPU time: ~40% at Tier 1

WITH STATIC (v8+v9):
  STATIC constrains token sampling to valid schema tokens only
  Schema violation rate: ~0%
  Per-step latency overhead: 0.033ms
  Speedup vs CPU-offloaded Trie: 948×
```

### Implementation

```python
from scipy.sparse import csr_matrix
from pydantic import BaseModel
from typing import Type
import numpy as np

class STATICDecoder:
    """
    Sparse Transition Matrix-Accelerated Trie decoder.

    Constrains LLM token generation to produce ONLY valid
    tokens according to the target Pydantic schema.

    Used by all 8 Tier-1 STATIC workers:
        SentimentWorker, NERWorker, ClaimWorker,
        SourceCredWorker, SupplierWorker, SanctionsWorker,
        SourceFeedbackSubAgent, AuditSampleSubAgent
    """

    def __init__(self):
        self._schema_cache: dict[str, csr_matrix] = {}

    @staticmethod
    def build_transition_matrix(schema: Type[BaseModel]) -> csr_matrix:
        """
        Build CSR sparse matrix from Pydantic schema.
        The matrix encodes valid token transitions — any token
        not on a valid path is masked to -inf before softmax.

        Returns: scipy CSR matrix (sparse, memory-efficient)
        Cost: One-time per schema (~2ms), cached thereafter
        """
        json_schema = schema.model_json_schema()
        # Build trie from all valid JSON paths
        # Convert trie to sparse transition matrix
        # Store as CSR for O(1) row access during generation
        ...

    @staticmethod
    def constrain_logits(logits: np.ndarray,
                         transition_matrix: csr_matrix,
                         current_state: int) -> np.ndarray:
        """
        Mask invalid tokens in logit vector.
        Only tokens on valid schema paths remain.

        Cost: 0.033ms per token step
        Schema violations: 0%
        """
        valid_tokens = transition_matrix[current_state].nonzero()[1]
        mask = np.full_like(logits, -np.inf)
        mask[valid_tokens] = 0.0
        return logits + mask

    @staticmethod
    def validate_output(output: str, schema: Type[BaseModel]) -> BaseModel:
        """
        Final validation: parse output against Pydantic schema.
        With STATIC decoder, this should NEVER fail.
        If it does, it's a bug in the transition matrix.
        """
        return schema.model_validate_json(output)

    def decode(self, model_output_fn, schema: Type[BaseModel]) -> BaseModel:
        """
        Full constrained decode pipeline.
        model_output_fn: callable that returns next-token logits
        schema: target Pydantic schema
        """
        schema_key = schema.__name__
        if schema_key not in self._schema_cache:
            self._schema_cache[schema_key] = self.build_transition_matrix(schema)

        matrix = self._schema_cache[schema_key]
        # Token-by-token constrained generation
        # Returns validated Pydantic object
        ...
```

---

## Static Method Patterns (v9 Extension)

Beyond the STATIC decoder, v9 introduces `@staticmethod` patterns for zero-allocation validation throughout the swarm.

### SchemaValidator — Static Contract Enforcement

```python
class SchemaValidator:
    """
    Static methods for validating all inter-agent contracts.
    No instance state — pure functions, zero allocation.
    """

    @staticmethod
    def validate_message_contract(message: dict) -> bool:
        """
        Validates the universal message contract:
        {
            'status': 'success' | 'error',
            'data': {...},
            'meta': {'agent': str, 'ts': float, 'cost_inr': float, 'session_id': str}
        }
        """
        required_keys = {'status', 'data', 'meta'}
        meta_keys = {'agent', 'ts', 'cost_inr', 'session_id'}
        if not required_keys.issubset(message.keys()):
            return False
        if message['status'] not in ('success', 'error'):
            return False
        if not meta_keys.issubset(message.get('meta', {}).keys()):
            return False
        return True

    @staticmethod
    def validate_geo_risk_score(score: dict) -> bool:
        """Validate GeoRiskScore has CI fields (v8 P1 requirement)."""
        required = {'point', 'ci_low', 'ci_high', 'data_density'}
        return required.issubset(score.keys())

    @staticmethod
    def validate_cost_inr(cost: float) -> bool:
        """Cost must be in INR, non-negative."""
        return isinstance(cost, (int, float)) and cost >= 0

    @staticmethod
    def validate_hallucination_floor(score: float) -> bool:
        """Score must meet HALLUCINATION_FLOOR = 0.70."""
        return score >= 0.70
```

### CostCalculator — Static INR Methods

```python
class CostCalculator:
    """Static methods for INR cost calculations. No instance state."""

    INR_PER_USD = 84  # Locked exchange rate

    @staticmethod
    def llm_cost_inr(model: str, tokens_in: int, tokens_out: int) -> float:
        """Calculate cost for an LLM call in INR."""
        rates = {
            "llama3.2:3b": 0.0,         # Local / Groq free
            "qwen2.5:14b": 0.0,         # Local
            "GPT-OSS:20b": 0.0,         # Local
            "llama-3.3-70b": 0.0,       # Groq free
            "claude-sonnet-4-6": 0.25,  # Emergency INR/call
        }
        return rates.get(model, 0.0)

    @staticmethod
    def check_budget_threshold(
        current_inr: float, period: str
    ) -> str | None:
        """
        Returns alert level if threshold exceeded.
        Thresholds: >INR 50/hr WARN, >INR 300/day ALERT, >INR 500/month CRITICAL
        """
        thresholds = {
            "hour":  (50.0, "WARN"),
            "day":   (300.0, "ALERT"),
            "month": (500.0, "CRITICAL"),
        }
        limit, level = thresholds.get(period, (float('inf'), None))
        return level if current_inr > limit else None

    @staticmethod
    def estimate_pipeline_cost_inr(task_types: list[str]) -> float:
        """Estimate total INR cost for a set of tasks before execution."""
        cost_map = {
            "EMERGENCY": 0.25,   # Claude API
            # All other tasks: INR 0 (local/Groq)
        }
        return sum(cost_map.get(t, 0.0) for t in task_types)
```

### HealthPredicates — Static Health Checks

```python
class HealthPredicates:
    """Static boolean predicates for system health. Pure functions."""

    @staticmethod
    def is_pc_available() -> bool:
        """PC RTX 5060 available Mon-Thu 10am-6pm only."""
        now = datetime.now()
        return now.weekday() < 4 and 10 <= now.hour < 18

    @staticmethod
    def is_groq_within_quota(requests_today: int) -> bool:
        """Groq free tier: 14,400 req/day."""
        return requests_today < 14400

    @staticmethod
    def is_queue_healthy(depth: int) -> bool:
        """ChromaDB write queue healthy if depth < 200."""
        return depth < 200

    @staticmethod
    def should_enter_degraded_mode(
        run_count: int, api_failures: int, budget_exceeded: bool
    ) -> bool:
        """Determine if system should enter DEGRADED_MODE."""
        return run_count < 3 or api_failures > 5 or budget_exceeded
```
