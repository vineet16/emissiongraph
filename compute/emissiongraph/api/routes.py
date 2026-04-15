"""FastAPI routes per spec Section 10.

Endpoints:
POST /ingest/workbook     — parse uploaded xlsx → Measurements
POST /graph/build         — portId, fy → graph hash + summary
POST /attribution/spatial — {portA, portB, fy, metric}
POST /attribution/temporal — {port, fyA, fyB, metric}
POST /attribution/fleet   — {fy, metric}
POST /narrative/generate  — {treeHash, template}
GET  /audit/trace/{runId} — full provenance chain
"""

from __future__ import annotations

import hashlib
import os
import tempfile
import uuid
from typing import Literal

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

from emissiongraph.attribution.fleet import run_fleet
from emissiongraph.attribution.spatial import run_spatial
from emissiongraph.attribution.temporal import run_temporal
from emissiongraph.attribution.tree import AttributionTree
from emissiongraph.facts.schema import IngestionResult, Measurement
from emissiongraph.graph.builder import build_graph, build_graph_from_headlines, graph_hash
from emissiongraph.ingestion.emission_parser import HeadlineMetrics, parse_workbook as parse_headlines
from emissiongraph.graph.queries import (
    cargo_mt,
    emission_breakdown_by_source,
    emission_intensity,
    energy_intensity,
    get_all_fys,
    get_all_ports,
    total_emissions,
    total_energy_gj,
)
from emissiongraph.ingestion.gri_parser import parse_workbook
from emissiongraph.ingestion.workbook_loader import EXPECTED_SHEETS, load_workbook, validate_workbook_sheets
from emissiongraph.narrative.generator import generate_narrative_sync, get_template_version
from emissiongraph.narrative.validator import validate_narrative
from emissiongraph.registry.factors import get_fuel_registry

from fastapi import APIRouter

# All API routes go on this router, mounted at both / and /api
api = APIRouter()
app = FastAPI(title="EmissionGraph Compute", version="0.1.0")

# In-memory stores for MVP (Convex is the real persistence layer)
_measurements_store: dict[str, list[Measurement]] = {}  # key: f"{port_id}:{fy}"
_headline_store: dict[str, HeadlineMetrics] = {}  # key: f"{port_id}:{fy}"
_workbook_paths: dict[str, str] = {}  # key: f"{port_id}:{fy}" -> temp path for re-parsing
_graph_store: dict[str, object] = {}  # key: f"{port_id}:{fy}" -> nx.MultiDiGraph
_attribution_cache: dict[str, AttributionTree] = {}  # key: tree_hash
_narrative_cache: dict[str, str] = {}  # key: f"{tree_hash}:{template_version}"


# --- Request/Response Models ---

class IngestResponse(BaseModel):
    port_id: str
    fy: str
    measurement_count: int
    fact_hash: str
    warnings: list[dict]


class GraphBuildRequest(BaseModel):
    port_id: str
    fy: str


class GraphBuildResponse(BaseModel):
    port_id: str
    fy: str
    graph_hash: str
    node_count: int
    edge_count: int
    total_emissions_tco2: float
    emission_intensity: float
    cargo_mt: float


class SpatialRequest(BaseModel):
    port_a: str
    port_b: str
    fy: str
    metric: str = "emission_intensity"


class TemporalRequest(BaseModel):
    port: str
    fy_a: str
    fy_b: str
    metric: str = "emission_intensity"


class FleetRequest(BaseModel):
    fy: str
    metric: str = "emission_intensity"


class NarrativeRequest(BaseModel):
    tree_hash: str
    template: str = "auto"


class NarrativeResponse(BaseModel):
    tree_hash: str
    template_version: str
    narrative: str
    validator_passed: bool


# --- Health check ---

@api.get("/health")
async def health():
    return {"status": "ok", "service": "emissiongraph-compute"}


# --- Ingestion ---

