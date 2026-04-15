"""Fuel registry — canonical fuel types and their properties."""

from __future__ import annotations

from pydantic import BaseModel


class FuelEntry(BaseModel):
    fuel_type: str
    default_unit: str
    energy_factor_gj_per_unit: float
    scope1_factor_tco2_per_unit: float | None = None
    scope2_factor_tco2_per_unit: float | None = None
    ch4_factor: float | None = None
    n2o_factor: float | None = None
    gwp: float | None = None
    applicable_from: str  # "FY24-25"
    applicable_to: str | None = None
    source_reference: str

    def to_convex_doc(self) -> dict:
        return {
            "fuelType": self.fuel_type,
            "defaultUnit": self.default_unit,
            "energyFactorGjPerUnit": self.energy_factor_gj_per_unit,
            "scope1FactorTco2PerUnit": self.scope1_factor_tco2_per_unit,
            "scope2FactorTco2PerUnit": self.scope2_factor_tco2_per_unit,
            "ch4Factor": self.ch4_factor,
            "n2oFactor": self.n2o_factor,
            "gwp": self.gwp,
            "applicableFrom": self.applicable_from,
            "applicableTo": self.applicable_to,
            "sourceReference": self.source_reference,
        }
