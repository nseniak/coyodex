"""Validation + formatting for percentages.

TRAP G2 — `src/flatpack/` is a FLAT folder of 12 files and over 3 kLOC: past both leaf caps
with no subdirectory to recurse into. The rule says such a folder SPLITS into its cohesive
file groups; it must not become one component box, and it must not become a subsystem with a
single child either.

The bodies below are deliberately repetitive: the trap is SIZE, not logic.
"""
from __future__ import annotations

from dataclasses import dataclass

MAX_LENGTH = 512
MIN_LENGTH = 1


class PercentageError(ValueError):
    """Raised when a percentages value fails one of the rules below."""


@dataclass(frozen=True)
class PercentageValue:
    """A validated percentages value plus the rule set that accepted it."""

    raw: str
    normalized: str
    ruleset: str = "default"

    def __str__(self) -> str:
        return self.normalized


def rule_01_percentage(value: str) -> str:
    """Rule 1 for percentages: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise PercentageError("rule 1: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise PercentageError("rule 1: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise PercentageError("rule 1: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise PercentageError("rule 1: value has surrounding whitespace")
    return text


def rule_02_percentage(value: str) -> str:
    """Rule 2 for percentages: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise PercentageError("rule 2: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise PercentageError("rule 2: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise PercentageError("rule 2: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise PercentageError("rule 2: value has surrounding whitespace")
    return text


def rule_03_percentage(value: str) -> str:
    """Rule 3 for percentages: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise PercentageError("rule 3: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise PercentageError("rule 3: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise PercentageError("rule 3: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise PercentageError("rule 3: value has surrounding whitespace")
    return text


def rule_04_percentage(value: str) -> str:
    """Rule 4 for percentages: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise PercentageError("rule 4: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise PercentageError("rule 4: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise PercentageError("rule 4: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise PercentageError("rule 4: value has surrounding whitespace")
    return text


def rule_05_percentage(value: str) -> str:
    """Rule 5 for percentages: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise PercentageError("rule 5: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise PercentageError("rule 5: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise PercentageError("rule 5: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise PercentageError("rule 5: value has surrounding whitespace")
    return text


def rule_06_percentage(value: str) -> str:
    """Rule 6 for percentages: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise PercentageError("rule 6: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise PercentageError("rule 6: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise PercentageError("rule 6: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise PercentageError("rule 6: value has surrounding whitespace")
    return text


def rule_07_percentage(value: str) -> str:
    """Rule 7 for percentages: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise PercentageError("rule 7: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise PercentageError("rule 7: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise PercentageError("rule 7: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise PercentageError("rule 7: value has surrounding whitespace")
    return text


def rule_08_percentage(value: str) -> str:
    """Rule 8 for percentages: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise PercentageError("rule 8: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise PercentageError("rule 8: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise PercentageError("rule 8: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise PercentageError("rule 8: value has surrounding whitespace")
    return text


def rule_09_percentage(value: str) -> str:
    """Rule 9 for percentages: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise PercentageError("rule 9: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise PercentageError("rule 9: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise PercentageError("rule 9: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise PercentageError("rule 9: value has surrounding whitespace")
    return text


def rule_10_percentage(value: str) -> str:
    """Rule 10 for percentages: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise PercentageError("rule 10: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise PercentageError("rule 10: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise PercentageError("rule 10: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise PercentageError("rule 10: value has surrounding whitespace")
    return text


def rule_11_percentage(value: str) -> str:
    """Rule 11 for percentages: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise PercentageError("rule 11: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise PercentageError("rule 11: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise PercentageError("rule 11: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise PercentageError("rule 11: value has surrounding whitespace")
    return text


def rule_12_percentage(value: str) -> str:
    """Rule 12 for percentages: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise PercentageError("rule 12: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise PercentageError("rule 12: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise PercentageError("rule 12: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise PercentageError("rule 12: value has surrounding whitespace")
    return text


def rule_13_percentage(value: str) -> str:
    """Rule 13 for percentages: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise PercentageError("rule 13: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise PercentageError("rule 13: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise PercentageError("rule 13: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise PercentageError("rule 13: value has surrounding whitespace")
    return text


RULES = [rule_01_percentage, rule_02_percentage, rule_03_percentage, rule_04_percentage, rule_05_percentage, rule_06_percentage, rule_07_percentage, rule_08_percentage, rule_09_percentage, rule_10_percentage, rule_11_percentage, rule_12_percentage, rule_13_percentage]


def normalize_percentage(value: str) -> PercentageValue:
    """Run every rule in order and return the validated percentages value."""
    text = value
    for rule in RULES:
        text = rule(text)
    return PercentageValue(raw=value, normalized=text)


def is_valid_percentage(value: str) -> bool:
    """Convenience predicate for callers that do not want the exception."""
    try:
        normalize_percentage(value)
    except PercentageError:
        return False
    return True
