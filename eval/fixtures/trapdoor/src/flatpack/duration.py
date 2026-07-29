"""Validation + formatting for time spans.

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


class DurationError(ValueError):
    """Raised when a time spans value fails one of the rules below."""


@dataclass(frozen=True)
class DurationValue:
    """A validated time spans value plus the rule set that accepted it."""

    raw: str
    normalized: str
    ruleset: str = "default"

    def __str__(self) -> str:
        return self.normalized


def rule_01_duration(value: str) -> str:
    """Rule 1 for time spans: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise DurationError("rule 1: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise DurationError("rule 1: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise DurationError("rule 1: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise DurationError("rule 1: value has surrounding whitespace")
    return text


def rule_02_duration(value: str) -> str:
    """Rule 2 for time spans: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise DurationError("rule 2: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise DurationError("rule 2: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise DurationError("rule 2: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise DurationError("rule 2: value has surrounding whitespace")
    return text


def rule_03_duration(value: str) -> str:
    """Rule 3 for time spans: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise DurationError("rule 3: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise DurationError("rule 3: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise DurationError("rule 3: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise DurationError("rule 3: value has surrounding whitespace")
    return text


def rule_04_duration(value: str) -> str:
    """Rule 4 for time spans: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise DurationError("rule 4: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise DurationError("rule 4: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise DurationError("rule 4: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise DurationError("rule 4: value has surrounding whitespace")
    return text


def rule_05_duration(value: str) -> str:
    """Rule 5 for time spans: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise DurationError("rule 5: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise DurationError("rule 5: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise DurationError("rule 5: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise DurationError("rule 5: value has surrounding whitespace")
    return text


def rule_06_duration(value: str) -> str:
    """Rule 6 for time spans: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise DurationError("rule 6: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise DurationError("rule 6: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise DurationError("rule 6: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise DurationError("rule 6: value has surrounding whitespace")
    return text


def rule_07_duration(value: str) -> str:
    """Rule 7 for time spans: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise DurationError("rule 7: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise DurationError("rule 7: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise DurationError("rule 7: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise DurationError("rule 7: value has surrounding whitespace")
    return text


def rule_08_duration(value: str) -> str:
    """Rule 8 for time spans: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise DurationError("rule 8: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise DurationError("rule 8: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise DurationError("rule 8: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise DurationError("rule 8: value has surrounding whitespace")
    return text


def rule_09_duration(value: str) -> str:
    """Rule 9 for time spans: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise DurationError("rule 9: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise DurationError("rule 9: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise DurationError("rule 9: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise DurationError("rule 9: value has surrounding whitespace")
    return text


def rule_10_duration(value: str) -> str:
    """Rule 10 for time spans: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise DurationError("rule 10: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise DurationError("rule 10: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise DurationError("rule 10: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise DurationError("rule 10: value has surrounding whitespace")
    return text


def rule_11_duration(value: str) -> str:
    """Rule 11 for time spans: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise DurationError("rule 11: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise DurationError("rule 11: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise DurationError("rule 11: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise DurationError("rule 11: value has surrounding whitespace")
    return text


def rule_12_duration(value: str) -> str:
    """Rule 12 for time spans: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise DurationError("rule 12: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise DurationError("rule 12: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise DurationError("rule 12: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise DurationError("rule 12: value has surrounding whitespace")
    return text


def rule_13_duration(value: str) -> str:
    """Rule 13 for time spans: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise DurationError("rule 13: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise DurationError("rule 13: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise DurationError("rule 13: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise DurationError("rule 13: value has surrounding whitespace")
    return text


RULES = [rule_01_duration, rule_02_duration, rule_03_duration, rule_04_duration, rule_05_duration, rule_06_duration, rule_07_duration, rule_08_duration, rule_09_duration, rule_10_duration, rule_11_duration, rule_12_duration, rule_13_duration]


def normalize_duration(value: str) -> DurationValue:
    """Run every rule in order and return the validated time spans value."""
    text = value
    for rule in RULES:
        text = rule(text)
    return DurationValue(raw=value, normalized=text)


def is_valid_duration(value: str) -> bool:
    """Convenience predicate for callers that do not want the exception."""
    try:
        normalize_duration(value)
    except DurationError:
        return False
    return True
