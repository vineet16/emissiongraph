"""Narrative validator tests."""

from __future__ import annotations

from emissiongraph.attribution.tree import AttributionNode, AttributionTree
from emissiongraph.narrative.validator import validate_narrative


def _make_tree() -> AttributionTree:
    return AttributionTree(
        query_type="spatial",
        subjects=("P1", "P10"),
        root_metric="emission_intensity",
        root_value_a=0.1810,
        root_value_b=0.1530,
        root_gap=0.0280,
        root_gap_pct=18.3,
        children=[
            AttributionNode(
                label="Electricity",
                delta_value=0.0150,
                delta_pct_of_gap=53.6,
                direction="increase",
                source_node_ids=["n1", "n2"],
            ),
            AttributionNode(
                label="Diesel",
                delta_value=0.0130,
                delta_pct_of_gap=46.4,
                direction="increase",
                source_node_ids=["n3", "n4"],
            ),
        ],
        excluded_sources=["HFC"],
        fact_hash="abc",
        graph_hash="def",
    )


def test_valid_narrative():
    tree = _make_tree()
    narrative = (
        "P1's emission intensity of 0.1810 tCO2e/MT is 0.0280 higher than "
        "P10's 0.1530 tCO2e/MT, a gap of 18.3%. "
        "Electricity accounted for 53.6% of the gap, contributing 0.0150 tCO2e/MT. "
        "Diesel contributed 0.0130 tCO2e/MT (46.4%). "
        "HFC emissions are excluded from monthly attribution as an annual-only source."
    )
    result = validate_narrative(narrative, tree)
    assert result.ok


def test_forbidden_word_rejected():
    tree = _make_tree()
    narrative = "P1 has better efficiency than P10."
    result = validate_narrative(narrative, tree)
    assert not result.ok
    assert "Forbidden word" in result.reason


def test_hallucinated_number_rejected():
    tree = _make_tree()
    narrative = (
        "P1's emission intensity of 0.1810 tCO2e/MT is 0.0280 higher. "
        "The 99.99% contribution comes from electricity. "
        "HFC excluded from monthly analysis."
    )
    result = validate_narrative(narrative, tree)
    assert not result.ok
    assert "not in tree" in result.reason


def test_missing_exclusion_rejected():
    tree = _make_tree()
    narrative = (
        "P1's emission intensity of 0.1810 tCO2e/MT is 0.0280 higher than "
        "P10's 0.1530 tCO2e/MT."
    )
    result = validate_narrative(narrative, tree)
    assert not result.ok
    assert "Excluded sources" in result.reason
