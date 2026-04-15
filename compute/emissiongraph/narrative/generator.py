"""Narrative generator — LLM call with structured output + validator gate.

Per spec Section 8:
- LLM input: serialized AttributionTree + Jinja2 template + pre-formatted numbers
- Post-processing validator is non-negotiable
- Failure → regenerate (max 3 attempts) → surface raw tree with error
- Caching: keyed by (treeHash, templateVersion)
"""

from __future__ import annotations

import os

import jinja2

from emissiongraph.attribution.tree import AttributionTree
from emissiongraph.narrative.templates import SYSTEM_PROMPT, TEMPLATES, TEMPLATE_VERSION
from emissiongraph.narrative.validator import ValidationResult, validate_narrative

MAX_RETRIES = 3


def _render_prompt(tree: AttributionTree) -> str:
    """Render the Jinja2 template with tree data."""
    template_str = TEMPLATES.get(tree.query_type)
    if not template_str:
        raise ValueError(f"No template for query type: {tree.query_type}")

    env = jinja2.Environment(undefined=jinja2.StrictUndefined)
    template = env.from_string(template_str)

    tree_data = tree.model_dump(mode="json")
    return template.render(**tree_data)


async def generate_narrative(
    tree: AttributionTree,
    api_key: str | None = None,
) -> tuple[str, ValidationResult]:
    """Generate a narrative for an attribution tree using Groq.

    Returns (narrative_text, validation_result).
    On validation failure after MAX_RETRIES, returns empty string with failure result.
    """
    from openai import OpenAI

    client = OpenAI(
        api_key=api_key or os.environ.get("GROQ_API_KEY"),
        base_url="https://api.groq.com/openai/v1",
    )
    prompt = _render_prompt(tree)

    for attempt in range(MAX_RETRIES):
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=1024,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )

        narrative = response.choices[0].message.content
        result = validate_narrative(narrative, tree)

        if result.ok:
            return narrative, result

        prompt = (
            f"{prompt}\n\n"
            f"VALIDATION FAILED (attempt {attempt + 1}): {result.reason}\n"
            "Please regenerate the narrative fixing this issue."
        )

    return "", ValidationResult(ok=False, reason=f"Failed after {MAX_RETRIES} attempts")


def generate_narrative_sync(
    tree: AttributionTree,
    api_key: str | None = None,
) -> tuple[str, ValidationResult]:
    """Synchronous wrapper for narrative generation."""
    import asyncio
    return asyncio.run(generate_narrative(tree, api_key))


def get_template_version() -> str:
    return TEMPLATE_VERSION