@api.post("/ingest/workbook", response_model=IngestResponse)
async def ingest_workbook(
    file: UploadFile = File(...),
    port_id: str = "P1",
    fy: str = "FY24-25",
):
    """Parse an uploaded xlsx workbook → Measurements."""
    if not file.filename or not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(400, "File must be .xlsx or .xls")

    # Save to temp file
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        wb = load_workbook(tmp_path)
        missing = validate_workbook_sheets(wb)
        if missing:
            raise HTTPException(400, f"Missing sheets: {missing}. Workbook must contain: {', '.join(EXPECTED_SHEETS)}")

        import logging
        logger = logging.getLogger("emissiongraph")
        logger.info(f"Workbook sheets found: {wb.sheetnames}")

        measurements, warnings = parse_workbook(wb, port_id, fy, file.filename)
        logger.info(f"Parsed {len(measurements)} measurements from {file.filename}")

        if not measurements:
            raise HTTPException(
                400,
                f"Workbook parsed but 0 measurements extracted. "
                f"Sheets: {wb.sheetnames}. "
                f"The parser expects GRI-format sheets (302-1, 305-1, 305-2, 305-4) "
                f"with monthly columns (Apr–Mar) and fuel-type rows."
            )

        result = IngestionResult(
            port_id=port_id,
            fy=fy,
            workbook_filename=file.filename,
            measurements=measurements,
            warnings=warnings,
        )

        # Store in memory
        key = f"{port_id}:{fy}"
        _measurements_store[key] = measurements

        # Also extract verified headline metrics from 305-4
        headlines = parse_headlines(tmp_path, port_id, fy)
        _headline_store[key] = headlines

        # Build the graph immediately using correct headline values
        cargo_ms = [m for m in measurements if m.fuel_type == "Cargo"]
        G = build_graph_from_headlines(headlines, cargo_ms)
        _graph_store[key] = G

        return IngestResponse(
            port_id=port_id,
            fy=fy,
            measurement_count=len(measurements),
            fact_hash=result.fact_hash(),
            warnings=[w.model_dump() for w in warnings],
        )
    finally:
        pass  # keep tmp_path for potential re-parsing


# --- Graph Build ---

@api.post("/graph/build", response_model=GraphBuildResponse)
async def build_port_graph(req: GraphBuildRequest):
    """Build the emissions graph for a port/FY from headline metrics."""
    key = f"{req.port_id}:{req.fy}"

    # Prefer headline-based graph (already built during ingest)
    if key in _graph_store:
        G = _graph_store[key]
        gh = graph_hash(G)
    else:
        measurements = _measurements_store.get(key)
        if not measurements:
            raise HTTPException(404, f"No measurements for {key}. Ingest a workbook first.")
        headlines = _headline_store.get(key)
        if headlines:
            cargo_ms = [m for m in measurements if m.fuel_type == "Cargo"]
            G = build_graph_from_headlines(headlines, cargo_ms)
        else:
            fuel_reg = get_fuel_registry(req.fy)
            G = build_graph(measurements, fuel_reg)
        _graph_store[key] = G
        gh = graph_hash(G)

    return GraphBuildResponse(
        port_id=req.port_id,
        fy=req.fy,
        graph_hash=gh,
        node_count=G.number_of_nodes(),
        edge_count=G.number_of_edges(),
        total_emissions_tco2=total_emissions(G, req.port_id, req.fy),
        emission_intensity=emission_intensity(G, req.port_id, req.fy),
        cargo_mt=cargo_mt(G, req.port_id, req.fy),
    )


# --- Attribution ---

def _get_combined_graph(port_ids: list[str], fys: list[str]):
    """Get or build a combined graph for multiple ports/FYs.

    Composes per-port headline-based graphs into a single MultiDiGraph.
    """
    import networkx as nx
    combined = nx.MultiDiGraph()

    found_any = False
    for pid in port_ids:
        for fy in fys:
            key = f"{pid}:{fy}"
            G = _graph_store.get(key)
            if G:
                combined = nx.compose(combined, G)
                found_any = True
            elif key in _headline_store:
                headlines = _headline_store[key]
                cargo_ms = [m for m in _measurements_store.get(key, []) if m.fuel_type == "Cargo"]
                G = build_graph_from_headlines(headlines, cargo_ms)
                _graph_store[key] = G
                combined = nx.compose(combined, G)
                found_any = True

    if not found_any:
        raise HTTPException(404, "No data found for requested ports/FYs")

    return combined


