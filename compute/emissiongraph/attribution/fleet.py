"""Fleet Ranking — default dashboard view.

Per spec Section 7.4: Not strictly an attribution — a structured summary
across all 10 ports for a given period.

Outputs:
- Sorted list of ports by intensity (asc and desc)
- Fleet min, max, median, spread
- Per-port YoY delta (when prior-period data available)
- Identity of largest absolute contributors at fleet level
"""

from __future__ import annotations

import statistics

import networkx as nx

from emissiongraph.attribution.tree import AttributionNode, AttributionTree
from emissiongraph.graph.builder import graph_hash
from emissiongraph.graph.queries import (
    cargo_mt,
    emission_breakdown_by_source,
    emission_intensity,
    get_all_fys,
    get_all_ports,
    total_emissions,
    total_energy_gj,
)


def _prior_fy(fy: str) -> str | None:
    """Compute prior FY string: 'FY24-25' -> 'FY23-24'."""
    try:
        parts = fy.replace("FY", "").split("-")
        start = int(parts[0])
        end = int(parts[1])
        return f"FY{start - 1:02d}-{end - 1:02d}"
    except (ValueError, IndexError):
        return None


def run_fleet(
    G: nx.MultiDiGraph,
    fy: str,
    fact_hash: str,
    metric: str = "emission_intensity",
) -> AttributionTree:
    """Generate fleet-level ranking and summary for the dashboard."""
    ports = get_all_ports(G)
    prior_fy = _prior_fy(fy)

    port_data: list[dict] = []
    intensities: list[float] = []

    for pid in ports:
        intensity = emission_intensity(G, pid, fy)
        cargo = cargo_mt(G, pid, fy)
        scope1 = total_emissions(G, pid, fy, "1")
        scope2 = total_emissions(G, pid, fy, "2")
        energy = total_energy_gj(G, pid, fy)

        yoy_delta = None
        if prior_fy:
            prior_intensity = emission_intensity(G, pid, prior_fy)
            if prior_intensity > 0:
                yoy_delta = (intensity - prior_intensity) / prior_intensity * 100

        if cargo > 0:  # only include ports with data
            intensities.append(intensity)
            port_data.append({
                "port_id": pid,
                "intensity": intensity,
                "cargo_mt": cargo,
                "scope1_tco2": scope1,
                "scope2_tco2": scope2,
                "total_emissions": scope1 + scope2,
                "energy_gj": energy,
                "yoy_delta_pct": yoy_delta,
            })

    # Sort by intensity descending
    port_data.sort(key=lambda x: x["intensity"], reverse=True)

    # Fleet statistics
    fleet_min = min(intensities) if intensities else 0.0
    fleet_max = max(intensities) if intensities else 0.0
    fleet_median = statistics.median(intensities) if intensities else 0.0
    fleet_spread = fleet_max - fleet_min

    # Build children — one per port
    children: list[AttributionNode] = []
    for pd_ in port_data:
        children.append(AttributionNode(
            label=pd_["port_id"],
            delta_value=pd_["intensity"],
            delta_pct_of_gap=(pd_["intensity"] / fleet_median * 100) if fleet_median > 0 else 0.0,
            direction="increase" if pd_["intensity"] >= fleet_median else "decrease",
            source_node_ids=[],
            children=[],
        ))

    # Find largest absolute contributors at fleet level
    fleet_breakdown: dict[str, float] = {}
    for pid in ports:
        breakdown = emission_breakdown_by_source(G, pid, fy)
        for source, val in breakdown.items():
            fleet_breakdown[source] = fleet_breakdown.get(source, 0.0) + val

    return AttributionTree(
        query_type="fleet",
        subjects=tuple(p["port_id"] for p in port_data),
        root_metric=metric,
        root_value_a=fleet_max,
        root_value_b=fleet_min,
        root_gap=fleet_spread,
        root_gap_pct=(fleet_spread / fleet_median * 100) if fleet_median > 0 else 0.0,
        children=children,
        excluded_sources=None,
        denominator={
            "fleet_min": fleet_min,
            "fleet_max": fleet_max,
            "fleet_median": fleet_median,
            "fleet_spread": fleet_spread,
            "port_details": port_data,
            "fleet_emission_breakdown": fleet_breakdown,
        },
        fact_hash=fact_hash,
        graph_hash=graph_hash(G),
    )
