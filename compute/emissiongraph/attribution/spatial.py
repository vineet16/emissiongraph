"""Spatial Attribution — Port A vs Port B, same period.

Per spec Section 7.2:
1. Compute intensity_A and intensity_B. Gap = A - B.
2. Decompose using ratio identity:
   intensity_A - intensity_B = sum_source[(emissions_source_A / cargo_A) - (emissions_source_B / cargo_B)]
3. For each source where |contribution| > threshold of total gap, descend one level.
   Since factors are constant across ports, gap reduces to consumption-per-MT-cargo gap.
4. For diesel, descend further into stationary vs mobile.
5. Emit AttributionTree, sorted by |contribution| descending.
"""

from __future__ import annotations

import networkx as nx

from emissiongraph.attribution.tree import AttributionNode, AttributionTree
from emissiongraph.graph.builder import graph_hash
from emissiongraph.graph.queries import (
    cargo_mt,
    consumption_per_mt_cargo,
    emission_breakdown_by_source,
    emission_intensity,
)
from emissiongraph.graph.schema import NodeType


DESCENT_THRESHOLD = 0.05  # 5% of gap — configurable per spec


def _get_source_node_ids(
    G: nx.MultiDiGraph, port_id: str, fy: str, fuel_type: str, sub_type: str | None = None,
) -> list[str]:
    """Get source node IDs for a given fuel type at a port."""
    nids = []
    for nid, data in G.nodes(data=True):
        if (data.get("type") == NodeType.EMISSION_CONTRIBUTION.value
                and data.get("port_id") == port_id
                and data.get("fy") == fy
                and data.get("fuel_type") == fuel_type):
            if sub_type is None or data.get("sub_type") == sub_type:
                nids.append(nid)
    return nids


def run_spatial(
    G: nx.MultiDiGraph,
    port_a: str,
    port_b: str,
    fy: str,
    fact_hash: str,
    metric: str = "emission_intensity",
    threshold: float = DESCENT_THRESHOLD,
) -> AttributionTree:
    """Run spatial attribution comparing two ports in the same period."""
    intensity_a = emission_intensity(G, port_a, fy)
    intensity_b = emission_intensity(G, port_b, fy)
    gap = intensity_a - intensity_b
    gap_pct = (gap / intensity_b * 100) if intensity_b != 0 else 0.0

    cargo_a = cargo_mt(G, port_a, fy)
    cargo_b = cargo_mt(G, port_b, fy)

    breakdown_a = emission_breakdown_by_source(G, port_a, fy)
    breakdown_b = emission_breakdown_by_source(G, port_b, fy)

    # Union of all source keys
    all_sources = sorted(set(breakdown_a.keys()) | set(breakdown_b.keys()))

    children: list[AttributionNode] = []
    excluded: list[str] = []

    for source_key in all_sources:
        em_a = breakdown_a.get(source_key, 0.0)
        em_b = breakdown_b.get(source_key, 0.0)

        # Intensity contribution per source
        contrib_a = (em_a / cargo_a) if cargo_a > 0 else 0.0
        contrib_b = (em_b / cargo_b) if cargo_b > 0 else 0.0
        delta = contrib_a - contrib_b

        direction = "increase" if delta >= 0 else "decrease"
        pct_of_gap = (delta / gap * 100) if gap != 0 else 0.0

        # Parse fuel_type and sub_type from source_key
        if "_" in source_key:
            parts = source_key.rsplit("_", 1)
            fuel_type = parts[0]
            sub_type = parts[1] if parts[1] != "None" else None
        else:
            fuel_type = source_key
            sub_type = None

        source_nids = (
            _get_source_node_ids(G, port_a, fy, fuel_type, sub_type)
            + _get_source_node_ids(G, port_b, fy, fuel_type, sub_type)
        )

        node = AttributionNode(
            label=source_key,
            delta_value=delta,
            delta_pct_of_gap=pct_of_gap,
            direction=direction,
            source_node_ids=source_nids,
            children=[],
        )

        # Descend one level for significant contributors
        if gap != 0 and abs(delta / gap) > threshold:
            # Since factors are constant across ports, gap = factor * (consumption_per_mt_A - consumption_per_mt_B)
            # Surface this explicitly
            cons_per_mt_a = consumption_per_mt_cargo(G, port_a, fy, fuel_type)
            cons_per_mt_b = consumption_per_mt_cargo(G, port_b, fy, fuel_type)
            cons_delta = cons_per_mt_a - cons_per_mt_b

            child = AttributionNode(
                label=f"{fuel_type} consumption/MT",
                delta_value=cons_delta,
                delta_pct_of_gap=pct_of_gap,  # same pct since factors are constant
                direction="increase" if cons_delta >= 0 else "decrease",
                source_node_ids=source_nids,
                children=[],
            )
            node.children.append(child)

            # For diesel, descend further into stationary vs mobile
            if fuel_type == "Diesel":
                for sub in ["stationary", "mobile"]:
                    sub_key = f"Diesel_{sub}"
                    em_a_sub = breakdown_a.get(sub_key, 0.0)
                    em_b_sub = breakdown_b.get(sub_key, 0.0)
                    c_a = (em_a_sub / cargo_a) if cargo_a > 0 else 0.0
                    c_b = (em_b_sub / cargo_b) if cargo_b > 0 else 0.0
                    sub_delta = c_a - c_b
                    sub_pct = (sub_delta / gap * 100) if gap != 0 else 0.0

                    sub_nids = (
                        _get_source_node_ids(G, port_a, fy, "Diesel", sub)
                        + _get_source_node_ids(G, port_b, fy, "Diesel", sub)
                    )

                    sub_child = AttributionNode(
                        label=f"Diesel ({sub})",
                        delta_value=sub_delta,
                        delta_pct_of_gap=sub_pct,
                        direction="increase" if sub_delta >= 0 else "decrease",
                        source_node_ids=sub_nids,
                    )
                    child.children.append(sub_child)

        children.append(node)

    # Sort by |contribution| descending
    children.sort(key=lambda c: abs(c.delta_value), reverse=True)

    # Check for annual-only exclusions
    for nid, data in G.nodes(data=True):
        if (data.get("type") == NodeType.FUGITIVE_SOURCE.value
                and data.get("port_id") in (port_a, port_b)
                and data.get("fy") == fy):
            excluded.append(data.get("fuel_type", ""))

    return AttributionTree(
        query_type="spatial",
        subjects=(port_a, port_b),
        root_metric=metric,
        root_value_a=intensity_a,
        root_value_b=intensity_b,
        root_gap=gap,
        root_gap_pct=gap_pct,
        children=children,
        excluded_sources=excluded if excluded else None,
        denominator={"cargo_a_mt": cargo_a, "cargo_b_mt": cargo_b},
        fact_hash=fact_hash,
        graph_hash=graph_hash(G),
    )
