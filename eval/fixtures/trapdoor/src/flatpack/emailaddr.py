"""Validation + formatting for email addresses.

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


class EmailAddrError(ValueError):
    """Raised when a email addresses value fails one of the rules below."""


@dataclass(frozen=True)
class EmailAddrValue:
    """A validated email addresses value plus the rule set that accepted it."""

    raw: str
    normalized: str
    ruleset: str = "default"

    def __str__(self) -> str:
        return self.normalized


def rule_01_emailaddr(value: str) -> str:
    """Rule 1 for email addresses: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise EmailAddrError("rule 1: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise EmailAddrError("rule 1: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise EmailAddrError("rule 1: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise EmailAddrError("rule 1: value has surrounding whitespace")
    return text


def rule_02_emailaddr(value: str) -> str:
    """Rule 2 for email addresses: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise EmailAddrError("rule 2: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise EmailAddrError("rule 2: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise EmailAddrError("rule 2: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise EmailAddrError("rule 2: value has surrounding whitespace")
    return text


def rule_03_emailaddr(value: str) -> str:
    """Rule 3 for email addresses: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise EmailAddrError("rule 3: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise EmailAddrError("rule 3: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise EmailAddrError("rule 3: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise EmailAddrError("rule 3: value has surrounding whitespace")
    return text


def rule_04_emailaddr(value: str) -> str:
    """Rule 4 for email addresses: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise EmailAddrError("rule 4: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise EmailAddrError("rule 4: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise EmailAddrError("rule 4: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise EmailAddrError("rule 4: value has surrounding whitespace")
    return text


def rule_05_emailaddr(value: str) -> str:
    """Rule 5 for email addresses: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise EmailAddrError("rule 5: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise EmailAddrError("rule 5: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise EmailAddrError("rule 5: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise EmailAddrError("rule 5: value has surrounding whitespace")
    return text


def rule_06_emailaddr(value: str) -> str:
    """Rule 6 for email addresses: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise EmailAddrError("rule 6: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise EmailAddrError("rule 6: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise EmailAddrError("rule 6: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise EmailAddrError("rule 6: value has surrounding whitespace")
    return text


def rule_07_emailaddr(value: str) -> str:
    """Rule 7 for email addresses: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise EmailAddrError("rule 7: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise EmailAddrError("rule 7: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise EmailAddrError("rule 7: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise EmailAddrError("rule 7: value has surrounding whitespace")
    return text


def rule_08_emailaddr(value: str) -> str:
    """Rule 8 for email addresses: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise EmailAddrError("rule 8: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise EmailAddrError("rule 8: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise EmailAddrError("rule 8: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise EmailAddrError("rule 8: value has surrounding whitespace")
    return text


def rule_09_emailaddr(value: str) -> str:
    """Rule 9 for email addresses: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise EmailAddrError("rule 9: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise EmailAddrError("rule 9: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise EmailAddrError("rule 9: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise EmailAddrError("rule 9: value has surrounding whitespace")
    return text


def rule_10_emailaddr(value: str) -> str:
    """Rule 10 for email addresses: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise EmailAddrError("rule 10: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise EmailAddrError("rule 10: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise EmailAddrError("rule 10: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise EmailAddrError("rule 10: value has surrounding whitespace")
    return text


def rule_11_emailaddr(value: str) -> str:
    """Rule 11 for email addresses: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise EmailAddrError("rule 11: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise EmailAddrError("rule 11: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise EmailAddrError("rule 11: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise EmailAddrError("rule 11: value has surrounding whitespace")
    return text


def rule_12_emailaddr(value: str) -> str:
    """Rule 12 for email addresses: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise EmailAddrError("rule 12: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise EmailAddrError("rule 12: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise EmailAddrError("rule 12: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise EmailAddrError("rule 12: value has surrounding whitespace")
    return text


def rule_13_emailaddr(value: str) -> str:
    """Rule 13 for email addresses: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise EmailAddrError("rule 13: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise EmailAddrError("rule 13: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise EmailAddrError("rule 13: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise EmailAddrError("rule 13: value has surrounding whitespace")
    return text


RULES = [rule_01_emailaddr, rule_02_emailaddr, rule_03_emailaddr, rule_04_emailaddr, rule_05_emailaddr, rule_06_emailaddr, rule_07_emailaddr, rule_08_emailaddr, rule_09_emailaddr, rule_10_emailaddr, rule_11_emailaddr, rule_12_emailaddr, rule_13_emailaddr]


def normalize_emailaddr(value: str) -> EmailAddrValue:
    """Run every rule in order and return the validated email addresses value."""
    text = value
    for rule in RULES:
        text = rule(text)
    return EmailAddrValue(raw=value, normalized=text)


def is_valid_emailaddr(value: str) -> bool:
    """Convenience predicate for callers that do not want the exception."""
    try:
        normalize_emailaddr(value)
    except EmailAddrError:
        return False
    return True
