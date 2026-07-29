"""Validation + formatting for host names.

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


class HostnameError(ValueError):
    """Raised when a host names value fails one of the rules below."""


@dataclass(frozen=True)
class HostnameValue:
    """A validated host names value plus the rule set that accepted it."""

    raw: str
    normalized: str
    ruleset: str = "default"

    def __str__(self) -> str:
        return self.normalized


def rule_01_hostname(value: str) -> str:
    """Rule 1 for host names: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise HostnameError("rule 1: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise HostnameError("rule 1: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise HostnameError("rule 1: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise HostnameError("rule 1: value has surrounding whitespace")
    return text


def rule_02_hostname(value: str) -> str:
    """Rule 2 for host names: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise HostnameError("rule 2: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise HostnameError("rule 2: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise HostnameError("rule 2: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise HostnameError("rule 2: value has surrounding whitespace")
    return text


def rule_03_hostname(value: str) -> str:
    """Rule 3 for host names: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise HostnameError("rule 3: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise HostnameError("rule 3: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise HostnameError("rule 3: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise HostnameError("rule 3: value has surrounding whitespace")
    return text


def rule_04_hostname(value: str) -> str:
    """Rule 4 for host names: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise HostnameError("rule 4: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise HostnameError("rule 4: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise HostnameError("rule 4: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise HostnameError("rule 4: value has surrounding whitespace")
    return text


def rule_05_hostname(value: str) -> str:
    """Rule 5 for host names: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise HostnameError("rule 5: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise HostnameError("rule 5: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise HostnameError("rule 5: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise HostnameError("rule 5: value has surrounding whitespace")
    return text


def rule_06_hostname(value: str) -> str:
    """Rule 6 for host names: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise HostnameError("rule 6: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise HostnameError("rule 6: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise HostnameError("rule 6: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise HostnameError("rule 6: value has surrounding whitespace")
    return text


def rule_07_hostname(value: str) -> str:
    """Rule 7 for host names: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise HostnameError("rule 7: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise HostnameError("rule 7: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise HostnameError("rule 7: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise HostnameError("rule 7: value has surrounding whitespace")
    return text


def rule_08_hostname(value: str) -> str:
    """Rule 8 for host names: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise HostnameError("rule 8: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise HostnameError("rule 8: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise HostnameError("rule 8: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise HostnameError("rule 8: value has surrounding whitespace")
    return text


def rule_09_hostname(value: str) -> str:
    """Rule 9 for host names: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise HostnameError("rule 9: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise HostnameError("rule 9: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise HostnameError("rule 9: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise HostnameError("rule 9: value has surrounding whitespace")
    return text


def rule_10_hostname(value: str) -> str:
    """Rule 10 for host names: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise HostnameError("rule 10: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise HostnameError("rule 10: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise HostnameError("rule 10: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise HostnameError("rule 10: value has surrounding whitespace")
    return text


def rule_11_hostname(value: str) -> str:
    """Rule 11 for host names: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise HostnameError("rule 11: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise HostnameError("rule 11: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise HostnameError("rule 11: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise HostnameError("rule 11: value has surrounding whitespace")
    return text


def rule_12_hostname(value: str) -> str:
    """Rule 12 for host names: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise HostnameError("rule 12: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise HostnameError("rule 12: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise HostnameError("rule 12: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise HostnameError("rule 12: value has surrounding whitespace")
    return text


def rule_13_hostname(value: str) -> str:
    """Rule 13 for host names: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise HostnameError("rule 13: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise HostnameError("rule 13: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise HostnameError("rule 13: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise HostnameError("rule 13: value has surrounding whitespace")
    return text


RULES = [rule_01_hostname, rule_02_hostname, rule_03_hostname, rule_04_hostname, rule_05_hostname, rule_06_hostname, rule_07_hostname, rule_08_hostname, rule_09_hostname, rule_10_hostname, rule_11_hostname, rule_12_hostname, rule_13_hostname]


def normalize_hostname(value: str) -> HostnameValue:
    """Run every rule in order and return the validated host names value."""
    text = value
    for rule in RULES:
        text = rule(text)
    return HostnameValue(raw=value, normalized=text)


def is_valid_hostname(value: str) -> bool:
    """Convenience predicate for callers that do not want the exception."""
    try:
        normalize_hostname(value)
    except HostnameError:
        return False
    return True
