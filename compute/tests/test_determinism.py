"""Determinism tests per spec Sections 5 (fact hash) and 7.5 (attribution).

Invariant: hash(facts) → hash(graph) → hash(attribution_tree) is deterministic.
Drift is a bug.
"""

from __future__ import annotations

from emissiongraph.attribution.spatial import run_spatial
from emissiongraph.attribution.fleet import run_fleet
from emissiongraph.facts.schema import IngestionResult
from emissiongraph.graph.builder import build_graph, graph_hash


def test_fact_hash_deterministic(sample_measurements):
    """Two ingests of the same measurements produce identical fact hashes."""
    r1 = IngestionResult(
        port_id="P1", fy="FY24-25", workbook_filename="test.xlsx",
        measurements=sample_measurements,
    )
    r2 = IngestionResult(
        port_id="P1", fy="FY24-25", workbook_filename="test.xlsx",
        measurements=sample_measurements,
    )
    assert r1.fact_hash() == r2.fact_hash()


def test_graph_hash_deterministic(sample_measurements, fuel_registry):
    """Same measurements → same graph hash."""
    g1 = build_graph(sample_measurements, fuel_registry)
    g2 = build_graph(sample_measurements, fuel_registry)
    assert graph_hash(g1) == graph_hash(g2)


def test_attribution_deterministic(sample_measurements, fuel_registry):
    """100 runs of the same spatial attribution produce identical tree hashes (spec 7.5)."""
    G = build_graph(sample_measurements, fuel_registry)
    fh = "test_hash"

    runs = [run_spatial(G, "P1", "P10", "FY24-25", fh) for _ in range(100)]
    assert len({t.hash() for t in runs}) == 1


def test_decomposition_sums_to_total(sample_measurements, fuel_registry):
    """Contributions sum exactly to the gap — no rounding leaks (spec 7.5)."""
    G = build_graph(sample_measurements, fuel_registry)
    fh = "test_hash"

    tree = run_spatial(G, "P1", "P10", "FY24-25", fh)
    child_sum = sum(c.delta_value for c in tree.children)
    assert abs(child_sum - tree.root_gap) < 1e-9


def test_fleet_deterministic(sample_measurements, fuel_registry):
    """Fleet ranking is deterministic."""
    G = build_graph(sample_measurements, fuel_registry)
    fh = "test_hash"

    runs = [run_fleet(G, "FY24-25", fh) for _ in range(50)]
    assert len({t.hash() for t in runs}) == 1
