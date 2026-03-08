# Part III: SubAgent Layer — Composable Pipelines + 15 SubAgents
## FA v2 | Gap Mitigations: G1, G8 applied | World Monitor Integration

## 3.1 BaseSubAgent Class

```python
class BaseSubAgent(ABC):
    """
    SubAgents compose multiple workers into directed pipelines.
    Each SubAgent is a mini-DAG: Plan → Execute → Fuse.

    PIPELINE PATTERN:
        step 1 → step 2a ─┐
                  step 2b ─┤ → step 3 (fuse) → result
                  step 2c ─┘

    KEY PROPERTIES:
        - SubAgents don't call other SubAgents (no nesting)
        - SubAgents can call Workers and infrastructure Agents
        - Results are Pydantic models (type-safe)
        - Cost aggregated from all worker calls
        - Circuit breakers on every worker call (v10)
    """

    name: str
    pipeline_steps: list[str]      # Ordered step names
    parallel_steps: set[str] = set()  # Steps that can run in parallel

    # --- FA v1: G1 FIX — Lifecycle hooks matching BaseWorker ---
    async def setup(self):
        """Called once before first run(). Initialise worker pools, load configs."""
        pass

    @abstractmethod
    async def run(self, input_data: dict) -> dict:
        """Execute the pipeline and return aggregated result."""
        pass

    async def teardown(self):
        """Called on graceful shutdown. Release worker pools, flush buffers."""
        pass

    async def run_parallel(self, steps: list[callable], inputs: list[dict]) -> list[dict]:
        """Run multiple worker calls in parallel."""
        return await asyncio.gather(*[step(inp) for step, inp in zip(steps, inputs)])
```

---

## 3.2 Complete SubAgent Inventory (15 SubAgents)

### RAG Pipeline SubAgents (5)

#### RAGPipelineSubAgent — Master RAG Orchestrator
```
PIPELINE: Plan → Retrieve(×N parallel) → Rerank → ContextBuild → BriefSynth

    Step 1: ReasonPlanSubAgent
        Input:  user query
        Output: 3-5 sub-questions + retrieval strategy
        Worker: ReasonPlanWorker (Tier-3)

    Step 2: RetrieveSubAgent (× N parallel)
        Input:  sub-questions from Step 1
        Output: N result sets from ChromaDB
        Worker: RAGWorker (Tier-0) per sub-question

    Step 3: RerankSubAgent
        Input:  N result sets
        Output: top-K ranked documents (cross-encoder)
        Worker: EmbedWorker (Tier-0)

    Step 4: ContextBuildSubAgent
        Input:  top-K documents
        Output: structured context window (≤4K tokens)
        Worker: ContextBuildWorker (Tier-0)

    Step 5: BriefSynthSubAgent (MoA)
        Input:  structured context
        Output: intelligence brief
        Workers: 3× BriefWorker (Tier-3) + 1 aggregation
```

#### BriefSynthSubAgent — Mixture of Agents
```python
class BriefSynthSubAgent(BaseSubAgent):
    """
    3-proposer + 1-aggregator Mixture-of-Agents pattern.

    PROPOSERS (parallel): 3× BriefWorker with different prompts
    AGGREGATOR: Select best + combine insights

    v10 FIX: MoAFallbackSubAgent handles aggregator failure
        Level 0: GPT-OSS:20b full MoA aggregation (primary)
        Level 1: Groq llama-3.3-70b aggregation (cloud fallback)
        Level 2: Scoring-based selection (highest confidence)
        Level 3: Return all 3 to admin for manual pick

    INVARIANT: All 3 proposals saved to SQLite BEFORE aggregation.
    """
    name = "BriefSynthSubAgent"
    pipeline_steps = ["propose_×3", "aggregate"]
    parallel_steps = {"propose_×3"}
```

### Quality Assurance SubAgents (3)

#### SourceFeedbackSubAgent
```python
class SourceFeedbackSubAgent(BaseSubAgent):
    """
    Adjusts source credibility scores based on FactCheck results.

    v10 FIX: Escalating penalties (not flat -0.05)
        1st quarantine: -0.05
        2nd (within 30d): -0.10
        3rd (within 30d): -0.20
        4th: PERMANENT FLAG → admin override required

    v10 FIX: Source clustering
        If source permanently flagged → SourceClusterSubAgent
        checks for related sources (IP/domain/author/style).
        Penalty applies to entire cluster.
    """
    name = "SourceFeedbackSubAgent"
```

#### SemanticDriftMonitor
```
SCHEDULE: Weekly
CHECK: Compare embedding distribution of last week vs baseline
METHOD: KL divergence on document embeddings per source
ALERT: If KL > 0.30 on any source → flag for review
```

#### HallucinationCheckSubAgent
```
PIPELINE: 7-step FactCheck (from FactCheckAgent)
    1. Claim extraction (ClaimWorker)
    2. Evidence retrieval (RAGWorker)
    3. Evidence scoring (VerifierWorker)
    4. Cross-reference check (3 sources minimum)
    5. Confidence calibration
    6. Hallucination floor check (≥ 0.70)
    7. Quarantine decision
```

### v10 New SubAgents (5)

#### SummarizationVerifierSubAgent
```python
class SummarizationVerifierSubAgent(BaseSubAgent):
    """
    Catches semantic distortion in marketing summaries/tweets.
    FIXES: v9 GAP 2

    CHECKS:
        1. Extract numerical values from source data
        2. Extract directional language from summary
        3. Verify direction matches data trend
        4. Verify magnitude band matches score:
            0.0-0.30 = "minimal/negligible"
            0.30-0.50 = "low/modest"
            0.50-0.70 = "moderate/notable"
            0.70-0.85 = "high/significant"
            0.85-1.00 = "critical/severe"
        5. If summary uses HIGHER band language than data → REJECT
    """
    name = "SummarizationVerifierSubAgent"
```

