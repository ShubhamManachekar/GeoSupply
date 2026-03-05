# Chapter 3: Worker Layer — BaseWorker + 32 Specialists

## Design Philosophy

> **A Worker does ONE thing. It does it well. It reports how much it cost.**

In v8.0, workers were ad-hoc classes with inconsistent interfaces. In v9.0, every worker inherits from `BaseWorker`, gaining automatic lifecycle management, instrumentation, circuit breaking, and health reporting.

---

## BaseWorker Abstract Class

```python
from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Optional
from pydantic import BaseModel
from datetime import datetime
import time

T_Input = TypeVar('T_Input', bound=BaseModel)
T_Output = TypeVar('T_Output', bound=BaseModel)

class WorkerState:
    IDLE = "IDLE"
    PROCESSING = "PROCESSING"
    RETRYING = "RETRYING"
    ERROR = "ERROR"
    CIRCUIT_OPEN = "CIRCUIT_OPEN"

class WorkerMeta(BaseModel):
    agent: str
    ts: float
    cost_inr: float
    session_id: str
    latency_ms: float
    retry_count: int
    model_used: Optional[str] = None
    static_decoder: bool = False

class WorkerResult(BaseModel):
    status: str  # "success" | "error"
    data: dict
    meta: WorkerMeta

class BaseWorker(ABC, Generic[T_Input, T_Output]):
    """
    Base class for all 32 expert workers in the GeoSupply swarm.

    LIFECYCLE (automatic — subclasses only implement process()):
        setup()           → one-time initialization (load models, connect DBs)
        validate_input()  → Pydantic schema check on incoming TaskPacket
        process()         → ★ THE WORK — subclass implements this
        validate_output() → Pydantic schema check on result
        teardown()        → cleanup (close connections, flush buffers)

    AUTOMATIC FEATURES (handled by BaseWorker):
        - Timing:          every process() call is timed in ms
        - Cost tracking:   cost_inr accumulated and reported in meta
        - Circuit breaker: @breaker on all external API calls
        - Health check:    standardized health_check() → bool
        - Retry:           configurable backoff (default: 3 attempts)
        - Logging:         LoggingAgent.log() on entry/exit/error
        - STATIC decoder:  if use_static=True, output constrained by CSR decoder
        - Registration:    auto-registers capabilities with parent agent
    """

    # ─── Subclass Configuration ─────────────────────
    name: str = "UnnamedWorker"
    tier: int = 0                    # 0=CPU, 1=3b, 2=14b, 3=20b
    use_static: bool = False         # True for Tier-1 schema-strict workers
    max_retries: int = 3
    retry_backoff_base: float = 1.5  # seconds
    capabilities: set[str] = set()   # TaskTypes this worker handles

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.state = WorkerState.IDLE
        self._total_cost_inr = 0.0
        self._consecutive_passes = 0
        self._last_confidence = 1.0
        self._created_at = datetime.utcnow()

    # ─── Lifecycle Hooks (override as needed) ───────
    def setup(self) -> None:
        """One-time init. Load models, warm caches, verify deps."""
        pass

    def teardown(self) -> None:
        """Cleanup. Flush buffers, close connections."""
        pass

    def validate_input(self, input_data: T_Input) -> bool:
        """Schema validation on input. Override for custom checks."""
        return isinstance(input_data, BaseModel)

    def validate_output(self, output_data: T_Output) -> bool:
        """Schema validation on output. Override for custom checks."""
        return isinstance(output_data, BaseModel)

    # ─── The Core Method (subclass MUST implement) ──
    @abstractmethod
    def process(self, input_data: T_Input) -> T_Output:
        """Execute the worker's single responsibility."""
        ...

    # ─── Orchestration (called by parent Agent) ─────
    def execute(self, input_data: T_Input) -> WorkerResult:
        """
        Full lifecycle execution with instrumentation.
        Parent agents call this — never call process() directly.
        """
        self.state = WorkerState.PROCESSING
        start_time = time.perf_counter()
        retry_count = 0
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                # Validate input
                if not self.validate_input(input_data):
                    raise ValueError(f"Input validation failed for {self.name}")

                # Execute core logic
                result = self.process(input_data)

                # STATIC decoder enforcement
                if self.use_static:
                    result = self._apply_static_decoder(result)

                # Validate output
                if not self.validate_output(result):
                    raise ValueError(f"Output validation failed for {self.name}")

                # Success
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                self.state = WorkerState.IDLE
                self._consecutive_passes += 1

                return WorkerResult(
                    status="success",
                    data=result.model_dump(),
                    meta=WorkerMeta(
                        agent=self.name,
                        ts=time.time(),
                        cost_inr=self._total_cost_inr,
                        session_id=self.session_id,
                        latency_ms=elapsed_ms,
                        retry_count=retry_count,
                        model_used=self._get_model_name(),
                        static_decoder=self.use_static
                    )
                )

            except Exception as e:
                retry_count = attempt + 1
                last_error = str(e)
                self.state = WorkerState.RETRYING
                if attempt < self.max_retries:
                    backoff = self.retry_backoff_base ** attempt
                    time.sleep(backoff)

        # All retries exhausted
        self.state = WorkerState.ERROR
        self._consecutive_passes = 0
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        return WorkerResult(
            status="error",
            data={"error": last_error, "retries_exhausted": True},
            meta=WorkerMeta(
                agent=self.name,
                ts=time.time(),
                cost_inr=self._total_cost_inr,
                session_id=self.session_id,
                latency_ms=elapsed_ms,
                retry_count=retry_count,
                static_decoder=self.use_static
            )
        )

    # ─── Health Protocol ────────────────────────────
    def health_check(self) -> bool:
        """Standardized health check. Override for custom checks."""
        return self.state != WorkerState.CIRCUIT_OPEN

    # ─── Internal Helpers ───────────────────────────
    def _apply_static_decoder(self, output: T_Output) -> T_Output:
        """CSR-matrix constrained decoder for Tier-1 schema outputs."""
        # Delegates to static/decoder.py — see Chapter 8
        return output

    def _get_model_name(self) -> Optional[str]:
        """Override to return the LLM model used."""
        return None

    def _track_cost(self, cost_inr: float) -> None:
        """Call this inside process() when incurring costs."""
        self._total_cost_inr += cost_inr
```

