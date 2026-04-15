"""AttributionTree datatype per spec Section 7.1."""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel


class AttributionNode(BaseModel):
    label: str
    delta_value: float
    delta_pct_of_gap: float
    direction: Literal["increase", "decrease"]
    source_node_ids: list[str]
    children: list["AttributionNode"] = []


class AttributionTree(BaseModel):
    query_type: Literal["spatial", "temporal", "fleet"]
    subjects: tuple[str, ...]
    root_metric: str
    root_value_a: float
    root_value_b: float
    root_gap: float
    root_gap_pct: float
    children: list[AttributionNode]
    excluded_sources: list[str] | None = None
    denominator: dict | None = None
    fact_hash: str
    graph_hash: str

    def hash(self) -> str:
        """Deterministic hash of the attribution tree."""
        data = self.model_dump(mode="json")
        canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()
