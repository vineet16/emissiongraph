"""Graph node and edge type definitions per spec Section 6."""

from __future__ import annotations

from enum import Enum


class NodeType(str, Enum):
    PORT = "Port"
    FISCAL_PERIOD = "FiscalPeriod"
    CARGO_THROUGHPUT = "CargoThroughput"
    ENERGY_SOURCE = "EnergySource"
    CONSUMPTION = "Consumption"
    ENERGY_CONTRIBUTION = "EnergyContribution"
    EMISSION_CONTRIBUTION = "EmissionContribution"
    FUGITIVE_SOURCE = "FugitiveSource"
    EMISSION_FACTOR = "EmissionFactor"
    ENERGY_FACTOR = "EnergyFactor"
    INTENSITY_METRIC = "IntensityMetric"


class EdgeType(str, Enum):
    OPERATES_IN = "operates_in"
    HANDLED = "handled"
    CONSUMED = "consumed"
    USING_FACTOR = "using_factor"
    PRODUCES_ENERGY = "produces_energy"
    PRODUCES_EMISSION = "produces_emission"
    CONTRIBUTES_TO = "contributes_to"
    SCOPED_AS = "scoped_as"