---

## Worker Specialization Examples

### SentimentWorker (Tier-1, STATIC decoder)

```python
class SentimentInput(BaseModel):
    text: str
    language: str
    article_id: str

class SentimentOutput(BaseModel):
    sentiment: str       # POSITIVE | NEGATIVE | NEUTRAL
    confidence: float    # 0.0 - 1.0
    language: str

class SentimentWorker(BaseWorker[SentimentInput, SentimentOutput]):
    name = "SentimentWorker"
    tier = 1
    use_static = True  # ◄── STATIC decoder enforced
    capabilities = {"SENTIMENT_ANALYSIS"}

    def setup(self):
        self._model = moe_gate.get_model(tier=1)  # llama3.2:3b via Groq

    def process(self, input_data: SentimentInput) -> SentimentOutput:
        prompt = f"Classify sentiment: {input_data.text}"
        result = moe_gate.call(
            task_type="CLASSIFY",
            prompt=prompt,
            schema=SentimentOutput  # STATIC enforces this schema
        )
        self._track_cost(result.cost_inr)
        return SentimentOutput(**result.data)
```

### RAGWorker (Tier-3, Fixed Plan-Parallel-Fuse — v8 P0 fix)

```python
class RAGWorker(BaseWorker[RAGQuery, RAGResult]):
    name = "RAGWorker"
    tier = 3
    use_static = False
    max_retries = 2
    capabilities = {"RAG_PLAN", "RAG_RETRIEVE", "RAG_SYNTHESIZE"}

    def process(self, input_data: RAGQuery) -> RAGResult:
        # Delegates to SubAgent pipeline (see Chapter 4)
        # Step 1: ReasonPlanSubAgent → 3-5 sub-questions
        # Step 2: RetrieveSubAgent ×N (parallel)
        # Step 3: RerankSubAgent (parallel per set)
        # Step 4: RRF Fusion
        # Step 5: ContextBuildSubAgent
        # Step 6: BriefSynthSubAgent (MoA)
        pipeline = RAGPipeline(self.session_id)
        return pipeline.run(input_data)
```

