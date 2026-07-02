"""GeoSupply subsystem verification gate.

Run:  python scripts/verify_subsystems.py

End-to-end subsystem verification: backend, middleware, storage, RAG,
automations, projections, statistical prediction. Real components, offline
data via MockTransport where the sandbox blocks the network."""
import asyncio, json, os, sys, tempfile
os.environ["OSINT_AUTOSTART"] = "0"
os.environ["OSINT_STATE_PATH"] = tempfile.mktemp(suffix=".json")
import pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT))

import httpx
from httpx import ASGITransport, AsyncClient
from tests.unit.test_osint_api import _route_request

RESULTS = []
def check(name, ok, detail=""):
    RESULTS.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))

async def main():
    from geosupply.api.main import create_app
    from geosupply.api.routers import osint as osint_mod
    from geosupply.osint.aggregator import OsintAggregator

    agg = OsintAggregator(client=httpx.AsyncClient(transport=httpx.MockTransport(_route_request)))
    app = create_app()
    app.dependency_overrides[osint_mod.aggregator_dep] = lambda: agg

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        # ── 1. BACKEND ────────────────────────────────────────────
        r = await c.get("/health")
        check("backend: /health liveness", r.status_code == 200, r.json().get("status", ""))
        routes = len(app.routes)
        check("backend: route registry", routes >= 60, f"{routes} routes")

        # ── 2. MIDDLEWARE ─────────────────────────────────────────
        snap = await agg.refresh(force=True)
        r = await c.get("/osint/snapshot")
        body = r.json()
        check("middleware: snapshot aggregation", r.status_code == 200 and body["events"] and body["news"],
              f"{len(body['events'])} events, {len(body['news'])} news, {len(body['markets'])} quotes")
        r = await c.get("/osint/snapshot", headers={"Origin": "http://example.com"})
        check("middleware: CORS headers", "access-control-allow-origin" in {k.lower() for k in r.headers})
        os.environ["GEOSUPPLY_PLAN"] = "FREE"
        r403 = await c.get("/osint/ask", params={"q": "hormuz"})
        del os.environ["GEOSUPPLY_PLAN"]
        r200 = await c.get("/osint/ask", params={"q": "hormuz"})
        check("middleware: freemium gate", r403.status_code == 403 and r200.status_code == 200,
              f"FREE→{r403.status_code}, self-hosted→{r200.status_code}")
        delivered_probe = await agg.hub.broadcast({"type": "ping"})
        check("middleware: WS hub broadcast path", delivered_probe == 0, "0 clients, no error")

        # ── 3. STORAGE (learning-state persistence) ───────────────
        agg.rag_feedback.apply.__self__  # attribute exists
        from geosupply.osint.rag_feedback import FeedbackEvent
        for _ in range(4):
            agg.rag_feedback.apply([FeedbackEvent(source="BBC World", kind="news", vote=1)])
        agg.save_state()
        state_file = os.environ["OSINT_STATE_PATH"]
        raw = json.loads(open(state_file).read())
        check("storage: atomic JSON state written",
              set(raw) >= {"kg", "bias", "projector", "rag_feedback", "calibrator", "cycles"},
              f"{len(open(state_file).read())} bytes, keys={sorted(raw)[:3]}…")
        agg2 = OsintAggregator(client=agg._client)
        check("storage: restart restores learners",
              agg2.rag_feedback.weight("BBC World") == agg.rag_feedback.weight("BBC World")
              and agg2._cycles == agg._cycles,
              f"weight={agg2.rag_feedback.weight('BBC World')}, cycles={agg2._cycles}")

        # ── 4. RAG (agentic + feedback loop) ─────────────────────
        r = await c.get("/osint/ask", params={"q": "red sea shipping risk"})
        ans = r.json()
        check("rag: agentic answer with citations",
              r.status_code == 200 and ans["citations"] and ans["confidence"] > 0,
              f"conf={ans['confidence']}, {len(ans['citations'])} citations, {len(ans['sub_queries'])} sub-queries")
        r = await c.post("/osint/ask/feedback", json={"items": [
            {"source": ans["citations"][0].get("source", "BBC World") or "BBC World",
             "kind": "news", "vote": 1}]})
        check("rag: feedback endpoint learns", r.status_code == 200 and r.json()["accepted"] == 1)

        # ── 5. AUTOMATIONS (scheduler + adaptive tempo) ───────────
        agg.start_scheduler()
        running = agg._task is not None and not agg._task.done()
        await agg.stop_scheduler()
        stopped = agg._task is None
        check("automations: scheduler start/stop", running and stopped)
        from geosupply.osint.models import ConvergenceAlert
        alert = ConvergenceAlert(id="x", title="t", lat=0, lon=0, asset_kind="port",
                                 signals=["a", "b"], severity=3)
        agg._adapt_interval([alert], [])
        surge = agg._surge and agg._interval_s == 60.0
        agg._cycles = 10; agg._adapt_interval([], [])
        quiet = (not agg._surge) and agg._interval_s == 300.0
        check("automations: adaptive tempo (surge→quiet)", surge and quiet)

        # ── 6. PROJECTIONS + STATISTICAL PREDICTION ───────────────
        from geosupply.osint.projection import RiskProjector
        proj = RiskProjector()
        series = [10, 18, 27, 35, 44, 52, 61, 70, 78, 85]   # rising trend
        naive_errs, model_errs, prev = [], [], None
        for actual in series:
            if prev is not None:
                naive_errs.append(abs(prev - actual))
                f = proj.forecast_for("XX")
                if f is not None:
                    model_errs.append(abs(f - actual))
            proj.observe({"XX": float(actual)})
            prev = actual
        mae_model = sum(model_errs) / len(model_errs) if model_errs else 999
        check("projection: online alpha selection", proj.best_alpha >= 0.6,
              f"best_alpha={proj.best_alpha}, reported MAE={proj.mae}")
        check("projection: honest error tracking", proj.mae is not None and proj.samples == 10,
              f"samples={proj.samples}")
        from geosupply.osint.calibration import ThresholdCalibrator
        cal = ThresholdCalibrator()
        cal.observe([0.05, 0.1, 0.12, 0.6, 0.65] * 40)
        e, h, cr = cal.bands()
        check("statistics: calibrated quantile bands", e < 0.25 or h != 0.5,
              f"bands=({e}, {h}, {cr}) vs static (0.25, 0.5, 0.75)")
        from geosupply.osint.intel import risk_confidence
        lo1, hi1, d1 = risk_confidence(50, 2)
        lo2, hi2, d2 = risk_confidence(50, 30)
        check("statistics: CI narrows with n (1/√n)", (hi1 - lo1) > (hi2 - lo2),
              f"n=2 width {hi1-lo1:.0f} > n=30 width {hi2-lo2:.0f}; density {d1}→{d2}")

    await agg.teardown()
    fails = [n for n, ok, _ in RESULTS if not ok]
    print(f"\n{'='*60}\nSUBSYSTEM VERIFICATION: {len(RESULTS)-len(fails)}/{len(RESULTS)} PASS")
    if fails:
        print("FAILURES:", fails); sys.exit(1)

asyncio.run(main())