#### SourceClusterSubAgent
```python
class SourceClusterSubAgent(BaseSubAgent):
    """
    Detects coordinated source networks. FIXES: v9 GAP 3

    CLUSTERING DIMENSIONS:
        - IP address range
        - Domain/subdomain
        - Author/byline
        - Writing style (embedding cosine > 0.90)
    If source A is flagged → penalty applies to entire cluster.
    """
    name = "SourceClusterSubAgent"
```

#### OverridePatternSubAgent
```python
class OverridePatternSubAgent(BaseSubAgent):
    """
    Detects admin override abuse patterns. FIXES: v9 GAP 6

    PATTERNS:
        - Volume: >5 overrides/week → ALERT
        - Source favouritism: same source approved >3 times → ALERT
        - Time clustering: >3 overrides in 1 hour → ALERT
        - FactCheck bypass rate: >20% quarantined briefs approved → ALERT
    """
    name = "OverridePatternSubAgent"
```

#### MoAFallbackSubAgent
```python
class MoAFallbackSubAgent(BaseSubAgent):
    """
    4-level fallback for MoA aggregation failure. FIXES: v9 GAP 5

    CHAIN:
        Level 0: GPT-OSS:20b (primary)
        Level 1: Groq llama-3.3-70b (cloud)
        Level 2: Scoring (pick highest confidence)
        Level 3: Manual (queue for admin)

    FA v1 G8 FIX — Level 2 Scoring Criteria:
        Weighted score = 0.4 × factcheck_score
                       + 0.3 × source_credibility_avg
                       + 0.3 × claim_evidence_ratio
        Select proposal with highest weighted score.
        If top 2 proposals within 0.05 of each other → merge both.
        If all scores < 0.50 → escalate to Level 3 (manual).

    INVARIANT: Proposals ALWAYS saved before aggregation.
    """
    name = "MoAFallbackSubAgent"
```

#### PenetrationTestSubAgent
```python
class PenetrationTestSubAgent(BaseSubAgent):
    """
    Runs 8 automated penetration tests. Schedule: weekly (Sunday).

    TESTS:
        1. Prompt injection via crafted articles
        2. Schema bypass (>2048 token input to Tier-1)
        3. Source credibility gaming (4 quarantines)
        4. API key leakage (grep logs for key patterns)
        5. Admin CLI brute force (6 wrong passwords)
        6. Message contract violation (malformed AgentMessage)
        7. ChromaDB direct write (bypass single-writer)
        8. Rate limit verification (flood ingestion endpoint)
    """
    name = "PenetrationTestSubAgent"
```

### FA v2 New SubAgents (2) — World Monitor Integration

#### ConvergenceSubAgent
```python
class ConvergenceSubAgent(BaseSubAgent):
    """
    Detects multi-domain incidents converging in the same geographic region.
    Inspired by World Monitor's Geographic Convergence Detection.

    PIPELINE:
        Step 1: Collect events from NewsWorker, DisasterWorker, AISWorker
        Step 2: Group events by 0.5° spatial grid + 24h time window
        Step 3: Score convergence = weighted sum of event diversity
        Step 4: If convergence_score > threshold → emit CONVERGENCE_ALERT event

    SCORING:
        base_score = num_unique_domains × 10
        recency_boost = events_in_last_6h × 5
        severity_boost = sum(event_severity for high-severity events) × 3
        convergence_score = base_score + recency_boost + severity_boost

    THRESHOLDS:
        > 30 = ELEVATED (log + dashboard)
        > 60 = HIGH (alert admin)
        > 90 = CRITICAL (auto-escalate to SwarmMaster)
    """
    name = "ConvergenceSubAgent"
    pipeline_steps = ["collect", "spatial_group", "score", "alert"]
```

#### CascadeSubAgent
```python
class CascadeSubAgent(BaseSubAgent):
    """
    Models infrastructure dependency chains to predict cascade failures.
    Inspired by World Monitor's Infrastructure Cascade Analysis.

    PIPELINE:
        Step 1: Load infrastructure dependency graph (cables, pipelines, ports)
        Step 2: Given a disruption event, identify first-order dependencies
        Step 3: Walk the graph to find second/third-order impacts
        Step 4: Calculate cascade severity score per affected country

    DEPENDENCY TYPES:
        - Undersea cables → Internet connectivity
        - Oil/gas pipelines → Energy supply
        - Maritime chokepoints → Trade routes
        - Power plants → Grid stability

    OUTPUT: CascadeReport schema with:
        - affected_countries: list[str]
        - cascade_depth: int (1-3)
        - severity_score: float (0-100)
        - redundancy_factor: float (0-1, higher = more resilient)
    """
    name = "CascadeSubAgent"
    pipeline_steps = ["load_graph", "identify_impact", "walk_cascade", "score"]
```

## CROSS-CHECK ✅
```
✓ 15 subagents listed (8 v9 + 5 v10 + 2 FA v2)
✓ RAG pipeline fully documented (5-step)
✓ MoA pattern with v10 fallback chain
✓ All v10 subagents map to specific gap fixes
✓ SourceFeedback has escalating penalties (v10 fix)
✓ HallucinationCheck enforces 0.70 floor
✓ No SubAgent nesting (SubAgents don't call SubAgents)
✓ [FA v1] BaseSubAgent has setup()/teardown() lifecycle hooks (G1)
✓ [FA v1] MoA Level 2 scoring criteria defined (G8)
✓ [FA v2] ConvergenceSubAgent for multi-domain geographic detection
✓ [FA v2] CascadeSubAgent for infrastructure dependency analysis
```
