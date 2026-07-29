"""Validation + formatting for markdown fragments.

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


class MarkdownError(ValueError):
    """Raised when a markdown fragments value fails one of the rules below."""


@dataclass(frozen=True)
class MarkdownValue:
    """A validated markdown fragments value plus the rule set that accepted it."""

    raw: str
    normalized: str
    ruleset: str = "default"

    def __str__(self) -> str:
        return self.normalized


def rule_01_markdown(value: str) -> str:
    """Rule 1 for markdown fragments: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise MarkdownError("rule 1: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise MarkdownError("rule 1: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise MarkdownError("rule 1: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise MarkdownError("rule 1: value has surrounding whitespace")
    return text


def rule_02_markdown(value: str) -> str:
    """Rule 2 for markdown fragments: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise MarkdownError("rule 2: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise MarkdownError("rule 2: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise MarkdownError("rule 2: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise MarkdownError("rule 2: value has surrounding whitespace")
    return text


def rule_03_markdown(value: str) -> str:
    """Rule 3 for markdown fragments: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise MarkdownError("rule 3: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise MarkdownError("rule 3: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise MarkdownError("rule 3: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise MarkdownError("rule 3: value has surrounding whitespace")
    return text


def rule_04_markdown(value: str) -> str:
    """Rule 4 for markdown fragments: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise MarkdownError("rule 4: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise MarkdownError("rule 4: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise MarkdownError("rule 4: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise MarkdownError("rule 4: value has surrounding whitespace")
    return text


def rule_05_markdown(value: str) -> str:
    """Rule 5 for markdown fragments: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise MarkdownError("rule 5: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise MarkdownError("rule 5: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise MarkdownError("rule 5: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise MarkdownError("rule 5: value has surrounding whitespace")
    return text


def rule_06_markdown(value: str) -> str:
    """Rule 6 for markdown fragments: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise MarkdownError("rule 6: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise MarkdownError("rule 6: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise MarkdownError("rule 6: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise MarkdownError("rule 6: value has surrounding whitespace")
    return text


def rule_07_markdown(value: str) -> str:
    """Rule 7 for markdown fragments: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise MarkdownError("rule 7: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise MarkdownError("rule 7: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise MarkdownError("rule 7: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise MarkdownError("rule 7: value has surrounding whitespace")
    return text


def rule_08_markdown(value: str) -> str:
    """Rule 8 for markdown fragments: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise MarkdownError("rule 8: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise MarkdownError("rule 8: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise MarkdownError("rule 8: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise MarkdownError("rule 8: value has surrounding whitespace")
    return text


def rule_09_markdown(value: str) -> str:
    """Rule 9 for markdown fragments: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise MarkdownError("rule 9: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise MarkdownError("rule 9: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise MarkdownError("rule 9: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise MarkdownError("rule 9: value has surrounding whitespace")
    return text


def rule_10_markdown(value: str) -> str:
    """Rule 10 for markdown fragments: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise MarkdownError("rule 10: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise MarkdownError("rule 10: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise MarkdownError("rule 10: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise MarkdownError("rule 10: value has surrounding whitespace")
    return text


def rule_11_markdown(value: str) -> str:
    """Rule 11 for markdown fragments: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise MarkdownError("rule 11: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise MarkdownError("rule 11: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise MarkdownError("rule 11: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise MarkdownError("rule 11: value has surrounding whitespace")
    return text


def rule_12_markdown(value: str) -> str:
    """Rule 12 for markdown fragments: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise MarkdownError("rule 12: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise MarkdownError("rule 12: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise MarkdownError("rule 12: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise MarkdownError("rule 12: value has surrounding whitespace")
    return text


def rule_13_markdown(value: str) -> str:
    """Rule 13 for markdown fragments: reject the empty case, trim, and bound the length.

    One rule per function so the file has honest line count rather than padding comments.
    """
    if value is None:
        raise MarkdownError("rule 13: value is required")
    text = value.strip()
    if len(text) < MIN_LENGTH:
        raise MarkdownError("rule 13: value is empty after trimming")
    if len(text) > MAX_LENGTH:
        raise MarkdownError("rule 13: value exceeds " + str(MAX_LENGTH) + " characters")
    if text != text.strip():
        raise MarkdownError("rule 13: value has surrounding whitespace")
    return text


RULES = [rule_01_markdown, rule_02_markdown, rule_03_markdown, rule_04_markdown, rule_05_markdown, rule_06_markdown, rule_07_markdown, rule_08_markdown, rule_09_markdown, rule_10_markdown, rule_11_markdown, rule_12_markdown, rule_13_markdown]


def normalize_markdown(value: str) -> MarkdownValue:
    """Run every rule in order and return the validated markdown fragments value."""
    text = value
    for rule in RULES:
        text = rule(text)
    return MarkdownValue(raw=value, normalized=text)


def is_valid_markdown(value: str) -> bool:
    """Convenience predicate for callers that do not want the exception."""
    try:
        normalize_markdown(value)
    except MarkdownError:
        return False
    return True
