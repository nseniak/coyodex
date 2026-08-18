"""Countable readability checks for the map's reader-facing prose.

The map's plain-language fields are read ONE BOX AT A TIME, out of any surrounding paragraph, by
someone who does not read code. Four properties of such a sentence can be COUNTED, which is why they
belong here rather than in the method prompt: how long it is, whether it leans on an em dash instead
of naming the link, whether it names CODE instead of the product, and whether it opens with a pointer
word that has nothing to point at once the field is read alone.

Everything fuzzy — is this jargon, is this a metaphor, is this sentence actually clear — stays in the
method prompt and in the audit. This module never judges meaning. It counts shapes, so a finding is
reproducible and is never an opinion, and a build can be handed the same rule twice and get the same
answer. Findings are ADVISORY: a map is not wrong for holding a 24-word sentence, it is just harder
to read than it needs to be.

Backticked spans are stripped before scanning, the same exemption a code block gets in prose: a field
that quotes a literal is quoting, not naming code in plain text.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Iterator

from coyodex.model import ProjectModel
from coyodex.reporting import clip, shown

SENTENCE_WORD_LIMIT = 20   # one idea per sentence; longer is a split, not a style opinion
EXAMPLES_PER_KIND = 3      # how many offending fields a summary line names before it counts the rest

_BACKTICKED = re.compile(r"`[^`]*`")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_EM_DASH = "—"

# A token that is CODE rather than product language. Deliberately narrow — a shape nobody writes by
# accident — because a noisy readability check is one nobody leaves switched on.
_CODE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("file path", re.compile(r"\b[\w./-]*\w\.(?:py|ts|tsx|js|jsx|go|rb|java|kt|rs|php|cs|sql|sh|"
                             r"yaml|yml|toml|ini|cfg|json)\b")),
    ("function call", re.compile(r"\b\w+\(\s*\)")),
    ("command flag", re.compile(r"(?<![\w-])--[a-z][\w-]*")),
    ("snake_case name", re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")),
)

# A field that opens with one of these reads as a fragment once it is shown alone in a box.
_BARE_POINTERS = ("It", "This", "That", "These", "Those", "They")
_OPENS_BARE = re.compile(r"^(%s)\b" % "|".join(_BARE_POINTERS))


def strip_literals(text: str) -> str:
    """Remove backticked spans. They are quotations of a literal, not plain-language prose."""
    return _BACKTICKED.sub(" ", text)


def sentences(text: str) -> list[str]:
    """Split on sentence-ending punctuation followed by whitespace. Crude on purpose: a smarter
    splitter would need an abbreviation list, and every entry in such a list is a judgement call
    this module exists to avoid."""
    return [s.strip() for s in _SENTENCE_SPLIT.split(text.strip()) if s.strip()]


def word_count(sentence: str) -> int:
    return len(sentence.split())


def long_sentences(text: str, limit: int = SENTENCE_WORD_LIMIT) -> list[str]:
    return [s for s in sentences(strip_literals(text)) if word_count(s) > limit]


def em_dash_count(text: str) -> int:
    return strip_literals(text).count(_EM_DASH)


def code_tokens(text: str) -> list[str]:
    """Every code-shaped token in the field, deduplicated, longest form only.

    One token often matches two patterns — `cancel_order()` is both a call and a snake_case name —
    and reporting both reads as two problems where the writer has one word to fix."""
    scanned = strip_literals(text)
    found: list[str] = []
    for _label, pattern in _CODE_PATTERNS:
        for match in pattern.findall(scanned):
            if match not in found:
                found.append(match)
    return [t for t in found if not any(t != other and t in other for other in found)]


def opens_with_bare_pointer(text: str) -> str:
    """The pointer word a field opens with, or "" — a field starting "It reads the queue" is a
    fragment of a paragraph the reader will never see."""
    match = _OPENS_BARE.match(strip_literals(text).strip())
    return match.group(1) if match else ""


class Finding:
    """One readability observation about one field. `kind` groups findings for reporting so a map
    with 200 long sentences produces one counted line, never 200."""

    __slots__ = ("kind", "where", "detail")

    def __init__(self, kind: str, where: str, detail: str) -> None:
        self.kind = kind
        self.where = where
        self.detail = detail

    def __repr__(self) -> str:            # pragma: no cover - debugging aid
        return f"Finding({self.kind!r}, {self.where!r}, {self.detail!r})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Finding):
            return NotImplemented
        return (self.kind, self.where, self.detail) == (other.kind, other.where, other.detail)


def field_findings(where: str, text: str, limit: int = SENTENCE_WORD_LIMIT) -> list[Finding]:
    """Every countable readability finding for one prose field. `where` names the field to a reader
    of the report ("C3 purpose"), never a code location."""
    body = (text or "").strip()
    if not body:
        return []
    found: list[Finding] = []
    for sentence in long_sentences(body, limit):
        found.append(Finding("long sentence", where,
                             f"{word_count(sentence)} words: \"{clip(sentence)}\""))
    dashes = em_dash_count(body)
    if dashes:
        found.append(Finding("em dash", where,
                             f"{dashes} em dash{'es' if dashes > 1 else ''}: \"{clip(body)}\""))
    tokens = code_tokens(body)
    if tokens:
        found.append(Finding("code name", where, f"names {shown(tokens, 3)}"))
    pointer = opens_with_bare_pointer(body)
    if pointer:
        found.append(Finding("bare pointer", where, f"opens with \"{pointer}\""))
    return found


def scan(fields: Iterable[tuple[str, str]], limit: int = SENTENCE_WORD_LIMIT) -> list[Finding]:
    """Run every field through `field_findings`, preserving order."""
    out: list[Finding] = []
    for where, text in fields:
        out.extend(field_findings(where, text, limit))
    return out


# The fix each finding kind asks for, in the reader's words. One place, so the report and the method
# never drift apart.
_REMEDY = {
    "long sentence": f"split it — one idea per sentence, at most {SENTENCE_WORD_LIMIT} words",
    "em dash": "replace it with the word that says the link: because, but, so, for example",
    "code name": "say what it does in product words; the code link already carries the path",
    "bare pointer": "name the thing — a box is read alone, with no paragraph before it",
}


def summarize(findings: Iterable[Finding], examples: int = EXAMPLES_PER_KIND) -> list[str]:
    """One advisory line per finding kind: the count first, then a few examples.

    The count leads because a report that prints every offending field pushes the readable lines off
    the screen — the same failure the dropped-by-name note had before it was capped. Truncation goes
    through `reporting.shown` so whole-list mode and `--json` see the full set."""
    grouped: dict[str, list[Finding]] = {}
    for finding in findings:
        grouped.setdefault(finding.kind, []).append(finding)
    lines: list[str] = []
    for kind in _REMEDY:
        hits = grouped.get(kind)
        if not hits:
            continue
        examples_text = shown([f"{f.where} ({f.detail})" for f in hits], examples, sep="; ",
                              unit="field(s)")
        article = "an" if kind[0] in "aeiou" else "a"
        lines.append(f"{len(hits)} prose field{'s' if len(hits) > 1 else ''} with {article} {kind} "
                     f"— {_REMEDY[kind]}. {examples_text}")
    return lines


def iter_prose_fields(model: ProjectModel) -> Iterator[tuple[str, str]]:
    """Every reader-facing prose field in a map, as (where, text).

    Reader-facing means: a person reads this sentence in the viewer. Titles, ids, anchors, code
    links and closed-vocabulary cells are excluded — they are labels or machine values, and a word
    limit on a label is meaningless."""
    for component in model.components:
        yield f"{component.id} purpose", component.purpose
    for group in (*model.capabilities, *model.subsystems, *model.subdomains, *model.blocks):
        yield f"{group.id} purpose", group.purpose
    for uc in model.use_cases:
        yield f"{uc.id} trigger/outcome", uc.trigger_outcome
    for rule in model.rules:
        yield f"{rule.id} statement", rule.statement
        yield f"{rule.id} risk", rule.risk
    for dep in model.deps:
        yield f"{dep.id} used for", dep.used_for
    for role in model.roles:
        yield f"{role.id} wants", role.wants
    for step in model.happy_path:
        yield f"{step.id} why", step.why or ""
    for row in model.glossary:
        yield f"glossary '{row.term}'", row.meaning


# ── the half a counter cannot judge ───────────────────────────────────────────────────────────────
#
# Rules 5 and 6 of the writing rules are judgements, not counts: does the reader know this word, and
# did a short sentence buy its shortness by dropping the specific. Nothing here calls a model. The
# tool emits BATCHES, a cheap fan-out reads them, and the lead folds what comes back into the audit
# report — the same division the grounding worklist uses, and for the same reason: a deterministic
# tool that quietly depended on a model would make two runs of `audit` disagree.

READ_PROMPT_VERSION = "v1"   # bump on any change to the RULES below; a batch records the version


def build_read_prompt() -> str:
    """What a reading agent is told. Deliberately narrow: it judges the two rules a counter cannot,
    and it is told NOT to repeat the four that are already counted, because a fan-out that re-reports
    long sentences would bury its own findings under the count the lead already has."""
    return (
        "You are reading the plain-language text of a codebase map. A reader meets each field ALONE, "
        "inside one box, with no paragraph around it, and does not read code.\n\n"
        "Judge ONLY these two things:\n"
        "  1. UNKNOWN WORD — a term the reader has not met and the field does not explain. Product "
        "words and words already in the map's Glossary are fine; jargon, an internal codename, or an "
        "unexplained abbreviation is not.\n"
        "  2. LOST PRECISION — the sentence is short and plain but says nothing specific. \"The "
        "system checks the user\" is the shape: grammatical, readable, and it names no decision, no "
        "data and no actor. This is the worse failure, because it looks correct.\n\n"
        "Do NOT report sentence length, em dashes, code names or an opening \"It\" — those are "
        "counted deterministically and the lead already has the numbers.\n"
        "Be conservative. Report a field only when you can say WHICH word is unknown, or WHAT the "
        "sentence should have said. If in doubt, pass the field.\n\n"
        "For each field you flag, return its `where` exactly as given, one of `unknown word` or "
        "`lost precision`, and one short line naming the word or the missing specific."
    )


def batch_fields(fields: Iterable[tuple[str, str]], cap: int) -> list[list[tuple[str, str]]]:
    """Split the non-empty prose fields into chunks of at most `cap`, in map order.

    Empty fields are dropped here rather than at the reader: a batch padded with blanks spends a
    fan-out's attention on nothing, and the count printed to the lead would not be the work done."""
    if cap < 1:
        raise ValueError("cap must be >= 1")
    live = [(where, text) for where, text in fields if text.strip()]
    return [live[i:i + cap] for i in range(0, len(live), cap)]
