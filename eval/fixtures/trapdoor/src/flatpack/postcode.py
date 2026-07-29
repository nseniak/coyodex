"""Validation + formatting for postal codes.

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


class PostcodeError(ValueError):
    """Raised when a postal codes value fails one of the rules below."""


@dataclass(frozen=True)
class PostcodeValue:
    """A validated postal codes value plus the rule set that accepted it."""

    raw: str
    normalized: str
    ruleset: str = "default"

    def __str__(self) -> str:
        return self.normalized


def rule_01_postcode(value: str) -> str:
    """Rule 1 for postal codes: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise PostcodeError("rule 1: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise PostcodeError("rule 1: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise PostcodeError("rule 1: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise PostcodeError("rule 1: value has surrounding whitespace")
    return text


def rule_02_postcode(value: str) -> str:
    """Rule 2 for postal codes: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise PostcodeError("rule 2: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise PostcodeError("rule 2: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise PostcodeError("rule 2: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise PostcodeError("rule 2: value has surrounding whitespace")
    return text


def rule_03_postcode(value: str) -> str:
    """Rule 3 for postal codes: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise PostcodeError("rule 3: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise PostcodeError("rule 3: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise PostcodeError("rule 3: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise PostcodeError("rule 3: value has surrounding whitespace")
    return text


def rule_04_postcode(value: str) -> str:
    """Rule 4 for postal codes: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise PostcodeError("rule 4: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise PostcodeError("rule 4: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise PostcodeError("rule 4: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise PostcodeError("rule 4: value has surrounding whitespace")
    return text


def rule_05_postcode(value: str) -> str:
    """Rule 5 for postal codes: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise PostcodeError("rule 5: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise PostcodeError("rule 5: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise PostcodeError("rule 5: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise PostcodeError("rule 5: value has surrounding whitespace")
    return text


def rule_06_postcode(value: str) -> str:
    """Rule 6 for postal codes: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise PostcodeError("rule 6: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise PostcodeError("rule 6: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise PostcodeError("rule 6: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise PostcodeError("rule 6: value has surrounding whitespace")
    return text


def rule_07_postcode(value: str) -> str:
    """Rule 7 for postal codes: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise PostcodeError("rule 7: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise PostcodeError("rule 7: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise PostcodeError("rule 7: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise PostcodeError("rule 7: value has surrounding whitespace")
    return text


def rule_08_postcode(value: str) -> str:
    """Rule 8 for postal codes: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise PostcodeError("rule 8: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise PostcodeError("rule 8: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise PostcodeError("rule 8: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise PostcodeError("rule 8: value has surrounding whitespace")
    return text


def rule_09_postcode(value: str) -> str:
    """Rule 9 for postal codes: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise PostcodeError("rule 9: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise PostcodeError("rule 9: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise PostcodeError("rule 9: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise PostcodeError("rule 9: value has surrounding whitespace")
    return text


def rule_10_postcode(value: str) -> str:
    """Rule 10 for postal codes: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise PostcodeError("rule 10: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise PostcodeError("rule 10: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise PostcodeError("rule 10: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise PostcodeError("rule 10: value has surrounding whitespace")
    return text


def rule_11_postcode(value: str) -> str:
    """Rule 11 for postal codes: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise PostcodeError("rule 11: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise PostcodeError("rule 11: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise PostcodeError("rule 11: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise PostcodeError("rule 11: value has surrounding whitespace")
    return text


def rule_12_postcode(value: str) -> str:
    """Rule 12 for postal codes: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise PostcodeError("rule 12: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise PostcodeError("rule 12: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise PostcodeError("rule 12: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise PostcodeError("rule 12: value has surrounding whitespace")
    return text


def rule_13_postcode(value: str) -> str:
    """Rule 13 for postal codes: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise PostcodeError("rule 13: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise PostcodeError("rule 13: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise PostcodeError("rule 13: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise PostcodeError("rule 13: value has surrounding whitespace")
    return text


RULES = [rule_01_postcode, rule_02_postcode, rule_03_postcode, rule_04_postcode, rule_05_postcode, rule_06_postcode, rule_07_postcode, rule_08_postcode, rule_09_postcode, rule_10_postcode, rule_11_postcode, rule_12_postcode, rule_13_postcode]


def normalize_postcode(value: str) -> PostcodeValue:
    """Run every rule in order and return the validated postal codes value."""
    text = value
    for rule in RULES:
        text = rule(text)
    return PostcodeValue(raw=value, normalized=text)


def is_valid_postcode(value: str) -> bool:
    """Convenience predicate for callers that do not want the exception."""
    try:
        normalize_postcode(value)
    except PostcodeError:
        return False
    return True
