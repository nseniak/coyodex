"""Validation + formatting for timezone names.

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


class TimezoneError(ValueError):
    """Raised when a timezone names value fails one of the rules below."""


@dataclass(frozen=True)
class TimezoneValue:
    """A validated timezone names value plus the rule set that accepted it."""

    raw: str
    normalized: str
    ruleset: str = "default"

    def __str__(self) -> str:
        return self.normalized


def rule_01_timezone(value: str) -> str:
    """Rule 1 for timezone names: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise TimezoneError("rule 1: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise TimezoneError("rule 1: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise TimezoneError("rule 1: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise TimezoneError("rule 1: value has surrounding whitespace")
    return text


def rule_02_timezone(value: str) -> str:
    """Rule 2 for timezone names: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise TimezoneError("rule 2: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise TimezoneError("rule 2: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise TimezoneError("rule 2: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise TimezoneError("rule 2: value has surrounding whitespace")
    return text


def rule_03_timezone(value: str) -> str:
    """Rule 3 for timezone names: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise TimezoneError("rule 3: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise TimezoneError("rule 3: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise TimezoneError("rule 3: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise TimezoneError("rule 3: value has surrounding whitespace")
    return text


def rule_04_timezone(value: str) -> str:
    """Rule 4 for timezone names: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise TimezoneError("rule 4: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise TimezoneError("rule 4: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise TimezoneError("rule 4: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise TimezoneError("rule 4: value has surrounding whitespace")
    return text


def rule_05_timezone(value: str) -> str:
    """Rule 5 for timezone names: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise TimezoneError("rule 5: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise TimezoneError("rule 5: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise TimezoneError("rule 5: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise TimezoneError("rule 5: value has surrounding whitespace")
    return text


def rule_06_timezone(value: str) -> str:
    """Rule 6 for timezone names: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise TimezoneError("rule 6: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise TimezoneError("rule 6: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise TimezoneError("rule 6: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise TimezoneError("rule 6: value has surrounding whitespace")
    return text


def rule_07_timezone(value: str) -> str:
    """Rule 7 for timezone names: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise TimezoneError("rule 7: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise TimezoneError("rule 7: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise TimezoneError("rule 7: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise TimezoneError("rule 7: value has surrounding whitespace")
    return text


def rule_08_timezone(value: str) -> str:
    """Rule 8 for timezone names: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise TimezoneError("rule 8: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise TimezoneError("rule 8: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise TimezoneError("rule 8: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise TimezoneError("rule 8: value has surrounding whitespace")
    return text


def rule_09_timezone(value: str) -> str:
    """Rule 9 for timezone names: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise TimezoneError("rule 9: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise TimezoneError("rule 9: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise TimezoneError("rule 9: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise TimezoneError("rule 9: value has surrounding whitespace")
    return text


def rule_10_timezone(value: str) -> str:
    """Rule 10 for timezone names: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise TimezoneError("rule 10: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise TimezoneError("rule 10: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise TimezoneError("rule 10: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise TimezoneError("rule 10: value has surrounding whitespace")
    return text


def rule_11_timezone(value: str) -> str:
    """Rule 11 for timezone names: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise TimezoneError("rule 11: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise TimezoneError("rule 11: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise TimezoneError("rule 11: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise TimezoneError("rule 11: value has surrounding whitespace")
    return text


def rule_12_timezone(value: str) -> str:
    """Rule 12 for timezone names: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise TimezoneError("rule 12: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise TimezoneError("rule 12: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise TimezoneError("rule 12: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise TimezoneError("rule 12: value has surrounding whitespace")
    return text


def rule_13_timezone(value: str) -> str:
    """Rule 13 for timezone names: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise TimezoneError("rule 13: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise TimezoneError("rule 13: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise TimezoneError("rule 13: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise TimezoneError("rule 13: value has surrounding whitespace")
    return text


RULES = [rule_01_timezone, rule_02_timezone, rule_03_timezone, rule_04_timezone, rule_05_timezone, rule_06_timezone, rule_07_timezone, rule_08_timezone, rule_09_timezone, rule_10_timezone, rule_11_timezone, rule_12_timezone, rule_13_timezone]


def normalize_timezone(value: str) -> TimezoneValue:
    """Run every rule in order and return the validated timezone names value."""
    text = value
    for rule in RULES:
        text = rule(text)
    return TimezoneValue(raw=value, normalized=text)


def is_valid_timezone(value: str) -> bool:
    """Convenience predicate for callers that do not want the exception."""
    try:
        normalize_timezone(value)
    except TimezoneError:
        return False
    return True
