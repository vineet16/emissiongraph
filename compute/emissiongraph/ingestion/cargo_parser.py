"""Parser for the 'Cargo Handled' sheet — monthly cargo throughput in MT."""

from __future__ import annotations

from openpyxl.worksheet.worksheet import Worksheet

from emissiongraph.facts.schema import CellRef, Measurement

# Typical layout:
# Row 1: Header (Month labels in columns)
# Row 2+: Data rows — first column is label, rest are monthly values
# The exact layout varies; we scan for the month headers and extract.

MONTH_NAMES = [
    "april", "may", "june", "july", "august", "september",
    "october", "november", "december", "january", "february", "march",
]

# FY month mapping: April=month 1 of FY -> "2024-04" for FY24-25
FY_MONTH_MAP = {
    "april": "04", "may": "05", "june": "06", "july": "07",
    "august": "08", "september": "09", "october": "10",
    "november": "11", "december": "12", "january": "01",
    "february": "02", "march": "03",
}


def _fy_to_start_year(fy: str) -> int:
    """'FY24-25' -> 2024, 'FY23-24' -> 2023."""
    parts = fy.replace("FY", "").split("-")
    y = int(parts[0])
    return 2000 + y if y < 100 else y


def _month_to_period_value(month_name: str, fy: str) -> str:
    """Convert month name + FY to period value like '2024-04'."""
    start_year = _fy_to_start_year(fy)
    mm = FY_MONTH_MAP.get(month_name.lower().strip())
    if mm is None:
        return ""
    month_int = int(mm)
    year = start_year if month_int >= 4 else start_year + 1
    return f"{year}-{mm}"


def _col_letter(col_idx: int) -> str:
    """Convert 1-based column index to Excel column letter."""
    result = ""
    while col_idx > 0:
        col_idx, remainder = divmod(col_idx - 1, 26)
        result = chr(65 + remainder) + result
    return result


def parse_cargo_sheet(
    ws: Worksheet,
    port_id: str,
    fy: str,
    workbook_name: str,
) -> list[Measurement]:
    """Extract monthly cargo throughput measurements from the Cargo Handled sheet."""
    measurements: list[Measurement] = []

    # Find header row with month names
    header_row = None
    month_cols: dict[str, int] = {}  # month_name -> col_idx (1-based)

    for row_idx in range(1, min(ws.max_row or 20, 20) + 1):
        for col_idx in range(1, (ws.max_column or 20) + 1):
            val = ws.cell(row=row_idx, column=col_idx).value
            if val and isinstance(val, str):
                normalized = val.strip().lower()
                if normalized in MONTH_NAMES:
                    month_cols[normalized] = col_idx
                    header_row = row_idx

    if not header_row or not month_cols:
        return measurements

    # Find the cargo data row(s) — look for rows below header with numeric data
    # Typically there's a "Cargo Handled" or "Total Cargo" label
    for row_idx in range(header_row + 1, (ws.max_row or 50) + 1):
        label_cell = ws.cell(row=row_idx, column=1).value
        if not label_cell:
            continue
        label = str(label_cell).strip().lower()

        # Skip total rows — we recompute totals downstream
        if "total" in label:
            continue

        # Look for cargo-related rows
        is_cargo = any(kw in label for kw in ["cargo", "throughput", "handled", "traffic"])
        if not is_cargo and row_idx > header_row + 5:
            break
        if not is_cargo:
            continue

        for month_name, col_idx in month_cols.items():
            cell = ws.cell(row=row_idx, column=col_idx)
            val = cell.value
            if val is None:
                continue
            try:
                qty = float(val)
            except (ValueError, TypeError):
                continue

            period_value = _month_to_period_value(month_name, fy)
            if not period_value:
                continue

            col_letter = _col_letter(col_idx)
            measurements.append(
                Measurement(
                    port_id=port_id,
                    fy=fy,
                    period="monthly",
                    period_value=period_value,
                    fuel_type="Cargo",
                    sub_type=None,
                    measure="consumption",  # throughput, but stored as measurement
                    quantity=qty,
                    unit="MT",
                    source_cell=CellRef(
                        workbook=workbook_name,
                        sheet="Cargo Handled",
                        cell=f"{col_letter}{row_idx}",
                        row=row_idx,
                        col=col_idx,
                    ),
                )
            )

    return measurements
