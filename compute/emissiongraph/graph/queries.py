"""Graph query primitives per spec Section 6.4."""

from __future__ import annotations

from typing import Literal

import networkx as nx

from emissiongraph.graph.schema import NodeType


def _nodes_of_type(G: nx.MultiDiGraph, ntype: str, **filters) -> list[tuple[str, dict]]:
    """Get all nodes of a given type, optionally filtered by attributes."""
    results = []
    for nid, data in G.nodes(data=True):
        if data.get("type") != ntype:
            continue
        if all(data.get(k) == v for k, v in filters.items()):
            results.append((nid, data))
    return results


def total_emissions(
    G: nx.MultiDiGraph,
    port_id: str,
    fy: str,
    scope: Literal["1", "2", "both"] = "both",
) -> float:
    """Total emissions (tCO2e) for a port in a given FY."""
    total = 0.0
    for nid, data in _nodes_of_type(G, NodeType.EMISSION_CONTRIBUTION.value,
                                      port_id=port_id, fy=fy):
        node_scope = data.get("scope", "")
        if scope == "both":
            total += data.get("quantity", 0.0)
        elif scope == "1" and node_scope == "scope1":
            total += data.get("quantity", 0.0)
        elif scope == "2" and node_scope == "scope2":
            total += data.get("quantity", 0.0)
    return total


def total_energy_gj(G: nx.MultiDiGraph, port_id: str, fy: str) -> float:
    """Total energy consumption in GJ for a port in a given FY."""
    total = 0.0
    for nid, data in _nodes_of_type(G, NodeType.ENERGY_CONTRIBUTION.value,
                                      port_id=port_id, fy=fy):
        total += data.get("quantity", 0.0)
    return total


def cargo_mt(G: nx.MultiDiGraph, port_id: str, fy: str) -> float:
    """Total cargo throughput in MT for a port in a given FY."""
    nodes = _nodes_of_type(G, NodeType.CARGO_THROUGHPUT.value,
                            port_id=port_id, fy=fy)
    if nodes:
        return nodes[0][1].get("quantity", 0.0)
    return 0.0


def emission_intensity(G: nx.MultiDiGraph, port_id: str, fy: str) -> float:
    """Emission intensity (tCO2e / MT cargo) for a port in a given FY."""
    cargo = cargo_mt(G, port_id, fy)
    if cargo == 0:
        return 0.0
    return total_emissions(G, port_id, fy, "both") / cargo


def energy_intensity(G: nx.MultiDiGraph, port_id: str, fy: str) -> float:
    """Energy intensity (GJ / MT cargo) for a port in a given FY."""
    cargo = cargo_mt(G, port_id, fy)
    if cargo == 0:
        return 0.0
    return total_energy_gj(G, port_id, fy) / cargo


def emission_breakdown_by_source(
    G: nx.MultiDiGraph,
    port_id: str,
    fy: str,
    scope: Literal["1", "2", "both"] = "both",
) -> dict[str, float]:
    """Emission breakdown by fuel source. Returns {fuel_type: tCO2e}."""
    breakdown: dict[str, float] = {}
    for nid, data in _nodes_of_type(G, NodeType.EMISSION_CONTRIBUTION.value,
                                      port_id=port_id, fy=fy):
        node_scope = data.get("scope", "")
        include = (
            scope == "both"
            or (scope == "1" and node_scope == "scope1")
            or (scope == "2" and node_scope == "scope2")
        )
        if include:
            ft = data.get("fuel_type", "Unknown")
            sub = data.get("sub_type")
            key = f"{ft}_{sub}" if sub else ft
            breakdown[key] = breakdown.get(key, 0.0) + data.get("quantity", 0.0)
    return breakdown


def consumption_per_mt_cargo(
    G: nx.MultiDiGraph,
    port_id: str,
    fy: str,
    fuel_type: str,
) -> float:
    """Consumption of a fuel type per MT of cargo handled."""
    cargo = cargo_mt(G, port_id, fy)
    if cargo == 0:
        return 0.0
    total = 0.0
    for nid, data in _nodes_of_type(G, NodeType.CONSUMPTION.value,
                                      port_id=port_id, fy=fy):
        if data.get("fuel_type") == fuel_type:
            total += data.get("quantity", 0.0)
    return total / cargo


def get_all_ports(G: nx.MultiDiGraph) -> list[str]:
    """Get all port IDs in the graph."""
    ports = set()
    for nid, data in _nodes_of_type(G, NodeType.PORT.value):
        ports.add(data.get("port_id", ""))
    return sorted(ports)


def get_all_fys(G: nx.MultiDiGraph, port_id: str) -> list[str]:
    """Get all fiscal years for a port."""
    fys = set()
    for nid, data in _nodes_of_type(G, NodeType.FISCAL_PERIOD.value, port_id=port_id):
        fys.add(data.get("fy", ""))
    return sorted(fys)
