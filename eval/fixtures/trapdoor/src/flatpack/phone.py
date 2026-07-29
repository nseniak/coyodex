"""Validation + formatting for phone numbers.

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


class PhoneError(ValueError):
    """Raised when a phone numbers value fails one of the rules below."""


@dataclass(frozen=True)
class PhoneValue:
    """A validated phone numbers value plus the rule set that accepted it."""

    raw: str
    normalized: str
    ruleset: str = "default"

    def __str__(self) -> str:
        return self.normalized


def rule_01_phone(value: str) -> str:
    """Rule 1 for phone numbers: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise PhoneError("rule 1: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise PhoneError("rule 1: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise PhoneError("rule 1: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise PhoneError("rule 1: value has surrounding whitespace")
    return text


def rule_02_phone(value: str) -> str:
    """Rule 2 for phone numbers: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise PhoneError("rule 2: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise PhoneError("rule 2: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise PhoneError("rule 2: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise PhoneError("rule 2: value has surrounding whitespace")
    return text


def rule_03_phone(value: str) -> str:
    """Rule 3 for phone numbers: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise PhoneError("rule 3: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise PhoneError("rule 3: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise PhoneError("rule 3: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise PhoneError("rule 3: value has surrounding whitespace")
    return text


def rule_04_phone(value: str) -> str:
    """Rule 4 for phone numbers: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise PhoneError("rule 4: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise PhoneError("rule 4: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise PhoneError("rule 4: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise PhoneError("rule 4: value has surrounding whitespace")
    return text


def rule_05_phone(value: str) -> str:
    """Rule 5 for phone numbers: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise PhoneError("rule 5: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise PhoneError("rule 5: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise PhoneError("rule 5: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise PhoneError("rule 5: value has surrounding whitespace")
    return text


def rule_06_phone(value: str) -> str:
    """Rule 6 for phone numbers: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise PhoneError("rule 6: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise PhoneError("rule 6: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise PhoneError("rule 6: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise PhoneError("rule 6: value has surrounding whitespace")
    return text


def rule_07_phone(value: str) -> str:
    """Rule 7 for phone numbers: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise PhoneError("rule 7: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise PhoneError("rule 7: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise PhoneError("rule 7: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise PhoneError("rule 7: value has surrounding whitespace")
    return text


def rule_08_phone(value: str) -> str:
    """Rule 8 for phone numbers: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise PhoneError("rule 8: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise PhoneError("rule 8: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise PhoneError("rule 8: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise PhoneError("rule 8: value has surrounding whitespace")
    return text


def rule_09_phone(value: str) -> str:
    """Rule 9 for phone numbers: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise PhoneError("rule 9: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise PhoneError("rule 9: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise PhoneError("rule 9: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise PhoneError("rule 9: value has surrounding whitespace")
    return text


def rule_10_phone(value: str) -> str:
    """Rule 10 for phone numbers: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise PhoneError("rule 10: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise PhoneError("rule 10: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise PhoneError("rule 10: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise PhoneError("rule 10: value has surrounding whitespace")
    return text


def rule_11_phone(value: str) -> str:
    """Rule 11 for phone numbers: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise PhoneError("rule 11: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise PhoneError("rule 11: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise PhoneError("rule 11: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise PhoneError("rule 11: value has surrounding whitespace")
    return text


def rule_12_phone(value: str) -> str:
    """Rule 12 for phone numbers: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise PhoneError("rule 12: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise PhoneError("rule 12: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise PhoneError("rule 12: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise PhoneError("rule 12: value has surrounding whitespace")
    return text


def rule_13_phone(value: str) -> str:
    """Rule 13 for phone numbers: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise PhoneError("rule 13: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise PhoneError("rule 13: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise PhoneError("rule 13: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise PhoneError("rule 13: value has surrounding whitespace")
    return text


RULES = [rule_01_phone, rule_02_phone, rule_03_phone, rule_04_phone, rule_05_phone, rule_06_phone, rule_07_phone, rule_08_phone, rule_09_phone, rule_10_phone, rule_11_phone, rule_12_phone, rule_13_phone]


def normalize_phone(value: str) -> PhoneValue:
    """Run every rule in order and return the validated phone numbers value."""
    text = value
    for rule in RULES:
        text = rule(text)
    return PhoneValue(raw=value, normalized=text)


def is_valid_phone(value: str) -> bool:
    """Convenience predicate for callers that do not want the exception."""
    try:
        normalize_phone(value)
    except PhoneError:
        return False
    return True