def _get_fact_hash(port_ids: list[str], fys: list[str]) -> str:
    """Compute combined fact hash for the measurements in scope."""
    import json
    all_ids = []
    for pid in port_ids:
        for fy in fys:
            key = f"{pid}:{fy}"
            ms = _measurements_store.get(key, [])
            all_ids.extend(m.id for m in ms)
    all_ids.sort()
    return hashlib.sha256(json.dumps(all_ids).encode()).hexdigest()


@api.post("/attribution/spatial")
async def attribution_spatial(req: SpatialRequest):
    """Run spatial attribution comparing two ports."""
    G = _get_combined_graph([req.port_a, req.port_b], [req.fy])
    fh = _get_fact_hash([req.port_a, req.port_b], [req.fy])

    tree = run_spatial(G, req.port_a, req.port_b, req.fy, fh, req.metric)
    tree_hash = tree.hash()
    _attribution_cache[tree_hash] = tree

    result = tree.model_dump(mode="json")
    result["tree_hash"] = tree_hash
    return result


@api.post("/attribution/temporal")
async def attribution_temporal(req: TemporalRequest):
    """Run temporal attribution for a port across two periods."""
    G = _get_combined_graph([req.port], [req.fy_a, req.fy_b])
    fh = _get_fact_hash([req.port], [req.fy_a, req.fy_b])

    tree = run_temporal(G, req.port, req.fy_a, req.fy_b, fh, req.metric)
    tree_hash = tree.hash()
    _attribution_cache[tree_hash] = tree

    result = tree.model_dump(mode="json")
    result["tree_hash"] = tree_hash
    return result


@api.post("/attribution/fleet")
async def attribution_fleet(req: FleetRequest):
    """Run fleet-level ranking for all ports in a period."""
    # Collect all ports that have data for this FY
    port_ids = []
    for key in _measurements_store:
        pid, fy = key.split(":")
        if fy == req.fy and pid not in port_ids:
            port_ids.append(pid)

    if not port_ids:
        raise HTTPException(404, f"No data for FY {req.fy}")

    G = _get_combined_graph(port_ids, [req.fy])
    fh = _get_fact_hash(port_ids, [req.fy])

    tree = run_fleet(G, req.fy, fh, req.metric)
    _attribution_cache[tree.hash()] = tree

    return tree.model_dump(mode="json")


# --- Narrative ---

@api.post("/narrative/generate", response_model=NarrativeResponse)
async def generate_narrative_endpoint(req: NarrativeRequest):
    """Generate a validated narrative for an attribution tree."""
    tree = _attribution_cache.get(req.tree_hash)
    if not tree:
        raise HTTPException(404, f"No attribution tree with hash {req.tree_hash}")

    tv = get_template_version()
    cache_key = f"{req.tree_hash}:{tv}"

    # Check cache
    if cache_key in _narrative_cache:
        return NarrativeResponse(
            tree_hash=req.tree_hash,
            template_version=tv,
            narrative=_narrative_cache[cache_key],
            validator_passed=True,
        )

    narrative, result = generate_narrative_sync(tree)

    if result.ok:
        _narrative_cache[cache_key] = narrative

    return NarrativeResponse(
        tree_hash=req.tree_hash,
        template_version=tv,
        narrative=narrative if result.ok else f"[Narrative generation failed: {result.reason}]",
        validator_passed=result.ok,
    )


# --- Audit Trace ---

@api.get("/audit/trace/{run_id}")
async def audit_trace(run_id: str):
    """Get the full provenance chain for an attribution run."""
    tree = _attribution_cache.get(run_id)
    if not tree:
        raise HTTPException(404, f"No attribution run with hash {run_id}")

    return {
        "run_id": run_id,
        "query_type": tree.query_type,
        "subjects": tree.subjects,
        "fact_hash": tree.fact_hash,
        "graph_hash": tree.graph_hash,
        "tree_hash": tree.hash(),
        "tree": tree.model_dump(mode="json"),
    }


# --- Debug: inspect workbook structure ---

