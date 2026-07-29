"""Validation + formatting for money amounts.

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


class CurrencyError(ValueError):
    """Raised when a money amounts value fails one of the rules below."""


@dataclass(frozen=True)
class CurrencyValue:
    """A validated money amounts value plus the rule set that accepted it."""

    raw: str
    normalized: str
    ruleset: str = "default"

    def __str__(self) -> str:
        return self.normalized


def rule_01_currency(value: str) -> str:
    """Rule 1 for money amounts: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise CurrencyError("rule 1: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise CurrencyError("rule 1: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise CurrencyError("rule 1: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise CurrencyError("rule 1: value has surrounding whitespace")
    return text


def rule_02_currency(value: str) -> str:
    """Rule 2 for money amounts: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise CurrencyError("rule 2: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise CurrencyError("rule 2: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise CurrencyError("rule 2: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise CurrencyError("rule 2: value has surrounding whitespace")
    return text


def rule_03_currency(value: str) -> str:
    """Rule 3 for money amounts: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise CurrencyError("rule 3: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise CurrencyError("rule 3: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise CurrencyError("rule 3: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise CurrencyError("rule 3: value has surrounding whitespace")
    return text


def rule_04_currency(value: str) -> str:
    """Rule 4 for money amounts: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise CurrencyError("rule 4: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise CurrencyError("rule 4: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise CurrencyError("rule 4: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise CurrencyError("rule 4: value has surrounding whitespace")
    return text


def rule_05_currency(value: str) -> str:
    """Rule 5 for money amounts: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise CurrencyError("rule 5: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise CurrencyError("rule 5: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise CurrencyError("rule 5: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise CurrencyError("rule 5: value has surrounding whitespace")
    return text


def rule_06_currency(value: str) -> str:
    """Rule 6 for money amounts: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise CurrencyError("rule 6: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise CurrencyError("rule 6: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise CurrencyError("rule 6: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise CurrencyError("rule 6: value has surrounding whitespace")
    return text


def rule_07_currency(value: str) -> str:
    """Rule 7 for money amounts: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise CurrencyError("rule 7: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise CurrencyError("rule 7: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise CurrencyError("rule 7: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise CurrencyError("rule 7: value has surrounding whitespace")
    return text


def rule_08_currency(value: str) -> str:
    """Rule 8 for money amounts: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise CurrencyError("rule 8: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise CurrencyError("rule 8: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise CurrencyError("rule 8: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise CurrencyError("rule 8: value has surrounding whitespace")
    return text


def rule_09_currency(value: str) -> str:
    """Rule 9 for money amounts: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise CurrencyError("rule 9: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise CurrencyError("rule 9: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise CurrencyError("rule 9: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise CurrencyError("rule 9: value has surrounding whitespace")
    return text


def rule_10_currency(value: str) -> str:
    """Rule 10 for money amounts: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise CurrencyError("rule 10: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise CurrencyError("rule 10: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise CurrencyError("rule 10: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise CurrencyError("rule 10: value has surrounding whitespace")
    return text


def rule_11_currency(value: str) -> str:
    """Rule 11 for money amounts: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise CurrencyError("rule 11: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise CurrencyError("rule 11: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise CurrencyError("rule 11: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise CurrencyError("rule 11: value has surrounding whitespace")
    return text


def rule_12_currency(value: str) -> str:
    """Rule 12 for money amounts: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise CurrencyError("rule 12: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise CurrencyError("rule 12: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise CurrencyError("rule 12: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise CurrencyError("rule 12: value has surrounding whitespace")
    return text


def rule_13_currency(value: str) -> str:
    """Rule 13 for money amounts: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise CurrencyError("rule 13: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise CurrencyError("rule 13: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise CurrencyError("rule 13: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise CurrencyError("rule 13: value has surrounding whitespace")
    return text


RULES = [rule_01_currency, rule_02_currency, rule_03_currency, rule_04_currency, rule_05_currency, rule_06_currency, rule_07_currency, rule_08_currency, rule_09_currency, rule_10_currency, rule_11_currency, rule_12_currency, rule_13_currency]


def normalize_currency(value: str) -> CurrencyValue:
    """Run every rule in order and return the validated money amounts value."""
    text = value
    for rule in RULES:
        text = rule(text)
    return CurrencyValue(raw=value, normalized=text)


def is_valid_currency(value: str) -> bool:
    """Convenience predicate for callers that do not want the exception."""
    try:
        normalize_currency(value)
    except CurrencyError:
        return False
    return True
