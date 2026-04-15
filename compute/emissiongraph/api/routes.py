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
from emissiongraph.graph.builder import build_graph, graph_hash
from emissiongraph.graph.queries import (
    cargo_mt,
    emission_intensity,
    energy_intensity,
    get_all_fys,
    get_all_ports,
    total_emissions,
    total_energy_gj,
)
from emissiongraph.ingestion.gri_parser import parse_workbook
from emissiongraph.ingestion.workbook_loader import load_workbook, validate_workbook_sheets
from emissiongraph.narrative.generator import generate_narrative_sync, get_template_version
from emissiongraph.narrative.validator import validate_narrative
from emissiongraph.registry.factors import get_fuel_registry

app = FastAPI(title="EmissionGraph Compute", version="0.1.0")

# In-memory stores for MVP (Convex is the real persistence layer)
_measurements_store: dict[str, list[Measurement]] = {}  # key: f"{port_id}:{fy}"
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

@app.get("/health")
async def health():
    return {"status": "ok", "service": "emissiongraph-compute"}


# --- Ingestion ---

@app.post("/ingest/workbook", response_model=IngestResponse)
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
            raise HTTPException(400, f"Missing sheets: {missing}")

        measurements, warnings = parse_workbook(wb, port_id, fy, file.filename)

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

        return IngestResponse(
            port_id=port_id,
            fy=fy,
            measurement_count=len(measurements),
            fact_hash=result.fact_hash(),
            warnings=[w.model_dump() for w in warnings],
        )
    finally:
        os.unlink(tmp_path)


# --- Graph Build ---

@app.post("/graph/build", response_model=GraphBuildResponse)
async def build_port_graph(req: GraphBuildRequest):
    """Build the emissions graph for a port/FY from stored measurements."""
    key = f"{req.port_id}:{req.fy}"
    measurements = _measurements_store.get(key)
    if not measurements:
        raise HTTPException(404, f"No measurements for {key}. Ingest a workbook first.")

    fuel_reg = get_fuel_registry(req.fy)
    G = build_graph(measurements, fuel_reg)
    gh = graph_hash(G)

    _graph_store[key] = G

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
    """Get or build a combined graph for multiple ports/FYs."""
    all_measurements: list[Measurement] = []
    for pid in port_ids:
        for fy in fys:
            key = f"{pid}:{fy}"
            ms = _measurements_store.get(key, [])
            all_measurements.extend(ms)

    if not all_measurements:
        raise HTTPException(404, "No measurements found for requested ports/FYs")

    fuel_reg = get_fuel_registry(fys[0])
    return build_graph(all_measurements, fuel_reg)


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


@app.post("/attribution/spatial")
async def attribution_spatial(req: SpatialRequest):
    """Run spatial attribution comparing two ports."""
    G = _get_combined_graph([req.port_a, req.port_b], [req.fy])
    fh = _get_fact_hash([req.port_a, req.port_b], [req.fy])

    tree = run_spatial(G, req.port_a, req.port_b, req.fy, fh, req.metric)
    _attribution_cache[tree.hash()] = tree

    return tree.model_dump(mode="json")


@app.post("/attribution/temporal")
async def attribution_temporal(req: TemporalRequest):
    """Run temporal attribution for a port across two periods."""
    G = _get_combined_graph([req.port], [req.fy_a, req.fy_b])
    fh = _get_fact_hash([req.port], [req.fy_a, req.fy_b])

    tree = run_temporal(G, req.port, req.fy_a, req.fy_b, fh, req.metric)
    _attribution_cache[tree.hash()] = tree

    return tree.model_dump(mode="json")


@app.post("/attribution/fleet")
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

@app.post("/narrative/generate", response_model=NarrativeResponse)
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

@app.get("/audit/trace/{run_id}")
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


# --- Convenience: list available data ---

@app.get("/data/ports")
async def list_ports():
    """List all ports with ingested data."""
    ports: dict[str, list[str]] = {}
    for key in _measurements_store:
        pid, fy = key.split(":")
        ports.setdefault(pid, []).append(fy)
    return {"ports": ports}