@api.post("/debug/workbook-headers")
async def debug_workbook_headers(
    file: UploadFile = File(...),
):
    """Return the first 10 rows of each sheet for debugging parse issues."""
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        wb = load_workbook(tmp_path)
        result = {}
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            rows = []
            for row_idx in range(1, min((ws.max_row or 10) + 1, 11)):
                row_data = []
                for col_idx in range(1, min((ws.max_column or 20) + 1, 21)):
                    val = ws.cell(row=row_idx, column=col_idx).value
                    row_data.append(str(val) if val is not None else None)
                rows.append(row_data)
            result[sheet_name] = rows
        return result
    finally:
        os.unlink(tmp_path)


# --- Convenience: list available data ---

@api.get("/data/ports")
async def list_ports():
    """List all ports with ingested data."""
    ports: dict[str, list[str]] = {}
    for key in _measurements_store:
        pid, fy = key.split(":")
        ports.setdefault(pid, []).append(fy)
    return {"ports": ports}


# --- LLM Query ---

class QueryRequest(BaseModel):
    question: str
    fy: str = "FY24-25"


class QueryResponse(BaseModel):
    answer: str
    context_used: list[str]


@api.post("/query", response_model=QueryResponse)
async def query_llm(req: QueryRequest):
    """Ask a free-form question about the emissions data.

    Builds a context summary from all loaded port data and sends it
    to the LLM along with the user's question.
    """
    from openai import OpenAI

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(500, "GROQ_API_KEY not set")

    # Build context from headline metrics for the requested FY
    context_parts = []
    port_ids = []
    for key, h in _headline_store.items():
        pid, fy = key.split(":")
        if fy != req.fy:
            continue
        port_ids.append(pid)

        scope1_total = (h.scope1_diesel_stationary_tco2e + h.scope1_diesel_mobile_tco2e
                        + h.scope1_petrol_tco2e + h.scope1_hfhsd_ifo_tco2e
                        + h.scope1_other_fuels_tco2e)

        # Per-MT intensity breakdown (kg CO2e per MT cargo) for decomposition
        c = h.cargo_mt if h.cargo_mt > 0 else 1
        components = [
            ("Electricity(S2)", h.scope2_electricity_tco2e),
            ("Diesel_mobile(S1)", h.scope1_diesel_mobile_tco2e),
            ("Diesel_stationary(S1)", h.scope1_diesel_stationary_tco2e),
            ("HFHSD_IFO(S1)", h.scope1_hfhsd_ifo_tco2e),
            ("Petrol(S1)", h.scope1_petrol_tco2e),
            ("OtherFuels(S1)", h.scope1_other_fuels_tco2e),
        ]
        breakdown_abs = ", ".join(f"{n}: {v:.2f} tCO2e" for n, v in components if v > 0)
        breakdown_per_mt = ", ".join(
            f"{n}: {v/c*1000:.4f} kg/MT" for n, v in components if v > 0
        )

        # Electricity source breakdown (thermal vs renewable MWH)
        elec_note = ""
        ms = _measurements_store.get(key, [])
        thermal_mwh = sum(m.quantity for m in ms if m.fuel_type == "Electricity" and m.sub_type == "thermal")
        renewable_mwh = sum(m.quantity for m in ms if m.fuel_type == "Electricity" and m.sub_type == "renewable")
        total_mwh = sum(m.quantity for m in ms if m.fuel_type == "Electricity" and m.sub_type is None)

        # Per-MT electricity emission (kg/MT) to detect operationally significant patterns
        elec_per_mt = h.scope2_electricity_tco2e / c * 1000 if c > 0 else 0

        if total_mwh > 0 or thermal_mwh > 0 or renewable_mwh > 0:
            elec_note = (
                f"\n  Electricity consumption: {thermal_mwh:,.1f} MWH thermal (grid) + "
                f"{renewable_mwh:,.1f} MWH renewable = {thermal_mwh + renewable_mwh:,.1f} MWH total"
            )
            if renewable_mwh > 0 and thermal_mwh > 0:
                pct_re = renewable_mwh / (thermal_mwh + renewable_mwh) * 100
                elec_note += f" ({pct_re:.0f}% renewable — RE has zero emission factor)"
            elif renewable_mwh > 0 and thermal_mwh == 0:
                elec_note += " (100% renewable — zero grid electricity emissions)"
            elif thermal_mwh > 0 and renewable_mwh == 0:
                elec_note += " (100% grid — all electricity emissions are Scope 2)"
        if elec_per_mt < 0.05 and h.total_emissions_tco2e > 100:
            elec_note += (
                f"\n  NOTE: Near-zero electricity emissions ({elec_per_mt:.4f} kg/MT) — "
                f"this port operates with minimal grid electricity, likely using renewable/captive power. "
                f"This is a significant operational difference vs grid-dependent ports."
            )

        part = (
            f"Port {pid} ({fy}):\n"
            f"  Cargo: {h.cargo_mt:,.0f} MT\n"
            f"  Total Emissions: {h.total_emissions_tco2e:,.2f} tCO2e\n"
            f"  Scope 1: {scope1_total:,.2f} tCO2e | Scope 2 (Electricity): {h.scope2_electricity_tco2e:,.2f} tCO2e\n"
            f"  GHG Intensity: {h.ghg_intensity_kg_per_mt:.4f} kg CO2e/MT\n"
            f"  Absolute breakdown: {breakdown_abs}\n"
            f"  Per-MT breakdown (kg CO2e/MT cargo): {breakdown_per_mt}"
            f"{elec_note}"
        )
        context_parts.append(part)

    if not context_parts:
        raise HTTPException(404, f"No data loaded for {req.fy}")

    context = "\n\n".join(context_parts)

    system = (
        "You are an emissions data analyst for port infrastructure. "
        "Answer questions using ONLY the data provided below. "
        "Use specific numbers from the data. Be concise and factual.\n\n"
        "IMPORTANT rules for comparison questions (why is X higher/lower than Y):\n"
        "1. Use the PER-MT BREAKDOWN (kg CO2e/MT) to decompose the intensity gap — "
        "these directly sum to the total intensity and show each source's contribution.\n"
        "2. Identify the TOP 2-3 sources driving the gap by their per-MT difference.\n"
        "3. Note if any source is present in one port but absent in another (e.g. HFHSD/IFO).\n"
        "4. Quantify: state the per-MT difference for each driver and what % of the total gap it explains.\n"
        "5. If one source offsets the gap (port B is higher on that source), mention it. "
        "List ALL offsetting sources, not just the largest — every source above 0.01 kg/MT difference matters.\n"
        "6a. MANDATORY: For comparison questions, first compute a full table of ALL sources showing "
        "portA kg/MT, portB kg/MT, diff, and % of gap. Then write the narrative from that table. "
        "Do not skip any source with |diff| > 0.01 kg/MT.\n"
        "6. ALWAYS disclose the electricity source (renewable vs grid) when it explains near-zero "
        "Scope 2 emissions. If a port has significant renewable electricity, this is a key "
        "operational difference that MUST be mentioned — do not skip it.\n"
        "7. When Scope 2 electricity per-MT is very different between ports, explain whether "
        "this is due to higher consumption, grid vs renewable sourcing, or both.\n\n"
        f"## Emissions Data ({req.fy})\n\n{context}"
    )

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1",
    )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=1024,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": req.question},
        ],
    )

    return QueryResponse(
        answer=response.choices[0].message.content,
        context_used=port_ids,
    )


# --- Mount API router at both / (direct) and /api (frontend proxy/production) ---
app.include_router(api)
app.include_router(api, prefix="/api")

# --- Static file serving for production (frontend build) ---
import pathlib
_static_dir = pathlib.Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "dist"
if _static_dir.exists():
    from starlette.staticfiles import StaticFiles
    from starlette.responses import FileResponse

    app.mount("/assets", StaticFiles(directory=_static_dir / "assets"), name="static-assets")

    @app.get("/{path:path}")
    async def serve_spa(path: str):
        """Serve frontend SPA — catch-all after API routes."""
        if path.startswith("api/"):
            raise HTTPException(404)
        file = _static_dir / path
        if file.exists() and file.is_file():
            return FileResponse(file)
        return FileResponse(_static_dir / "index.html")
