"""Shared test fixtures — synthetic measurement data for two ports."""

from __future__ import annotations

import pytest

from emissiongraph.facts.schema import CellRef, Measurement
from emissiongraph.registry.factors import get_fuel_registry


def _make_measurement(
    port_id: str,
    fy: str,
    month: str,
    fuel_type: str,
    quantity: float,
    unit: str = "KL",
    sub_type: str | None = None,
    period: str = "monthly",
    measure: str = "consumption",
) -> Measurement:
    return Measurement(
        port_id=port_id,
        fy=fy,
        period=period,
        period_value=month if period == "monthly" else fy,
        fuel_type=fuel_type,
        sub_type=sub_type,
        measure=measure,
        quantity=quantity,
        unit=unit,
        source_cell=CellRef(
            workbook=f"{port_id}_{fy}.xlsx",
            sheet="302-1",
            cell="C5",
            row=5,
            col=3,
        ),
    )


@pytest.fixture
def sample_measurements() -> list[Measurement]:
    """Two ports (P1, P10) with FY24-25 data, enough for spatial attribution."""
    ms = []

    # P1: Higher intensity port
    for month in ["2024-04", "2024-05", "2024-06"]:
        ms.append(_make_measurement("P1", "FY24-25", month, "Cargo", 500000, "MT"))
        ms.append(_make_measurement("P1", "FY24-25", month, "Electricity", 3000, "MWH"))
        ms.append(_make_measurement("P1", "FY24-25", month, "Diesel", 150, sub_type="stationary"))
        ms.append(_make_measurement("P1", "FY24-25", month, "Diesel", 80, sub_type="mobile"))
        ms.append(_make_measurement("P1", "FY24-25", month, "Petrol", 20))

    # P1 annual HFC
    ms.append(_make_measurement("P1", "FY24-25", "", "HFC", 50, "Kg",
                                 period="annual", measure="fugitive_release"))

    # P10: Lower intensity port
    for month in ["2024-04", "2024-05", "2024-06"]:
        ms.append(_make_measurement("P10", "FY24-25", month, "Cargo", 800000, "MT"))
        ms.append(_make_measurement("P10", "FY24-25", month, "Electricity", 2500, "MWH"))
        ms.append(_make_measurement("P10", "FY24-25", month, "Diesel", 100, sub_type="stationary"))
        ms.append(_make_measurement("P10", "FY24-25", month, "Diesel", 40, sub_type="mobile"))
        ms.append(_make_measurement("P10", "FY24-25", month, "Petrol", 10))

    # P10 annual HFC
    ms.append(_make_measurement("P10", "FY24-25", "", "HFC", 30, "Kg",
                                 period="annual", measure="fugitive_release"))

    return ms


@pytest.fixture
def fuel_registry():
    return get_fuel_registry("FY24-25")
