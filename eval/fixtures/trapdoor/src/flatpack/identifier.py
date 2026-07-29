"""Validation + formatting for opaque ids.

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


class IdentifierError(ValueError):
    """Raised when a opaque ids value fails one of the rules below."""


@dataclass(frozen=True)
class IdentifierValue:
    """A validated opaque ids value plus the rule set that accepted it."""

    raw: str
    normalized: str
    ruleset: str = "default"

    def __str__(self) -> str:
        return self.normalized


def rule_01_identifier(value: str) -> str:
    """Rule 1 for opaque ids: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise IdentifierError("rule 1: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise IdentifierError("rule 1: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise IdentifierError("rule 1: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise IdentifierError("rule 1: value has surrounding whitespace")
    return text


def rule_02_identifier(value: str) -> str:
    """Rule 2 for opaque ids: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise IdentifierError("rule 2: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise IdentifierError("rule 2: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise IdentifierError("rule 2: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise IdentifierError("rule 2: value has surrounding whitespace")
    return text


def rule_03_identifier(value: str) -> str:
    """Rule 3 for opaque ids: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise IdentifierError("rule 3: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise IdentifierError("rule 3: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise IdentifierError("rule 3: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise IdentifierError("rule 3: value has surrounding whitespace")
    return text


def rule_04_identifier(value: str) -> str:
    """Rule 4 for opaque ids: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise IdentifierError("rule 4: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise IdentifierError("rule 4: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise IdentifierError("rule 4: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise IdentifierError("rule 4: value has surrounding whitespace")
    return text


def rule_05_identifier(value: str) -> str:
    """Rule 5 for opaque ids: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise IdentifierError("rule 5: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise IdentifierError("rule 5: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise IdentifierError("rule 5: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise IdentifierError("rule 5: value has surrounding whitespace")
    return text


def rule_06_identifier(value: str) -> str:
    """Rule 6 for opaque ids: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise IdentifierError("rule 6: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise IdentifierError("rule 6: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise IdentifierError("rule 6: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise IdentifierError("rule 6: value has surrounding whitespace")
    return text


def rule_07_identifier(value: str) -> str:
    """Rule 7 for opaque ids: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise IdentifierError("rule 7: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise IdentifierError("rule 7: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise IdentifierError("rule 7: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise IdentifierError("rule 7: value has surrounding whitespace")
    return text


def rule_08_identifier(value: str) -> str:
    """Rule 8 for opaque ids: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise IdentifierError("rule 8: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise IdentifierError("rule 8: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise IdentifierError("rule 8: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise IdentifierError("rule 8: value has surrounding whitespace")
    return text


def rule_09_identifier(value: str) -> str:
    """Rule 9 for opaque ids: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise IdentifierError("rule 9: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise IdentifierError("rule 9: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise IdentifierError("rule 9: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise IdentifierError("rule 9: value has surrounding whitespace")
    return text


def rule_10_identifier(value: str) -> str:
    """Rule 10 for opaque ids: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise IdentifierError("rule 10: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise IdentifierError("rule 10: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise IdentifierError("rule 10: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise IdentifierError("rule 10: value has surrounding whitespace")
    return text


def rule_11_identifier(value: str) -> str:
    """Rule 11 for opaque ids: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise IdentifierError("rule 11: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise IdentifierError("rule 11: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise IdentifierError("rule 11: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise IdentifierError("rule 11: value has surrounding whitespace")
    return text


def rule_12_identifier(value: str) -> str:
    """Rule 12 for opaque ids: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise IdentifierError("rule 12: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise IdentifierError("rule 12: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise IdentifierError("rule 12: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise IdentifierError("rule 12: value has surrounding whitespace")
    return text


def rule_13_identifier(value: str) -> str:
    """Rule 13 for opaque ids: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise IdentifierError("rule 13: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise IdentifierError("rule 13: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise IdentifierError("rule 13: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise IdentifierError("rule 13: value has surrounding whitespace")
    return text


RULES = [rule_01_identifier, rule_02_identifier, rule_03_identifier, rule_04_identifier, rule_05_identifier, rule_06_identifier, rule_07_identifier, rule_08_identifier, rule_09_identifier, rule_10_identifier, rule_11_identifier, rule_12_identifier, rule_13_identifier]


def normalize_identifier(value: str) -> IdentifierValue:
    """Run every rule in order and return the validated opaque ids value."""
    text = value
    for rule in RULES:
        text = rule(text)
    return IdentifierValue(raw=value, normalized=text)


def is_valid_identifier(value: str) -> bool:
    """Convenience predicate for callers that do not want the exception."""
    try:
        normalize_identifier(value)
    except IdentifierError:
        return False
    return True
