"""Jinja2 narrative templates per query type (spatial, temporal, fleet).

Per spec Section 8: LLM input is the serialized AttributionTree + Jinja2 template
+ pre-formatted numeric strings. Python formats, LLM places.
"""

from __future__ import annotations

TEMPLATE_VERSION = "v1.0"

# --- System prompt rules (spec 8.1) ---
SYSTEM_PROMPT = """You are an emissions attribution analyst producing factual narratives for port sustainability reports.

HARD RULES:
1. Every number in your output must appear verbatim in the AttributionTree data provided.
2. FORBIDDEN words (never use): better, worse, good, bad, efficient, inefficient, improved, deteriorated, optimal, suboptimal, healthy, concerning
3. ALLOWED directional words: higher, lower, increased, decreased, contributed, accounted for, drove, offset
4. Do not make causal claims not present in the attribution tree.
5. If excluded_sources is present, you MUST disclose the exclusion in your closing sentence.
6. Use neutral, factual language suitable for auditor review.
7. Format numbers consistently: intensities to 4 decimal places, percentages to 1 decimal place, absolute emissions to 0 decimal places.
"""

# --- Spatial template ---
SPATIAL_TEMPLATE = """Analyze the following spatial attribution comparing two ports.

## Attribution Data
- Port A: {{ subjects[0] }} — Emission intensity: {{ "%.4f"|format(root_value_a) }} tCO2e/MT
- Port B: {{ subjects[1] }} — Emission intensity: {{ "%.4f"|format(root_value_b) }} tCO2e/MT
- Gap: {{ "%.4f"|format(root_gap) }} tCO2e/MT ({{ "%.1f"|format(root_gap_pct) }}%)
- Cargo A: {{ "%.0f"|format(denominator.cargo_a_mt) }} MT
- Cargo B: {{ "%.0f"|format(denominator.cargo_b_mt) }} MT

## Source-level decomposition (sorted by magnitude):
{% for child in children %}
- {{ child.label }}: {{ "%.4f"|format(child.delta_value) }} tCO2e/MT ({{ "%.1f"|format(child.delta_pct_of_gap) }}% of gap, {{ child.direction }})
{% for sub in child.children %}
  - {{ sub.label }}: {{ "%.4f"|format(sub.delta_value) }} ({{ "%.1f"|format(sub.delta_pct_of_gap) }}% of gap)
{% for subsub in sub.children %}
    - {{ subsub.label }}: {{ "%.4f"|format(subsub.delta_value) }} ({{ "%.1f"|format(subsub.delta_pct_of_gap) }}% of gap)
{% endfor %}
{% endfor %}
{% endfor %}

{% if excluded_sources %}
## Excluded from monthly attribution:
{% for src in excluded_sources %}- {{ src }}
{% endfor %}
{% endif %}

Write a 3-5 sentence factual narrative explaining why {{ subjects[0] }}'s emission intensity is {{ "higher" if root_gap > 0 else "lower" }} than {{ subjects[1] }}'s. Reference the top contributors by name and percentage. If factors are constant across ports, note that the gap is driven by consumption differences per MT of cargo."""

# --- Temporal template ---
TEMPORAL_TEMPLATE = """Analyze the following temporal attribution for a single port across two periods.

## Attribution Data
- Port: {{ subjects[0] }}
- Earlier period ({{ subjects[1] }}): Emission intensity: {{ "%.4f"|format(root_value_a) }} tCO2e/MT
- Later period ({{ subjects[2] }}): Emission intensity: {{ "%.4f"|format(root_value_b) }} tCO2e/MT
- Change: {{ "%.4f"|format(root_gap) }} tCO2e/MT ({{ "%.1f"|format(root_gap_pct) }}%)
- Cargo earlier: {{ "%.0f"|format(denominator.cargo_earlier_mt) }} MT
- Cargo later: {{ "%.0f"|format(denominator.cargo_later_mt) }} MT

## Source-level decomposition:
{% for child in children %}
- {{ child.label }}: {{ "%.4f"|format(child.delta_value) }} tCO2e/MT ({{ "%.1f"|format(child.delta_pct_of_gap) }}% of change, {{ child.direction }})
{% for sub in child.children %}
  - {{ sub.label }}: {{ "%.4f"|format(sub.delta_value) }} ({{ "%.1f"|format(sub.delta_pct_of_gap) }}%)
{% endfor %}
{% endfor %}

{% if excluded_sources %}
## Excluded from monthly attribution:
{% for src in excluded_sources %}- {{ src }}
{% endfor %}
{% endif %}

Write a 3-5 sentence factual narrative describing how {{ subjects[0] }}'s emission intensity changed from {{ subjects[1] }} to {{ subjects[2] }}. Frame chronologically — earlier period first. Reference the top contributors by name and percentage."""

# --- Fleet template ---
FLEET_TEMPLATE = """Analyze the following fleet-level emissions summary.

## Fleet Summary ({{ subjects|length }} ports, current period)
- Highest intensity: {{ "%.4f"|format(root_value_a) }} tCO2e/MT
- Lowest intensity: {{ "%.4f"|format(root_value_b) }} tCO2e/MT
- Spread: {{ "%.4f"|format(root_gap) }} tCO2e/MT
- Median: {{ "%.4f"|format(denominator.fleet_median) }} tCO2e/MT

## Port rankings (by emission intensity, highest first):
{% for child in children %}
- {{ child.label }}: {{ "%.4f"|format(child.delta_value) }} tCO2e/MT{% if child.delta_pct_of_gap %} ({{ "%.1f"|format(child.delta_pct_of_gap) }}% of median){% endif %}
{% endfor %}

## Port details:
{% for pd in denominator.port_details %}
- {{ pd.port_id }}: Cargo {{ "%.0f"|format(pd.cargo_mt) }} MT | Scope 1: {{ "%.0f"|format(pd.scope1_tco2) }} tCO2e | Scope 2: {{ "%.0f"|format(pd.scope2_tco2) }} tCO2e | Intensity: {{ "%.4f"|format(pd.intensity) }}{% if pd.yoy_delta_pct is not none %} | YoY: {{ "%.1f"|format(pd.yoy_delta_pct) }}%{% endif %}
{% endfor %}

Write a 2-3 sentence fleet summary suitable for the dashboard landing page. Mention the highest and lowest intensity ports, the spread, and the fleet median. Keep it factual and concise."""


TEMPLATES = {
    "spatial": SPATIAL_TEMPLATE,
    "temporal": TEMPORAL_TEMPLATE,
    "fleet": FLEET_TEMPLATE,
}
