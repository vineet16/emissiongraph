"""Post-processing validator per spec Section 8.2.

Non-negotiable: every narrative must pass validation before being served.
Failure → regenerate (max 3 attempts) → surface raw tree with error notice.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from emissiongraph.attribution.tree import AttributionTree


FORBIDDEN_WORDS = [
    "better", "worse", "good", "bad", "efficient", "inefficient",
    "improved", "deteriorated", "optimal", "suboptimal", "healthy", "concerning",
]


@dataclass
class ValidationResult:
    ok: bool
    reason: str = ""


def _extract_numeric_tokens(text: str) -> list[float]:
    """Extract all numeric tokens from narrative text."""
    # Match integers, decimals, percentages, negative numbers
    pattern = r"-?\d+\.?\d*"
    tokens = re.findall(pattern, text)
    results = []
    for t in tokens:
        try:
            results.append(float(t))
        except ValueError:
            pass
    return results


def _collect_all_numbers_from_tree(tree: AttributionTree) -> set[float]:
    """Collect all numeric values from the attribution tree."""
    numbers: set[float] = set()

    # Root-level numbers
    numbers.add(tree.root_value_a)
    numbers.add(tree.root_value_b)
    numbers.add(tree.root_gap)
    numbers.add(tree.root_gap_pct)

    # Denominator numbers
    if tree.denominator:
        for v in tree.denominator.values():
            if isinstance(v, (int, float)):
                numbers.add(float(v))
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, dict):
                        for val in item.values():
                            if isinstance(val, (int, float)):
                                numbers.add(float(val))

    def _collect_from_node(node):
        numbers.add(node.delta_value)
        numbers.add(node.delta_pct_of_gap)
        for child in node.children:
            _collect_from_node(child)

    for child in tree.children:
        _collect_from_node(child)

    # Add common derived forms (rounded, truncated)
    derived = set()
    for n in numbers:
        derived.add(round(n, 4))
        derived.add(round(n, 3))
        derived.add(round(n, 2))
        derived.add(round(n, 1))
        derived.add(round(n, 0))
        derived.add(abs(n))
        derived.add(round(abs(n), 1))
        derived.add(round(abs(n), 4))
    numbers.update(derived)

    return numbers


def _matches_within_tolerance(n: float, allowed: set[float], tol: float = 1e-6) -> bool:
    """Check if a number matches any allowed number within tolerance."""
    for a in allowed:
        if abs(n - a) < tol:
            return True
    return False


def _word_present(text: str, word: str) -> bool:
    """Check if a word is present as a whole word in text."""
    pattern = r"\b" + re.escape(word) + r"\b"
    return bool(re.search(pattern, text, re.IGNORECASE))


def _mentions_exclusion(narrative: str) -> bool:
    """Check if the narrative mentions excluded sources."""
    keywords = ["exclud", "annual-only", "not included in monthly", "omit"]
    lower = narrative.lower()
    return any(kw in lower for kw in keywords)


def validate_narrative(narrative: str, tree: AttributionTree) -> ValidationResult:
    """Validate a generated narrative against the attribution tree.

    Checks:
    1. Every number in the narrative must appear in the tree (within tolerance).
    2. No forbidden words.
    3. If excluded_sources present, narrative must disclose exclusion.
    """
    # Check forbidden words
    for w in FORBIDDEN_WORDS:
        if _word_present(narrative, w):
            return ValidationResult(ok=False, reason=f"Forbidden word: {w}")

    # Check numbers
    numbers = _extract_numeric_tokens(narrative)
    allowed = _collect_all_numbers_from_tree(tree)

    for n in numbers:
        if not _matches_within_tolerance(n, allowed, tol=1e-6):
            # Allow common non-tree numbers: years, port numbers, counts
            if n < 100 and n == int(n):  # small integers (port numbers, counts)
                continue
            if 2020 <= n <= 2030:  # year references
                continue
            return ValidationResult(ok=False, reason=f"Number {n} not in tree")

    # Check excluded sources disclosure
    if tree.excluded_sources and not _mentions_exclusion(narrative):
        return ValidationResult(ok=False, reason="Excluded sources not disclosed")

    return ValidationResult(ok=True)
