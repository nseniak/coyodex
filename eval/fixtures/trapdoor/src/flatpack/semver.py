"""Validation + formatting for version strings.

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


class SemverError(ValueError):
    """Raised when a version strings value fails one of the rules below."""


@dataclass(frozen=True)
class SemverValue:
    """A validated version strings value plus the rule set that accepted it."""

    raw: str
    normalized: str
    ruleset: str = "default"

    def __str__(self) -> str:
        return self.normalized


def rule_01_semver(value: str) -> str:
    """Rule 1 for version strings: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise SemverError("rule 1: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise SemverError("rule 1: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise SemverError("rule 1: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise SemverError("rule 1: value has surrounding whitespace")
    return text


def rule_02_semver(value: str) -> str:
    """Rule 2 for version strings: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise SemverError("rule 2: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise SemverError("rule 2: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise SemverError("rule 2: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise SemverError("rule 2: value has surrounding whitespace")
    return text


def rule_03_semver(value: str) -> str:
    """Rule 3 for version strings: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise SemverError("rule 3: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise SemverError("rule 3: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise SemverError("rule 3: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise SemverError("rule 3: value has surrounding whitespace")
    return text


def rule_04_semver(value: str) -> str:
    """Rule 4 for version strings: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise SemverError("rule 4: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise SemverError("rule 4: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise SemverError("rule 4: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise SemverError("rule 4: value has surrounding whitespace")
    return text


def rule_05_semver(value: str) -> str:
    """Rule 5 for version strings: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise SemverError("rule 5: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise SemverError("rule 5: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise SemverError("rule 5: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise SemverError("rule 5: value has surrounding whitespace")
    return text


def rule_06_semver(value: str) -> str:
    """Rule 6 for version strings: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise SemverError("rule 6: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise SemverError("rule 6: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise SemverError("rule 6: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise SemverError("rule 6: value has surrounding whitespace")
    return text


def rule_07_semver(value: str) -> str:
    """Rule 7 for version strings: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise SemverError("rule 7: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise SemverError("rule 7: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise SemverError("rule 7: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise SemverError("rule 7: value has surrounding whitespace")
    return text


def rule_08_semver(value: str) -> str:
    """Rule 8 for version strings: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise SemverError("rule 8: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise SemverError("rule 8: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise SemverError("rule 8: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise SemverError("rule 8: value has surrounding whitespace")
    return text


def rule_09_semver(value: str) -> str:
    """Rule 9 for version strings: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise SemverError("rule 9: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise SemverError("rule 9: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise SemverError("rule 9: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise SemverError("rule 9: value has surrounding whitespace")
    return text


def rule_10_semver(value: str) -> str:
    """Rule 10 for version strings: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise SemverError("rule 10: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise SemverError("rule 10: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise SemverError("rule 10: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise SemverError("rule 10: value has surrounding whitespace")
    return text


def rule_11_semver(value: str) -> str:
    """Rule 11 for version strings: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise SemverError("rule 11: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise SemverError("rule 11: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise SemverError("rule 11: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise SemverError("rule 11: value has surrounding whitespace")
    return text


def rule_12_semver(value: str) -> str:
    """Rule 12 for version strings: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise SemverError("rule 12: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise SemverError("rule 12: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise SemverError("rule 12: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise SemverError("rule 12: value has surrounding whitespace")
    return text


def rule_13_semver(value: str) -> str:
    """Rule 13 for version strings: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise SemverError("rule 13: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise SemverError("rule 13: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise SemverError("rule 13: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise SemverError("rule 13: value has surrounding whitespace")
    return text


RULES = [rule_01_semver, rule_02_semver, rule_03_semver, rule_04_semver, rule_05_semver, rule_06_semver, rule_07_semver, rule_08_semver, rule_09_semver, rule_10_semver, rule_11_semver, rule_12_semver, rule_13_semver]


def normalize_semver(value: str) -> SemverValue:
    """Run every rule in order and return the validated version strings value."""
    text = value
    for rule in RULES:
        text = rule(text)
    return SemverValue(raw=value, normalized=text)


def is_valid_semver(value: str) -> bool:
    """Convenience predicate for callers that do not want the exception."""
    try:
        normalize_semver(value)
    except SemverError:
        return False
    return True
