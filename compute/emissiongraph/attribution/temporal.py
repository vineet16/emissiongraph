"""Temporal Attribution — Port A: period A vs period B.

Per spec Section 7.3: Same logic as spatial, different subjects.
Works MoM and YoY. Required: chronological framing — earlier first, later second.
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


DESCENT_THRESHOLD = 0.05


def _get_source_node_ids(
    G: nx.MultiDiGraph, port_id: str, fy: str, fuel_type: str, sub_type: str | None = None,
) -> list[str]:
    nids = []
    for nid, data in G.nodes(data=True):
        if (data.get("type") == NodeType.EMISSION_CONTRIBUTION.value
                and data.get("port_id") == port_id
                and data.get("fy") == fy
                and data.get("fuel_type") == fuel_type):
            if sub_type is None or data.get("sub_type") == sub_type:
                nids.append(nid)
    return nids


def run_temporal(
    G: nx.MultiDiGraph,
    port_id: str,
    fy_earlier: str,
    fy_later: str,
    fact_hash: str,
    metric: str = "emission_intensity",
    threshold: float = DESCENT_THRESHOLD,
) -> AttributionTree:
    """Run temporal attribution for a single port across two periods.

    Chronological framing: earlier period first (A), later period second (B).
    Gap = B - A (positive = increased, negative = decreased).
    """
    intensity_earlier = emission_intensity(G, port_id, fy_earlier)
    intensity_later = emission_intensity(G, port_id, fy_later)
    gap = intensity_later - intensity_earlier
    gap_pct = (gap / intensity_earlier * 100) if intensity_earlier != 0 else 0.0

    cargo_earlier = cargo_mt(G, port_id, fy_earlier)
    cargo_later = cargo_mt(G, port_id, fy_later)

    breakdown_earlier = emission_breakdown_by_source(G, port_id, fy_earlier)
    breakdown_later = emission_breakdown_by_source(G, port_id, fy_later)

    all_sources = sorted(set(breakdown_earlier.keys()) | set(breakdown_later.keys()))

    children: list[AttributionNode] = []
    excluded: list[str] = []

    for source_key in all_sources:
        em_earlier = breakdown_earlier.get(source_key, 0.0)
        em_later = breakdown_later.get(source_key, 0.0)

        contrib_earlier = (em_earlier / cargo_earlier) if cargo_earlier > 0 else 0.0
        contrib_later = (em_later / cargo_later) if cargo_later > 0 else 0.0
        delta = contrib_later - contrib_earlier

        direction = "increase" if delta >= 0 else "decrease"
        pct_of_gap = (delta / gap * 100) if gap != 0 else 0.0

        if "_" in source_key:
            parts = source_key.rsplit("_", 1)
            fuel_type = parts[0]
            sub_type = parts[1] if parts[1] != "None" else None
        else:
            fuel_type = source_key
            sub_type = None

        source_nids = (
            _get_source_node_ids(G, port_id, fy_earlier, fuel_type, sub_type)
            + _get_source_node_ids(G, port_id, fy_later, fuel_type, sub_type)
        )

        node = AttributionNode(
            label=source_key,
            delta_value=delta,
            delta_pct_of_gap=pct_of_gap,
            direction=direction,
            source_node_ids=source_nids,
            children=[],
        )

        if gap != 0 and abs(delta / gap) > threshold:
            cons_earlier = consumption_per_mt_cargo(G, port_id, fy_earlier, fuel_type)
            cons_later = consumption_per_mt_cargo(G, port_id, fy_later, fuel_type)
            cons_delta = cons_later - cons_earlier

            child = AttributionNode(
                label=f"{fuel_type} consumption/MT",
                delta_value=cons_delta,
                delta_pct_of_gap=pct_of_gap,
                direction="increase" if cons_delta >= 0 else "decrease",
                source_node_ids=source_nids,
                children=[],
            )
            node.children.append(child)

            if fuel_type == "Diesel":
                for sub in ["stationary", "mobile"]:
                    sub_key = f"Diesel_{sub}"
                    em_e_sub = breakdown_earlier.get(sub_key, 0.0)
                    em_l_sub = breakdown_later.get(sub_key, 0.0)
                    c_e = (em_e_sub / cargo_earlier) if cargo_earlier > 0 else 0.0
                    c_l = (em_l_sub / cargo_later) if cargo_later > 0 else 0.0
                    sub_delta = c_l - c_e
                    sub_pct = (sub_delta / gap * 100) if gap != 0 else 0.0

                    sub_nids = (
                        _get_source_node_ids(G, port_id, fy_earlier, "Diesel", sub)
                        + _get_source_node_ids(G, port_id, fy_later, "Diesel", sub)
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

    children.sort(key=lambda c: abs(c.delta_value), reverse=True)

    for nid, data in G.nodes(data=True):
        if (data.get("type") == NodeType.FUGITIVE_SOURCE.value
                and data.get("port_id") == port_id
                and data.get("fy") in (fy_earlier, fy_later)):
            ft = data.get("fuel_type", "")
            if ft not in excluded:
                excluded.append(ft)

    return AttributionTree(
        query_type="temporal",
        subjects=(port_id, fy_earlier, fy_later),
        root_metric=metric,
        root_value_a=intensity_earlier,
        root_value_b=intensity_later,
        root_gap=gap,
        root_gap_pct=gap_pct,
        children=children,
        excluded_sources=excluded if excluded else None,
        denominator={
            "cargo_earlier_mt": cargo_earlier,
            "cargo_later_mt": cargo_later,
        },
        fact_hash=fact_hash,
        graph_hash=graph_hash(G),
    )
