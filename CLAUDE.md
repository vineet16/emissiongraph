# EmissionGraph

Port infrastructure emissions attribution engine (Scope 1 + Scope 2).

## Architecture

6-layer system: Ingestion → Fact Store → Graph Builder → Attribution Engine → Narrative Layer → Audit UI

- **Convex** (TypeScript): Schema, queries, mutations, live data
- **Python** (FastAPI + NetworkX): Ingestion parsing, graph build, attribution math
- **React** (Vite + Tailwind + recharts): Dashboard UI

## Key Commands

```bash
# Run Python tests (from compute/)
cd compute && python -m pytest tests/ -v

# Start compute service
cd compute && uvicorn emissiongraph.api.routes:app --reload --port 8000

# Start frontend dev server
cd frontend && npm run dev
```

## Invariant

`hash(facts) → hash(graph) → hash(attribution_tree) → cached(narrative)` is deterministic. Drift is a bug.

## Determinism Tests Gate Every PR

All tests in `compute/tests/test_determinism.py` must pass. The decomposition test verifies contributions sum exactly to the gap.
