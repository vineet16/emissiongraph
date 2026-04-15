"""GRI sheet parsers for 302-1, 305-1, 305-2, 305-4.

Actual workbook layout — multi-section horizontal:
  Row 3: Section headers across columns:
         B="Electricity Consumed", G="Diesel Consumed", L="Petrol Consumed",
         O="HFHSD & IFO Consumed", R="Other Fuels"
  Row 4: Sub-headers per section (Month, units, etc.)
  Row 5: FY label row
  Rows 6-17: Monthly data (datetime in date col, values in data cols)
  Row 18: "Total" row
  Rows 19+: Summary/derived rows (emissions, intensity, etc.)

Each section has its own date column + data columns.
"Other Fuels" section is a vertical list (Type, Quantity, GJ/tCO2) not a time series.
"""

from __future__ import annotations

from datetime import datetime

from openpyxl.worksheet.worksheet import Worksheet
from openpyxl.workbook import Workbook

from emissiongraph.facts.schema import AmbiguousTotalWarning, CellRef, Measurement
from emissiongraph.ingestion.cargo_parser import (
    _col_letter,
    _datetime_to_period_value,
)


# Section definitions: maps section header patterns to fuel type + extraction info
SECTION_DEFS = [
    {
        "header_pattern": "electricity consumed",
        "fuel_type": "Electricity",
        "unit": "MWH",
        # Columns relative to the section's date column:
        # We extract specific named columns from row 4 headers
        "columns": {
            "thermal": ("Electricity", "thermal", "MWH"),
            "re": ("Electricity", "renewable", "MWH"),
            "total": ("Electricity", None, "MWH"),
        },
        # Note: matching is substring-based within section boundaries.
        # P4 has multi-source layout: Thermal(1)/RE(1)/Total(1)/Thermal(2)/RE(2)/Total(2)
        # The parser picks the last match per pattern, which gives us source (2) or the combined total.
    },
    {
        "header_pattern": "diesel consumed",
        "fuel_type": "Diesel",
        "unit": "KL",
        "columns": {
            "stationary eqp": ("Diesel", "stationary", "KL"),
            "mobile eqp": ("Diesel", "mobile", "KL"),
            "total qty": ("Diesel", None, "KL"),
        },
    },
    {
        "header_pattern": "petrol consumed",
        "fuel_type": "Petrol",
        "unit": "KL",
        "columns": {
            "total qty": ("Petrol", None, "KL"),
        },
    },
    {
        "header_pattern": "hfhsd",
        "fuel_type": "HFHSD",
        "unit": "KL",
        "columns": {
            "total qty": ("HFHSD", None, "KL"),
        },
    },
]


def _find_section_boundaries(ws: Worksheet) -> list[int]:
    """Find the start column of each section from row 3 headers.

    Returns sorted list of 1-based column indices where sections begin.
    """
    boundaries = []
    for col_idx in range(1, (ws.max_column or 30) + 1):
        val = ws.cell(row=3, column=col_idx).value
        if val and isinstance(val, str) and val.strip():
            boundaries.append(col_idx)
    return sorted(boundaries)


def _find_sections(ws: Worksheet) -> list[dict]:
    """Scan row 3 for section headers and row 4 for column sub-headers.

    Returns a list of section dicts with:
      - fuel_type, unit
      - date_col: 1-based column index for the "Month" column
      - data_cols: list of (col_idx, fuel_type, sub_type, unit)
    """
    sections = []
    boundaries = _find_section_boundaries(ws)
    sub_header_row = 4

    for b_idx, col_idx in enumerate(boundaries):
        val = ws.cell(row=3, column=col_idx).value
        if not val or not isinstance(val, str):
            continue

        val_lower = val.strip().lower()

        # Determine the end of this section (start of next section, or max_column)
        if b_idx + 1 < len(boundaries):
            section_end = boundaries[b_idx + 1]
        else:
            section_end = (ws.max_column or 30) + 1

        for sdef in SECTION_DEFS:
            if sdef["header_pattern"] in val_lower:
                date_col = None
                data_cols = []

                # Scan only within this section's boundaries
                for sc in range(col_idx, section_end):
                    sub_val = ws.cell(row=sub_header_row, column=sc).value
                    if not sub_val or not isinstance(sub_val, str):
                        continue
                    sub_lower = sub_val.strip().lower()

                    if sub_lower == "month":
                        date_col = sc
                    else:
                        for pattern, (ft, st, unit) in sdef["columns"].items():
                            if pattern in sub_lower:
                                data_cols.append((sc, ft, st, unit))
                                break

                if date_col and data_cols:
                    sections.append({
                        "fuel_type": sdef["fuel_type"],
                        "date_col": date_col,
                        "data_cols": data_cols,
                    })
                break

    return sections


