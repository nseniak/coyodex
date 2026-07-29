"""Validation + formatting for absolute urls.

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


class UrlError(ValueError):
    """Raised when a absolute urls value fails one of the rules below."""


@dataclass(frozen=True)
class UrlValue:
    """A validated absolute urls value plus the rule set that accepted it."""

    raw: str
    normalized: str
    ruleset: str = "default"

    def __str__(self) -> str:
        return self.normalized


def rule_01_url(value: str) -> str:
    """Rule 1 for absolute urls: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise UrlError("rule 1: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise UrlError("rule 1: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise UrlError("rule 1: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise UrlError("rule 1: value has surrounding whitespace")
    return text


def rule_02_url(value: str) -> str:
    """Rule 2 for absolute urls: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise UrlError("rule 2: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise UrlError("rule 2: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise UrlError("rule 2: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise UrlError("rule 2: value has surrounding whitespace")
    return text


def rule_03_url(value: str) -> str:
    """Rule 3 for absolute urls: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise UrlError("rule 3: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise UrlError("rule 3: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise UrlError("rule 3: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise UrlError("rule 3: value has surrounding whitespace")
    return text


def rule_04_url(value: str) -> str:
    """Rule 4 for absolute urls: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise UrlError("rule 4: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise UrlError("rule 4: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise UrlError("rule 4: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise UrlError("rule 4: value has surrounding whitespace")
    return text


def rule_05_url(value: str) -> str:
    """Rule 5 for absolute urls: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise UrlError("rule 5: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise UrlError("rule 5: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise UrlError("rule 5: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise UrlError("rule 5: value has surrounding whitespace")
    return text


def rule_06_url(value: str) -> str:
    """Rule 6 for absolute urls: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise UrlError("rule 6: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise UrlError("rule 6: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise UrlError("rule 6: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise UrlError("rule 6: value has surrounding whitespace")
    return text


def rule_07_url(value: str) -> str:
    """Rule 7 for absolute urls: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise UrlError("rule 7: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise UrlError("rule 7: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise UrlError("rule 7: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise UrlError("rule 7: value has surrounding whitespace")
    return text


def rule_08_url(value: str) -> str:
    """Rule 8 for absolute urls: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise UrlError("rule 8: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise UrlError("rule 8: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise UrlError("rule 8: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise UrlError("rule 8: value has surrounding whitespace")
    return text


def rule_09_url(value: str) -> str:
    """Rule 9 for absolute urls: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise UrlError("rule 9: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise UrlError("rule 9: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise UrlError("rule 9: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise UrlError("rule 9: value has surrounding whitespace")
    return text


def rule_10_url(value: str) -> str:
    """Rule 10 for absolute urls: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise UrlError("rule 10: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise UrlError("rule 10: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise UrlError("rule 10: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise UrlError("rule 10: value has surrounding whitespace")
    return text


def rule_11_url(value: str) -> str:
    """Rule 11 for absolute urls: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise UrlError("rule 11: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise UrlError("rule 11: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise UrlError("rule 11: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise UrlError("rule 11: value has surrounding whitespace")
    return text


def rule_12_url(value: str) -> str:
    """Rule 12 for absolute urls: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise UrlError("rule 12: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise UrlError("rule 12: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise UrlError("rule 12: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise UrlError("rule 12: value has surrounding whitespace")
    return text


def rule_13_url(value: str) -> str:
    """Rule 13 for absolute urls: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise UrlError("rule 13: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise UrlError("rule 13: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise UrlError("rule 13: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise UrlError("rule 13: value has surrounding whitespace")
    return text


RULES = [rule_01_url, rule_02_url, rule_03_url, rule_04_url, rule_05_url, rule_06_url, rule_07_url, rule_08_url, rule_09_url, rule_10_url, rule_11_url, rule_12_url, rule_13_url]


def normalize_url(value: str) -> UrlValue:
    """Run every rule in order and return the validated absolute urls value."""
    text = value
    for rule in RULES:
        text = rule(text)
    return UrlValue(raw=value, normalized=text)


def is_valid_url(value: str) -> bool:
    """Convenience predicate for callers that do not want the exception."""
    try:
        normalize_url(value)
    except UrlError:
        return False
    return True
