"""Graph builder tests — verify correct node/edge structure and query primitives."""

from __future__ import annotations

from emissiongraph.graph.builder import build_graph, graph_hash
from emissiongraph.graph.queries import (
    cargo_mt,
    emission_breakdown_by_source,
    emission_intensity,
    energy_intensity,
    get_all_ports,
    total_emissions,
    total_energy_gj,
)
from emissiongraph.graph.schema import NodeType


def test_graph_has_expected_nodes(sample_measurements, fuel_registry):
    G = build_graph(sample_measurements, fuel_registry)

    # Should have Port, FiscalPeriod, CargoThroughput, etc.
    node_types = set()
    for _, data in G.nodes(data=True):
        node_types.add(data.get("type"))

    assert NodeType.PORT.value in node_types
    assert NodeType.FISCAL_PERIOD.value in node_types
    assert NodeType.CARGO_THROUGHPUT.value in node_types
    assert NodeType.CONSUMPTION.value in node_types
    assert NodeType.EMISSION_CONTRIBUTION.value in node_types


def test_cargo_mt(sample_measurements, fuel_registry):
    G = build_graph(sample_measurements, fuel_registry)
    # P1 has 500000 MT * 3 months = 1500000
    assert cargo_mt(G, "P1", "FY24-25") == 1500000.0
    # P10 has 800000 MT * 3 months = 2400000
    assert cargo_mt(G, "P10", "FY24-25") == 2400000.0


def test_total_emissions_positive(sample_measurements, fuel_registry):
    G = build_graph(sample_measurements, fuel_registry)
    e1 = total_emissions(G, "P1", "FY24-25")
    e10 = total_emissions(G, "P10", "FY24-25")
    assert e1 > 0
    assert e10 > 0


def test_emission_intensity_p1_higher(sample_measurements, fuel_registry):
    """P1 should have higher intensity than P10 (smaller cargo, more fuel)."""
    G = build_graph(sample_measurements, fuel_registry)
    i1 = emission_intensity(G, "P1", "FY24-25")
    i10 = emission_intensity(G, "P10", "FY24-25")
    assert i1 > i10


def test_get_all_ports(sample_measurements, fuel_registry):
    G = build_graph(sample_measurements, fuel_registry)
    ports = get_all_ports(G)
    assert "P1" in ports
    assert "P10" in ports


def test_emission_breakdown_by_source(sample_measurements, fuel_registry):
    G = build_graph(sample_measurements, fuel_registry)
    breakdown = emission_breakdown_by_source(G, "P1", "FY24-25")
    assert "Electricity" in breakdown
    assert "Diesel_stationary" in breakdown
    assert "Diesel_mobile" in breakdown
    assert all(v >= 0 for v in breakdown.values())