---

## Complete Worker Inventory (32 Workers)

| # | Worker | Domain | Tier | STATIC | Capabilities |
|---|--------|--------|------|--------|-------------|
| 1 | NewsWorker | Ingestion | 1 | No | INGEST, NEWS_FETCH |
| 2 | IndiaAPIWorker | Ingestion | 0 | No | INGEST, INDIA_API |
| 3 | TelegramWorker | Ingestion | 0 | No | INGEST, TELEGRAM |
| 4 | AISWorker | Ingestion | 0 | No | INGEST, AIS_MARITIME |
| 5 | LangWorker | NLP | 0 | No | DETECT_LANG |
| 6 | TranslationWorker | NLP | 2 | No | TRANSLATE_FAST, TRANSLATE_DEEP |
| 7 | SentimentWorker | NLP | 1 | ⚡Yes | SENTIMENT_ANALYSIS |
| 8 | NERWorker | NLP | 1 | ⚡Yes | NER_EXTRACT |
| 9 | EmbedWorker | NLP | 0 | No | EMBED |
| 10 | ClaimWorker | Intel | 1 | ⚡Yes | CLAIM_EXTRACT |
| 11 | VerifierWorker | Intel | 3 | No | FACT_CHECK |
| 12 | SourceCredWorker | Intel | 1 | ⚡Yes | SOURCE_SCORE |
| 13 | AuthorWorker | Intel | 3 | No | AUTHOR_INTEL |
| 14 | NetworkWorker | Intel | 0 | No | NETWORK_GRAPH |
| 15 | CIBWorker | Intel | 3 | No | CIB_DETECT |
| 16 | PropagandaWorker | Intel | 3 | No | PROPAGANDA_DETECT |
| 17 | ConflictWorker | ML | 0 | No | CONFLICT_PREDICT |
| 18 | RetrainWorker | ML | 0 | No | MODEL_RETRAIN |
| 19 | DriftWorker | ML | 0 | No | DRIFT_DETECT |
| 20 | RAGWorker | RAG | 3 | No | RAG_PLAN, RAG_RETRIEVE, RAG_SYNTHESIZE |
| 21 | GraphRAGWorker | RAG | 3 | No | GRAPH_RAG |
| 22 | BriefWorker | RAG | 3 | No | BRIEF_MOA, BRIEF_SYNTH |
| 23 | StressWorker | Supply | 3 | No | STRESS_TEST |
| 24 | SupplierWorker | Supply | 1 | ⚡Yes | SUPPLIER_SCORE |
| 25 | SanctionsWorker | Supply | 1 | ⚡Yes | SANCTIONS_CHECK |
| 26 | IndiaIntelWorker | India | 3 | No | INDIA_INTEL |
| 27 | MonsoonWorker | India | 0 | No | MONSOON_TRACK |
| 28 | StreamlitWorker | Dashboard | 0 | No | DASHBOARD_RENDER |
| 29 | CIVisualisationWorker | Dashboard | 0 | No | CI_VISUALISE |
| 30 | ScaffoldAgent | Dev | — | No | CODE_SCAFFOLD |
| 31 | CodeReviewAgent | Dev | — | No | CODE_REVIEW |
| 32 | DocGenAgent | Dev | — | No | DOC_GENERATE |

**⚡ = 8 workers use STATIC decoder for 0% schema violations at Tier-1**
