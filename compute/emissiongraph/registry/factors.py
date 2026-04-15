"""Seed data for the fuel registry — FY24-25 emission/energy factors.

Sources:
- Grid electricity: CEA CO2 Baseline Database v20 (0.727 tCO2/MWH)
- Diesel/Petrol: IPCC AR6, GHG Protocol defaults
- HFCs: IPCC AR6 GWP-100
- Acetylene: IPCC defaults
- LPG/FO/Coal: IPCC defaults + Indian conversion factors

These are placeholder factors pending confirmation of exact IPCC/CPCB source
per Open Question #1 in the spec. The architecture allows factor versioning
via applicableFrom/To so corrections are non-breaking.
"""

from __future__ import annotations

from emissiongraph.registry.fuels import FuelEntry

# FY24-25 factors — CEA v20 grid, IPCC AR6 defaults for fuels
FY2425_FUEL_REGISTRY: list[FuelEntry] = [
    # --- Electricity (Scope 2) ---
    FuelEntry(
        fuel_type="Electricity",
        default_unit="MWH",
        energy_factor_gj_per_unit=3.6,  # 1 MWH = 3.6 GJ
        scope1_factor_tco2_per_unit=None,
        scope2_factor_tco2_per_unit=0.727,  # CEA v20 grid factor
        applicable_from="FY24-25",
        source_reference="CEA CO2 Baseline Database v20",
    ),
    # --- Diesel (Scope 1) ---
    FuelEntry(
        fuel_type="Diesel",
        default_unit="KL",
        energy_factor_gj_per_unit=35.86,  # IPCC default for diesel
        scope1_factor_tco2_per_unit=2.68,  # tCO2/KL — IPCC AR6
        ch4_factor=0.000133,  # tCH4/KL
        n2o_factor=0.000133,  # tN2O/KL
        applicable_from="FY24-25",
        source_reference="IPCC AR6 / GHG Protocol",
    ),
    # --- Petrol (Scope 1) ---
    FuelEntry(
        fuel_type="Petrol",
        default_unit="KL",
        energy_factor_gj_per_unit=32.24,
        scope1_factor_tco2_per_unit=2.30,  # tCO2/KL — IPCC AR6
        ch4_factor=0.000292,
        n2o_factor=0.000022,
        applicable_from="FY24-25",
        source_reference="IPCC AR6 / GHG Protocol",
    ),
    # --- Furnace Oil (Scope 1) ---
    FuelEntry(
        fuel_type="Furnace Oil",
        default_unit="KL",
        energy_factor_gj_per_unit=40.19,
        scope1_factor_tco2_per_unit=3.07,
        applicable_from="FY24-25",
        source_reference="IPCC AR6 / GHG Protocol",
    ),
    # --- LPG (Scope 1) ---
    FuelEntry(
        fuel_type="LPG",
        default_unit="T",
        energy_factor_gj_per_unit=47.31,
        scope1_factor_tco2_per_unit=2.98,
        applicable_from="FY24-25",
        source_reference="IPCC AR6 / GHG Protocol",
    ),
    # --- Coal (Scope 1) ---
    FuelEntry(
        fuel_type="Coal",
        default_unit="T",
        energy_factor_gj_per_unit=19.59,  # Indian sub-bituminous default
        scope1_factor_tco2_per_unit=1.87,
        applicable_from="FY24-25",
        source_reference="IPCC AR6 / Indian coal defaults",
    ),
    # --- HFCs (Scope 1, fugitive, annual) ---
    FuelEntry(
        fuel_type="HFC",
        default_unit="Kg",
        energy_factor_gj_per_unit=0.0,  # no energy content
        scope1_factor_tco2_per_unit=None,
        gwp=1430.0,  # R-410A typical, IPCC AR6 GWP-100
        applicable_from="FY24-25",
        source_reference="IPCC AR6 GWP-100",
    ),
    # --- Acetylene (Scope 1, annual) ---
    FuelEntry(
        fuel_type="Acetylene",
        default_unit="Kg",
        energy_factor_gj_per_unit=48.55,  # MJ/kg → GJ/T basis
        scope1_factor_tco2_per_unit=0.00338,  # tCO2/Kg
        applicable_from="FY24-25",
        source_reference="IPCC defaults",
    ),
    # --- Biodiesel (Scope 1, currently zero at most ports) ---
    FuelEntry(
        fuel_type="Biodiesel",
        default_unit="KL",
        energy_factor_gj_per_unit=33.32,
        scope1_factor_tco2_per_unit=0.0,  # biogenic, excluded from scope 1
        applicable_from="FY24-25",
        source_reference="IPCC AR6 — biogenic exclusion",
    ),
]


def get_fuel_registry(fy: str = "FY24-25") -> list[FuelEntry]:
    """Return the fuel registry for a given FY. Currently only FY24-25."""
    if fy == "FY24-25":
        return FY2425_FUEL_REGISTRY
    # Fall back to FY24-25 factors for prior FYs until historical factors diverge
    return FY2425_FUEL_REGISTRY


def get_fuel_entry(fuel_type: str, fy: str = "FY24-25") -> FuelEntry | None:
    """Look up a single fuel entry by type and period."""
    for entry in get_fuel_registry(fy):
        if entry.fuel_type.lower() == fuel_type.lower():
            return entry
    return None
