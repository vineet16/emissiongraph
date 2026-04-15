"""Pydantic models mirroring the Convex schema — single source of truth for Python side."""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class CellRef(BaseModel):
    """Exact cell reference in a source workbook."""

    workbook: str
    sheet: str
    cell: str  # e.g. "C5"
    row: int
    col: int


class Measurement(BaseModel):
    """A single parsed measurement from a GRI workbook.

    The id is a deterministic UUID5 derived from the deduplication key:
    (port_id, fy, period_value, fuel_type, sub_type, measure).
    """

    id: str = ""
    port_id: str  # P1..P10
    fy: str  # "FY24-25"
    period: Literal["monthly", "annual"]
    period_value: str  # "2024-04" or "FY24-25"
    fuel_type: str  # registry-driven
    sub_type: str | None = None  # "stationary", "mobile", or None
    measure: Literal["consumption", "fugitive_release"] = "consumption"
    quantity: float
    unit: str  # "MWH", "KL", "T", "Kg"
    source_cell: CellRef
    confidence: Literal["EXTRACTED", "INFERRED", "AMBIGUOUS"] = "EXTRACTED"

    @model_validator(mode="after")
    def _set_deterministic_id(self) -> "Measurement":
        if not self.id:
            key = f"{self.port_id}|{self.fy}|{self.period_value}|{self.fuel_type}|{self.sub_type}|{self.measure}"
            self.id = str(uuid.uuid5(uuid.NAMESPACE_URL, key))
        return self

    def to_convex_doc(self) -> dict:
        """Convert to the shape expected by Convex measurements table."""
        return {
            "measurementId": self.id,
            "portId": self.port_id,
            "fy": self.fy,
            "period": self.period,
            "periodValue": self.period_value,
            "fuelType": self.fuel_type,
            "subType": self.sub_type,
            "measure": self.measure,
            "quantity": self.quantity,
            "unit": self.unit,
            "sourceCell": {
                "workbook": self.source_cell.workbook,
                "sheet": self.source_cell.sheet,
                "cell": self.source_cell.cell,
                "row": self.source_cell.row,
                "col": self.source_cell.col,
            },
            "confidence": self.confidence,
        }


class AmbiguousTotalWarning(BaseModel):
    """Raised when a parsed total disagrees with the recomputed sum by >0.5%."""

    sheet: str
    row_label: str
    parsed_total: float
    computed_total: float
    pct_diff: float


class IngestionResult(BaseModel):
    """Output of parsing a single workbook."""

    port_id: str
    fy: str
    workbook_filename: str
    measurements: list[Measurement]
    warnings: list[AmbiguousTotalWarning] = Field(default_factory=list)

    def fact_hash(self) -> str:
        """SHA-256 of canonical JSON of sorted measurements. Determinism invariant."""
        sorted_ms = sorted(self.measurements, key=lambda m: m.id)
        canonical = json.dumps(
            [m.model_dump(mode="json") for m in sorted_ms],
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode()).hexdigest()