def _find_other_fuels_section(ws: Worksheet) -> dict | None:
    """Find the 'Other Fuels' section which has a vertical Type/Quantity layout."""
    header_row = 3
    sub_header_row = 4

    for col_idx in range(1, (ws.max_column or 30) + 1):
        val = ws.cell(row=header_row, column=col_idx).value
        if val and isinstance(val, str) and "other fuels" in val.strip().lower():
            # Find Type, Quantity, GJ/tCO2 columns
            type_col = None
            qty_col = None
            value_col = None

            for sc in range(col_idx, min(col_idx + 5, (ws.max_column or 30) + 1)):
                sub_val = ws.cell(row=sub_header_row, column=sc).value
                if not sub_val or not isinstance(sub_val, str):
                    continue
                sub_lower = sub_val.strip().lower()
                if sub_lower == "type":
                    type_col = sc
                elif "quantity" in sub_lower:
                    qty_col = sc
                elif sub_lower in ("gj", "tco2"):
                    value_col = sc

            if type_col and (qty_col or value_col):
                return {
                    "type_col": type_col,
                    "qty_col": qty_col,
                    "value_col": value_col,
                }
    return None


# Fuel type normalization for "Other Fuels" entries
OTHER_FUEL_NORMALIZE = {
    "acetylene": ("Acetylene", "Kg"),
    "lpg": ("LPG", "T"),
    "coal": ("Coal", "T"),
    "hfcs": ("HFC", "Kg"),
    "hfc": ("HFC", "Kg"),
    "co2 fire extinguisher": ("CO2_Extinguisher", "Kg"),
}


def parse_energy_sheet(
    ws: Worksheet,
    port_id: str,
    fy: str,
    workbook_name: str,
    sheet_name: str = "302-1",
) -> tuple[list[Measurement], list[AmbiguousTotalWarning]]:
    """Parse a GRI sheet with multi-section horizontal layout.

    Works for 302-1, 305-1, 305-2, 305-4.
    """
    measurements: list[Measurement] = []
    warnings: list[AmbiguousTotalWarning] = []

    sections = _find_sections(ws)

    # Parse monthly data for each section
    for section in sections:
        date_col = section["date_col"]

        # Find data rows: start after FY label row, stop at Total
        data_start = None
        data_end = None

        for row_idx in range(5, (ws.max_row or 50) + 1):
            date_cell = ws.cell(row=row_idx, column=date_col).value

            if date_cell is None:
                continue

            # Skip FY label row
            if isinstance(date_cell, str) and date_cell.strip().upper().startswith("FY"):
                continue

            # Stop at Total
            if isinstance(date_cell, str) and "total" in date_cell.strip().lower():
                data_end = row_idx
                break

            # First datetime = data start
            if data_start is None:
                if isinstance(date_cell, datetime):
                    data_start = row_idx
                elif isinstance(date_cell, str):
                    try:
                        datetime.fromisoformat(date_cell.split(" ")[0])
                        data_start = row_idx
                    except (ValueError, IndexError):
                        continue

        if data_start is None:
            continue
        if data_end is None:
            data_end = min(data_start + 12, (ws.max_row or 50) + 1)

        # Extract measurements for each data column
        for col_idx, fuel_type, sub_type, unit in section["data_cols"]:
            for row_idx in range(data_start, data_end):
                date_cell = ws.cell(row=row_idx, column=date_col).value

                # Parse datetime
                if isinstance(date_cell, datetime):
                    period_value = _datetime_to_period_value(date_cell)
                elif isinstance(date_cell, str):
                    try:
                        dt = datetime.fromisoformat(date_cell.split(" ")[0])
                        period_value = _datetime_to_period_value(dt)
                    except (ValueError, IndexError):
                        continue
                else:
                    continue

                # Parse value
                val_cell = ws.cell(row=row_idx, column=col_idx).value
                qty = 0.0
                if val_cell is not None:
                    if isinstance(val_cell, str) and val_cell.strip() == "-":
                        qty = 0.0
                    else:
                        try:
                            qty = float(val_cell)
                        except (ValueError, TypeError):
                            continue

                measurements.append(Measurement(
                    port_id=port_id,
                    fy=fy,
                    period="monthly",
                    period_value=period_value,
                    fuel_type=fuel_type,
                    sub_type=sub_type,
                    measure="consumption",
                    quantity=qty,
                    unit=unit,
                    source_cell=CellRef(
                        workbook=workbook_name,
                        sheet=sheet_name,
                        cell=f"{_col_letter(col_idx)}{row_idx}",
                        row=row_idx,
                        col=col_idx,
                    ),
                ))

    # Parse "Other Fuels" section (vertical type list, annual values)
    other = _find_other_fuels_section(ws)
    if other:
        type_col = other["type_col"]
        qty_col = other.get("qty_col")
        value_col = other.get("value_col")

        for row_idx in range(5, (ws.max_row or 30) + 1):
            type_cell = ws.cell(row=row_idx, column=type_col).value
            if not type_cell or not isinstance(type_cell, str):
                continue

            type_lower = type_cell.strip().lower()

            # Skip header-like rows and total rows
            if type_lower in ("type", "") or "total" in type_lower or "energy" in type_lower:
                continue

            # Normalize fuel type
            normalized = OTHER_FUEL_NORMALIZE.get(type_lower)
            if normalized:
                fuel_type, unit = normalized
            else:
                fuel_type = type_cell.strip()
                unit = "T"

            # Get quantity
            read_col = qty_col or value_col
            if not read_col:
                continue

            val = ws.cell(row=row_idx, column=read_col).value
            qty = 0.0
            if val is not None:
                try:
                    qty = float(val)
                except (ValueError, TypeError):
                    continue

            measurements.append(Measurement(
                port_id=port_id,
                fy=fy,
                period="annual",
                period_value=fy,
                fuel_type=fuel_type,
                sub_type=None,
                measure="consumption",
                quantity=qty,
                unit=unit,
                source_cell=CellRef(
                    workbook=workbook_name,
                    sheet=sheet_name,
                    cell=f"{_col_letter(read_col)}{row_idx}",
                    row=row_idx,
                    col=read_col,
                ),
            ))

    return measurements, warnings


