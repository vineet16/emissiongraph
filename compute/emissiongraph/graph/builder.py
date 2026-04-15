"""Graph builder — facts + fuel registry → typed emissions graph.

Purity: build_graph(measurements, fuelRegistry, scope) → nx.MultiDiGraph
No randomness, no I/O, no LLM.

Determinism rules (spec 6.3):
1. Node IDs are deterministic UUID5s from canonical attributes.
2. Edge enumeration order is fixed — sort by (source_id, target_id, type).
3. Every computed quantity carries computed_from listing predecessor node IDs.
4. Graph serialization uses nx.node_link_data with sort_keys=True.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Literal

import networkx as nx

from emissiongraph.facts.schema import Measurement
from emissiongraph.graph.schema import EdgeType, NodeType
from emissiongraph.registry.fuels import FuelEntry


def _node_id(*parts: str) -> str:
    """Deterministic UUID5 from canonical attributes."""
    key = "|".join(str(p) for p in parts)
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))


def build_graph(
    measurements: list[Measurement],
    fuel_registry: list[FuelEntry],
    scope: Literal["1", "2", "both"] = "both",
) -> nx.MultiDiGraph:
    """Build the emissions graph from measurements and fuel registry.

    The graph captures: Port → FiscalPeriod → EnergySource → Consumption →
    (via factors) → EnergyContribution + EmissionContribution → IntensityMetric.
    """
    G = nx.MultiDiGraph()

    # Index fuel registry
    fuel_map: dict[str, FuelEntry] = {}
    for entry in fuel_registry:
        fuel_map[entry.fuel_type] = entry

    # Group measurements by port and FY
    by_port_fy: dict[tuple[str, str], list[Measurement]] = {}
    for m in measurements:
        key = (m.port_id, m.fy)
        by_port_fy.setdefault(key, []).append(m)

    for (port_id, fy), port_measurements in by_port_fy.items():
        # --- Port node ---
        port_nid = _node_id("port", port_id)
        G.add_node(port_nid, type=NodeType.PORT.value, port_id=port_id,
                    source_measurement_ids=[], computed_from=[])

        # --- FiscalPeriod node ---
        fp_nid = _node_id("fp", port_id, fy)
        G.add_node(fp_nid, type=NodeType.FISCAL_PERIOD.value,
                    port_id=port_id, fy=fy,
                    source_measurement_ids=[], computed_from=[])
        G.add_edge(port_nid, fp_nid, type=EdgeType.OPERATES_IN.value)

        # Separate cargo, consumption, and intensity measurements
        cargo_ms = [m for m in port_measurements if m.fuel_type == "Cargo"]
        intensity_ms = [m for m in port_measurements
                        if m.fuel_type in ("EmissionIntensity", "EnergyIntensity")]
        fuel_ms = [m for m in port_measurements
                   if m.fuel_type not in ("Cargo", "EmissionIntensity", "EnergyIntensity")]

        # --- Cargo throughput ---
        total_cargo = sum(m.quantity for m in cargo_ms)
        cargo_nid = _node_id("cargo", port_id, fy)
        G.add_node(cargo_nid, type=NodeType.CARGO_THROUGHPUT.value,
                    port_id=port_id, fy=fy, quantity=total_cargo, unit="MT",
                    source_measurement_ids=[m.id for m in cargo_ms],
                    computed_from=[])
        G.add_edge(fp_nid, cargo_nid, type=EdgeType.HANDLED.value)

        # --- Group fuel measurements by (fuel_type, sub_type) ---
        fuel_groups: dict[tuple[str, str | None], list[Measurement]] = {}
        for m in fuel_ms:
            key = (m.fuel_type, m.sub_type)
            fuel_groups.setdefault(key, []).append(m)

        total_energy_gj = 0.0
        total_scope1_tco2 = 0.0
        total_scope2_tco2 = 0.0
        energy_contrib_nids: list[str] = []
        emission_contrib_nids: list[str] = []

        for (fuel_type, sub_type), fms in fuel_groups.items():
            fuel_entry = fuel_map.get(fuel_type)
            if fuel_entry is None:
                continue  # Unknown fuel, skip

            sub_label = f"_{sub_type}" if sub_type else ""

            # --- EnergySource node ---
            es_nid = _node_id("energy_source", port_id, fy, fuel_type, str(sub_type))
            G.add_node(es_nid, type=NodeType.ENERGY_SOURCE.value,
                        port_id=port_id, fy=fy,
                        fuel_type=fuel_type, sub_type=sub_type,
                        source_measurement_ids=[], computed_from=[])
            G.add_edge(fp_nid, es_nid, type=EdgeType.CONSUMED.value)

            # --- Consumption node (sum of all periods for this fuel) ---
            total_qty = sum(m.quantity for m in fms)
            unit = fms[0].unit if fms else fuel_entry.default_unit
            cons_nid = _node_id("consumption", port_id, fy, fuel_type, str(sub_type))
            G.add_node(cons_nid, type=NodeType.CONSUMPTION.value,
                        port_id=port_id, fy=fy,
                        fuel_type=fuel_type, sub_type=sub_type,
                        quantity=total_qty, unit=unit,
                        source_measurement_ids=[m.id for m in fms],
                        computed_from=[es_nid])
            G.add_edge(es_nid, cons_nid, type=EdgeType.CONSUMED.value)

            # --- Energy Factor node ---
            ef_nid = _node_id("energy_factor", fuel_type, fuel_entry.applicable_from)
            if not G.has_node(ef_nid):
                G.add_node(ef_nid, type=NodeType.ENERGY_FACTOR.value,
                            fuel_type=fuel_type,
                            factor=fuel_entry.energy_factor_gj_per_unit,
                            unit=f"GJ/{fuel_entry.default_unit}",
                            source_reference=fuel_entry.source_reference,
                            source_measurement_ids=[], computed_from=[])
            G.add_edge(cons_nid, ef_nid, type=EdgeType.USING_FACTOR.value)

            # --- Energy Contribution ---
            energy_gj = total_qty * fuel_entry.energy_factor_gj_per_unit
            ec_nid = _node_id("energy_contrib", port_id, fy, fuel_type, str(sub_type))
            G.add_node(ec_nid, type=NodeType.ENERGY_CONTRIBUTION.value,
                        port_id=port_id, fy=fy,
                        fuel_type=fuel_type, sub_type=sub_type,
                        quantity=energy_gj, unit="GJ",
                        source_measurement_ids=[],
                        computed_from=[cons_nid, ef_nid])
            G.add_edge(cons_nid, ec_nid, type=EdgeType.PRODUCES_ENERGY.value)
            energy_contrib_nids.append(ec_nid)
            total_energy_gj += energy_gj

            # --- Emission Factor + Emission Contribution ---
            is_scope1 = fuel_entry.scope1_factor_tco2_per_unit is not None
            is_scope2 = fuel_entry.scope2_factor_tco2_per_unit is not None
            is_fugitive = fuel_type == "HFC" and fuel_entry.gwp is not None

            if is_fugitive:
                # HFC: emissions = quantity * GWP / 1000 (Kg to tCO2e)
                fugitive_nid = _node_id("fugitive", port_id, fy, fuel_type)
                emissions_tco2 = total_qty * fuel_entry.gwp / 1000.0
                G.add_node(fugitive_nid, type=NodeType.FUGITIVE_SOURCE.value,
                            port_id=port_id, fy=fy,
                            fuel_type=fuel_type,
                            quantity=emissions_tco2, unit="tCO2e",
                            gwp=fuel_entry.gwp,
                            source_measurement_ids=[m.id for m in fms],
                            computed_from=[cons_nid])
                G.add_edge(cons_nid, fugitive_nid, type=EdgeType.PRODUCES_EMISSION.value)

                emc_nid = _node_id("emission_contrib", port_id, fy, fuel_type, str(sub_type))
                G.add_node(emc_nid, type=NodeType.EMISSION_CONTRIBUTION.value,
                            port_id=port_id, fy=fy,
                            fuel_type=fuel_type, sub_type=sub_type,
                            quantity=emissions_tco2, unit="tCO2e",
                            scope="scope1",
                            source_measurement_ids=[],
                            computed_from=[fugitive_nid])
                G.add_edge(fugitive_nid, emc_nid, type=EdgeType.CONTRIBUTES_TO.value)
                G.add_edge(emc_nid, emc_nid, type=EdgeType.SCOPED_AS.value, scope="scope1")
                emission_contrib_nids.append(emc_nid)
                total_scope1_tco2 += emissions_tco2

            if is_scope1 and not is_fugitive:
                emf_nid = _node_id("emission_factor_s1", fuel_type, fuel_entry.applicable_from)
                if not G.has_node(emf_nid):
                    G.add_node(emf_nid, type=NodeType.EMISSION_FACTOR.value,
                                fuel_type=fuel_type, scope="scope1",
                                factor=fuel_entry.scope1_factor_tco2_per_unit,
                                unit=f"tCO2/{fuel_entry.default_unit}",
                                source_reference=fuel_entry.source_reference,
                                source_measurement_ids=[], computed_from=[])
                G.add_edge(cons_nid, emf_nid, type=EdgeType.USING_FACTOR.value)

                emissions_s1 = total_qty * fuel_entry.scope1_factor_tco2_per_unit
                emc_nid = _node_id("emission_contrib", port_id, fy, fuel_type, str(sub_type))
                G.add_node(emc_nid, type=NodeType.EMISSION_CONTRIBUTION.value,
                            port_id=port_id, fy=fy,
                            fuel_type=fuel_type, sub_type=sub_type,
                            quantity=emissions_s1, unit="tCO2e",
                            scope="scope1",
                            source_measurement_ids=[],
                            computed_from=[cons_nid, emf_nid])
                G.add_edge(cons_nid, emc_nid, type=EdgeType.PRODUCES_EMISSION.value)
                G.add_edge(emc_nid, emc_nid, type=EdgeType.SCOPED_AS.value, scope="scope1")
                emission_contrib_nids.append(emc_nid)
                total_scope1_tco2 += emissions_s1

            if is_scope2:
                emf_nid = _node_id("emission_factor_s2", fuel_type, fuel_entry.applicable_from)
                if not G.has_node(emf_nid):
                    G.add_node(emf_nid, type=NodeType.EMISSION_FACTOR.value,
                                fuel_type=fuel_type, scope="scope2",
                                factor=fuel_entry.scope2_factor_tco2_per_unit,
                                unit=f"tCO2/{fuel_entry.default_unit}",
                                source_reference=fuel_entry.source_reference,
                                source_measurement_ids=[], computed_from=[])
                G.add_edge(cons_nid, emf_nid, type=EdgeType.USING_FACTOR.value)

                emissions_s2 = total_qty * fuel_entry.scope2_factor_tco2_per_unit
                emc_s2_nid = _node_id("emission_contrib_s2", port_id, fy, fuel_type, str(sub_type))
                G.add_node(emc_s2_nid, type=NodeType.EMISSION_CONTRIBUTION.value,
                            port_id=port_id, fy=fy,
                            fuel_type=fuel_type, sub_type=sub_type,
                            quantity=emissions_s2, unit="tCO2e",
                            scope="scope2",
                            source_measurement_ids=[],
                            computed_from=[cons_nid, emf_nid])
                G.add_edge(cons_nid, emc_s2_nid, type=EdgeType.PRODUCES_EMISSION.value)
                G.add_edge(emc_s2_nid, emc_s2_nid, type=EdgeType.SCOPED_AS.value, scope="scope2")
                emission_contrib_nids.append(emc_s2_nid)
                total_scope2_tco2 += emissions_s2

        # --- Intensity metrics ---
        if total_cargo > 0:
            total_emissions = 0.0
            if scope in ("1", "both"):
                total_emissions += total_scope1_tco2
            if scope in ("2", "both"):
                total_emissions += total_scope2_tco2

            emission_intensity = total_emissions / total_cargo
            ei_nid = _node_id("intensity_emission", port_id, fy)
            G.add_node(ei_nid, type=NodeType.INTENSITY_METRIC.value,
                        port_id=port_id, fy=fy,
                        metric="emission_intensity",
                        quantity=emission_intensity, unit="tCO2e/MT",
                        source_measurement_ids=[],
                        computed_from=emission_contrib_nids + [cargo_nid])

            energy_intensity = total_energy_gj / total_cargo
            eni_nid = _node_id("intensity_energy", port_id, fy)
            G.add_node(eni_nid, type=NodeType.INTENSITY_METRIC.value,
                        port_id=port_id, fy=fy,
                        metric="energy_intensity",
                        quantity=energy_intensity, unit="GJ/MT",
                        source_measurement_ids=[],
                        computed_from=energy_contrib_nids + [cargo_nid])

    return G


def build_graph_from_headlines(
    headlines: "HeadlineMetrics",
    cargo_measurements: list[Measurement] | None = None,
) -> nx.MultiDiGraph:
    """Build the emissions graph from verified headline metrics (from 305-4).

    This produces correct emission values that match the workbook author's
    own calculations, rather than recomputing from quantities × factors.
    """
    from emissiongraph.ingestion.emission_parser import HeadlineMetrics

    G = nx.MultiDiGraph()
    h = headlines
    port_id = h.port_id
    fy = h.fy

    # --- Port node ---
    port_nid = _node_id("port", port_id)
    G.add_node(port_nid, type=NodeType.PORT.value, port_id=port_id,
                source_measurement_ids=[], computed_from=[])

    # --- FiscalPeriod node ---
    fp_nid = _node_id("fp", port_id, fy)
    G.add_node(fp_nid, type=NodeType.FISCAL_PERIOD.value,
                port_id=port_id, fy=fy,
                source_measurement_ids=[], computed_from=[])
    G.add_edge(port_nid, fp_nid, type=EdgeType.OPERATES_IN.value)

    # --- Cargo throughput ---
    cargo_nid = _node_id("cargo", port_id, fy)
    cargo_mids = [m.id for m in (cargo_measurements or [])]
    G.add_node(cargo_nid, type=NodeType.CARGO_THROUGHPUT.value,
                port_id=port_id, fy=fy, quantity=h.cargo_mt, unit="MT",
                source_measurement_ids=cargo_mids, computed_from=[])
    G.add_edge(fp_nid, cargo_nid, type=EdgeType.HANDLED.value)

    # --- Emission contributions from headline metrics ---
    emission_contrib_nids = []
    scope1_components = [
        ("Diesel", "stationary", h.scope1_diesel_stationary_tco2e),
        ("Diesel", "mobile", h.scope1_diesel_mobile_tco2e),
        ("Petrol", None, h.scope1_petrol_tco2e),
        ("HFHSD", None, h.scope1_hfhsd_ifo_tco2e),
        ("OtherFuels", None, h.scope1_other_fuels_tco2e),
    ]

    for fuel_type, sub_type, emissions in scope1_components:
        sub_label = str(sub_type) if sub_type else "None"
        emc_nid = _node_id("emission_contrib", port_id, fy, fuel_type, sub_label)
        G.add_node(emc_nid, type=NodeType.EMISSION_CONTRIBUTION.value,
                    port_id=port_id, fy=fy,
                    fuel_type=fuel_type, sub_type=sub_type,
                    quantity=emissions, unit="tCO2e",
                    scope="scope1",
                    source_measurement_ids=[], computed_from=[fp_nid])
        G.add_edge(fp_nid, emc_nid, type=EdgeType.PRODUCES_EMISSION.value)
        emission_contrib_nids.append(emc_nid)

    # Scope 2: Electricity
    elec_nid = _node_id("emission_contrib_s2", port_id, fy, "Electricity", "None")
    G.add_node(elec_nid, type=NodeType.EMISSION_CONTRIBUTION.value,
                port_id=port_id, fy=fy,
                fuel_type="Electricity", sub_type=None,
                quantity=h.scope2_electricity_tco2e, unit="tCO2e",
                scope="scope2",
                source_measurement_ids=[], computed_from=[fp_nid])
    G.add_edge(fp_nid, elec_nid, type=EdgeType.PRODUCES_EMISSION.value)
    emission_contrib_nids.append(elec_nid)

    # --- Intensity metric ---
    if h.cargo_mt > 0:
        ei = h.total_emissions_tco2e / h.cargo_mt
        ei_nid = _node_id("intensity_emission", port_id, fy)
        G.add_node(ei_nid, type=NodeType.INTENSITY_METRIC.value,
                    port_id=port_id, fy=fy,
                    metric="emission_intensity",
                    quantity=ei, unit="tCO2e/MT",
                    source_measurement_ids=[],
                    computed_from=emission_contrib_nids + [cargo_nid])

    return G


def graph_hash(G: nx.MultiDiGraph) -> str:
    """Deterministic hash of the graph. Spec: sort_keys=True in serialization."""
    data = nx.node_link_data(G)
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()
