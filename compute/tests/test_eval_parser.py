"""
Eval harness — runs the parser against all 10 port workbooks and diffs against
ground-truth headline numbers.

Pass criterion: every field within 0.5% relative tolerance.
"""

import os
import pytest
from dataclasses import asdict
from emissiongraph.ingestion.emission_parser import parse_workbook

UPLOADS_DIR = "/Users/vineet/Downloads/Draft Data"

GROUND_TRUTH = {
    'P1':  {'cargo_mt': 3058783.23,    'total_emissions_tco2e': 3060.29,    'scope2_electricity_tco2e': 18.7130,    'scope1_diesel_stationary_tco2e': 2074.1104,  'scope1_diesel_mobile_tco2e': 15.8547,    'scope1_petrol_tco2e': 0.5189,  'scope1_hfhsd_ifo_tco2e': 951.0930,  'scope1_other_fuels_tco2e': 0.0,     'ghg_intensity_kg_per_mt': 1.0005},
    'P2':  {'cargo_mt': 6078496.00,    'total_emissions_tco2e': 6748.63,    'scope2_electricity_tco2e': 521.3710,   'scope1_diesel_stationary_tco2e': 23.1329,    'scope1_diesel_mobile_tco2e': 6176.1856,  'scope1_petrol_tco2e': 20.7886, 'scope1_hfhsd_ifo_tco2e': 0.0,       'scope1_other_fuels_tco2e': 7.1517,  'ghg_intensity_kg_per_mt': 1.1102},
    'P3':  {'cargo_mt': 20985571.88,   'total_emissions_tco2e': 9764.72,    'scope2_electricity_tco2e': 8326.3955,  'scope1_diesel_stationary_tco2e': 6.6640,     'scope1_diesel_mobile_tco2e': 1426.5038,  'scope1_petrol_tco2e': 0.0,     'scope1_hfhsd_ifo_tco2e': 0.0,       'scope1_other_fuels_tco2e': 5.16,    'ghg_intensity_kg_per_mt': 0.4653},
    'P4':  {'cargo_mt': 14029190.01,   'total_emissions_tco2e': 7011.93,    'scope2_electricity_tco2e': 3768.6708,  'scope1_diesel_stationary_tco2e': 34.5187,    'scope1_diesel_mobile_tco2e': 3202.0463,  'scope1_petrol_tco2e': 0.0,     'scope1_hfhsd_ifo_tco2e': 0.0,       'scope1_other_fuels_tco2e': 6.6907,  'ghg_intensity_kg_per_mt': 0.4998},
    'P5':  {'cargo_mt': 25331318.22,   'total_emissions_tco2e': 31211.66,   'scope2_electricity_tco2e': 20798.0981, 'scope1_diesel_stationary_tco2e': 6.2737,     'scope1_diesel_mobile_tco2e': 3023.4403,  'scope1_petrol_tco2e': 3.0928,  'scope1_hfhsd_ifo_tco2e': 7305.3680, 'scope1_other_fuels_tco2e': 75.388,  'ghg_intensity_kg_per_mt': 1.2321},
    'P6':  {'cargo_mt': 3142491.86,    'total_emissions_tco2e': 1578.22,    'scope2_electricity_tco2e': 70.4810,    'scope1_diesel_stationary_tco2e': 46.0250,    'scope1_diesel_mobile_tco2e': 1453.3011,  'scope1_petrol_tco2e': 0.0,     'scope1_hfhsd_ifo_tco2e': 0.0,       'scope1_other_fuels_tco2e': 8.4162,  'ghg_intensity_kg_per_mt': 0.5022},
    'P7':  {'cargo_mt': 5571548.22,    'total_emissions_tco2e': 444.33,     'scope2_electricity_tco2e': 205.9297,   'scope1_diesel_stationary_tco2e': 8.8297,     'scope1_diesel_mobile_tco2e': 229.5656,   'scope1_petrol_tco2e': 0.0,     'scope1_hfhsd_ifo_tco2e': 0.0,       'scope1_other_fuels_tco2e': 0.0,     'ghg_intensity_kg_per_mt': 0.0797},
    'P8':  {'cargo_mt': 20444510.16,   'total_emissions_tco2e': 26453.43,   'scope2_electricity_tco2e': 26451.2189, 'scope1_diesel_stationary_tco2e': 2.1776,     'scope1_diesel_mobile_tco2e': 0.0,        'scope1_petrol_tco2e': 0.0,     'scope1_hfhsd_ifo_tco2e': 0.0,       'scope1_other_fuels_tco2e': 0.029,   'ghg_intensity_kg_per_mt': 1.2939},
    'P9':  {'cargo_mt': 9467334.41,    'total_emissions_tco2e': 9179.80,    'scope2_electricity_tco2e': 9176.1890,  'scope1_diesel_stationary_tco2e': 1.3519,     'scope1_diesel_mobile_tco2e': 0.0,        'scope1_petrol_tco2e': 0.0,     'scope1_hfhsd_ifo_tco2e': 0.0,       'scope1_other_fuels_tco2e': 2.256,   'ghg_intensity_kg_per_mt': 0.9696},
    'P10': {'cargo_mt': 7749956.06,    'total_emissions_tco2e': 9309.93,    'scope2_electricity_tco2e': 8127.9084,  'scope1_diesel_stationary_tco2e': 101.0617,   'scope1_diesel_mobile_tco2e': 1060.1515,  'scope1_petrol_tco2e': 8.5126,  'scope1_hfhsd_ifo_tco2e': 0.0,       'scope1_other_fuels_tco2e': 12.2964, 'ghg_intensity_kg_per_mt': 1.2013},
}

REL_TOL = 0.005
ABS_TOL = 0.5


def is_match(parsed, expected):
    if abs(expected) < 1.0:
        return abs(parsed - expected) < ABS_TOL
    return abs(parsed - expected) / abs(expected) < REL_TOL


@pytest.mark.parametrize("port_id", [f"P{i}" for i in range(1, 11)])
def test_headline_metrics(port_id):
    path = os.path.join(UPLOADS_DIR, f"{port_id}Data.xlsx")
    if not os.path.exists(path):
        pytest.skip(f"{path} not found")

    m = parse_workbook(path, port_id)
    parsed = asdict(m)
    truth = GROUND_TRUTH[port_id]

    for field, expected in truth.items():
        actual = parsed[field]
        assert is_match(actual, expected), (
            f"{port_id}.{field}: parsed={actual:.4f} expected={expected:.4f}"
        )