def parse_emissions_sheet(
    ws: Worksheet,
    port_id: str,
    fy: str,
    workbook_name: str,
    sheet_name: str,
    scope: str,
) -> tuple[list[Measurement], list[AmbiguousTotalWarning]]:
    """Parse GRI 305-1 (Scope 1) or 305-2 (Scope 2) emissions sheets.

    Same multi-section layout as 302-1. We parse the consumption quantities;
    emission totals in rows 19+ are derived values we don't store as facts.
    """
    return parse_energy_sheet(ws, port_id, fy, workbook_name, sheet_name)


def parse_intensity_sheet(
    ws: Worksheet,
    port_id: str,
    fy: str,
    workbook_name: str,
) -> tuple[list[Measurement], list[AmbiguousTotalWarning]]:
    """Parse GRI 305-4 intensity metrics sheet.

    Same layout — we parse consumption data. Intensity metrics in summary rows
    are derived values verified downstream.
    """
    return parse_energy_sheet(ws, port_id, fy, workbook_name, "305-4")


def parse_workbook(
    wb: Workbook,
    port_id: str,
    fy: str,
    workbook_name: str,
) -> tuple[list[Measurement], list[AmbiguousTotalWarning]]:
    """Parse all GRI sheets from a workbook, deduplicating across sheets.

    Deduplication key: (port_id, fy, period_value, fuel_type, sub_type).
    The deterministic UUID5 on Measurement handles this automatically.
    """
    all_measurements: dict[str, Measurement] = {}
    all_warnings: list[AmbiguousTotalWarning] = []

    from emissiongraph.ingestion.cargo_parser import parse_cargo_sheet
    from emissiongraph.ingestion.workbook_loader import get_sheet

    # Parse Cargo Handled
    cargo_ws = get_sheet(wb, "Cargo Handled")
    if cargo_ws:
        for m in parse_cargo_sheet(cargo_ws, port_id, fy, workbook_name):
            all_measurements[m.id] = m

    # Parse 302-1 (Energy consumption) — primary source for fuel quantities
    energy_ws = get_sheet(wb, "302-1")
    if energy_ws:
        ms, ws_ = parse_energy_sheet(energy_ws, port_id, fy, workbook_name, "302-1")
        for m in ms:
            all_measurements[m.id] = m
        all_warnings.extend(ws_)

    # Parse 305-1 (Scope 1 emissions)
    scope1_ws = get_sheet(wb, "305-1")
    if scope1_ws:
        ms, ws_ = parse_emissions_sheet(scope1_ws, port_id, fy, workbook_name, "305-1", "scope1")
        for m in ms:
            if m.id not in all_measurements:
                all_measurements[m.id] = m
        all_warnings.extend(ws_)

    # Parse 305-2 (Scope 2 emissions)
    scope2_ws = get_sheet(wb, "305-2")
    if scope2_ws:
        ms, ws_ = parse_emissions_sheet(scope2_ws, port_id, fy, workbook_name, "305-2", "scope2")
        for m in ms:
            if m.id not in all_measurements:
                all_measurements[m.id] = m
        all_warnings.extend(ws_)

    # Parse 305-4 (Intensity — for verification only)
    intensity_ws = get_sheet(wb, "305-4")
    if intensity_ws:
        ms, ws_ = parse_intensity_sheet(intensity_ws, port_id, fy, workbook_name)
        for m in ms:
            all_measurements[m.id] = m
        all_warnings.extend(ws_)

    return list(all_measurements.values()), all_warnings
