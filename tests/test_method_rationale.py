"""The rationale record is a COPY of why each rule exists. It must stay attached to its rule.

`method.md` and the `method/` docs used to carry three registers in one file: the **contract** (what
a map must contain), the **procedure** (how to run a build), and the **incident record** (the named
past build that produced a rule — "a live build spent 88 of its 278 tool calls polling", "two maps
of one repo went from 103 security rows to 19"). The third one is written for the coyodex author,
not for the build agent, and the agent paid attention cost for it on every build.

That register now lives in `internal/docs/method-rationale.md`, which the method tells agents to
ignore and which nothing in the method links to. The risk this file exists to close is the obvious
one: rationale detached from its rule rots twice as fast, because a rule can be reworded, moved or
deleted with nothing pointing back at the account that justified it. So every rationale entry names
an **Anchor** — a verbatim phrase that must still appear in the method doc it belongs to.

**What this can and cannot prove.** The anchor is a PRESENCE test, so it catches a rule that was
deleted or renamed out from under its evidence. It cannot catch a rule whose body was gutted while
its heading survived — which is why `test_every_anchor_is_more_than_a_section_label` refuses an
anchor that is only a bold lead-in: an anchor has to quote enough of the rule that removing the rule
removes the anchor. An adversarial review proved the weak form was defeatable, with a rule
*inverted* in place and the test still green.

Pure text. No fixture, no LLM, no tool import.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RATIONALE = "internal/docs/method-rationale.md"

#: The agent-facing method corpus. A rationale entry may only point into one of these.
METHOD_DOCS: frozenset[str] = frozenset({
    "method.md",
    "method/change-impact.md",
    "method/diagrams.md",
    "method/dispatch.md",
    "method/domain-cards.md",
    "method/model.md",
    "method/templates/harvest-contract.md",
    "method/templates/project-map.template.md",
    "method/templates/skeptic-contract.md",
})

#: Shortest anchor that can plausibly quote a rule rather than label one. Below this, deleting the
#: rule and leaving a heading behind keeps the test green.
MIN_ANCHOR_CHARS = 30

_HEADING = re.compile(r"^### (?P<id>R\d+) — (?P<title>.+)$")
_FIELD = re.compile(r"^- \*\*(?P<key>Where|Anchor|Evidence)\*\*: (?P<value>.+)$")


def make_record_text() -> str:
    """The record, with a failure that names the file rather than a bare traceback.

    It is untracked-and-un-ignored today, so the honest failure mode when it is missing is "commit
    it", not `FileNotFoundError` from inside a helper."""
    path = REPO_ROOT / RATIONALE
    assert path.is_file(), (
        f"{RATIONALE} is missing. It holds the incident evidence behind every rule in the method, "
        "and this file is the only thing pairing the two. It must be committed together with the "
        "method docs — if this fails on a fresh clone, the record was left out of the commit.")
    return path.read_text(encoding="utf-8")


def _unwrap(value: str) -> str:
    """A backtick-quoted field value. Anchors contain backticks themselves (`` `coyodex fix` ``), so
    this spans first-to-last backtick instead of matching a backtick-free run — the bug that made
    this test silently skip 11 of 115 entries and mispair 11 more."""
    assert value.startswith("`") and value.endswith("`") and len(value) > 2, (
        f"field value is not backtick-quoted: {value!r}")
    return value[1:-1]


def make_entries() -> list[dict[str, str]]:
    """Every rationale entry, parsed line by line off the record.

    Line-by-line on purpose: a single multiline regex over the whole file fails OPEN — one entry it
    cannot match gets absorbed into its neighbour's fields, so the parse loses entries and silently
    attributes one entry's anchor to another entry's id."""
    entries: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for lineno, line in enumerate(make_record_text().splitlines(), start=1):
        head = _HEADING.match(line)
        if head:
            current = {"id": head.group("id"), "title": head.group("title"), "line": str(lineno)}
            entries.append(current)
            continue
        field = _FIELD.match(line)
        if field and current is not None:
            key, value = field.group("key"), field.group("value")
            current[key.lower()] = value if key == "Evidence" else _unwrap(value)
    return entries


def make_doc_text(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


def flat(text: str) -> str:
    """Whitespace-collapsed text, for anchor matching.

    The method corpus is hard-wrapped at ~100 columns, so any anchor long enough to quote a rule
    spans a line break — and re-wrapping the paragraph would then "delete" the rule as far as a
    literal match is concerned. Matching on collapsed whitespace makes an anchor survive a reflow
    and still fail on a real edit to the words."""
    return " ".join(text.split())


def test_every_heading_parses_into_a_complete_entry():
    """The check that keeps every check below from going vacuous.

    A count threshold ("at least 100") is not enough: the parse was passing at 104 of 115. It has to
    be an equality against the headings actually in the file, and every entry has to carry all three
    fields — a missing `Anchor` is an entry that guards nothing."""
    text = make_record_text()
    headings = re.findall(r"^### (R\d+) — ", text, re.MULTILINE)
    entries = make_entries()
    assert len(entries) == len(headings), (
        f"{RATIONALE}: {len(headings)} headings but {len(entries)} parsed entries — the record's "
        "format has drifted from what this test reads")
    incomplete = [f'{e["id"]} (line {e["line"]}) missing {k}'
                  for e in entries for k in ("where", "anchor", "evidence") if k not in e]
    assert not incomplete, ("every entry needs Where / Anchor / Evidence:\n  "
                            + "\n  ".join(incomplete))


def test_every_anchor_still_exists_in_its_method_doc():
    """The one check that matters: a rule cannot be deleted or reworded away from its evidence.

    When this fails, the fix is a decision, not a text edit. Either the rule moved and the anchor
    should follow it, or the rule was RETIRED — in which case say so in the entry (and keep the
    entry: the point of the record is that a future incident cannot silently re-add a rule that was
    dropped on purpose)."""
    orphans: list[str] = []
    for e in make_entries():
        if flat(e["anchor"]) not in flat(make_doc_text(e["where"])):
            orphans.append(f'{e["id"]} ({e["title"]}) → {e["where"]}: {e["anchor"]!r}')
    assert not orphans, (
        "rationale entries whose anchor no longer appears in the method doc — the rule they explain "
        "was reworded, moved or deleted:\n  " + "\n  ".join(orphans))


def test_every_anchor_matches_exactly_once():
    """An anchor that matches twice cannot say WHICH occurrence it is guarding, so one of them can
    go with the test still green."""
    ambiguous = [f'{e["id"]} → {e["where"]}: {e["anchor"]!r} ({n} matches)'
                 for e in make_entries()
                 if (n := flat(make_doc_text(e["where"])).count(flat(e["anchor"]))) > 1]
    assert not ambiguous, ("an anchor must identify one place in its doc:\n  "
                           + "\n  ".join(ambiguous))


def test_every_anchor_is_more_than_a_section_label():
    """An anchor must quote the RULE, not the heading above it.

    This is the finding an adversarial review proved: with `**Scope warning.**` as the anchor, the
    four lines of rule under it were replaced with "Serial builds may skip Phases 3.5 and 4" and the
    suite stayed green. A bold lead-in survives its own paragraph being gutted, so it certifies
    nothing. Two shapes are refused: an anchor that is entirely one bold span, and an anchor too
    short to contain a claim."""
    weak: list[str] = []
    for e in make_entries():
        anchor = e["anchor"]
        stripped = anchor.strip()
        only_bold = (stripped.startswith("**") and stripped.endswith("**")
                     and "**" not in stripped[2:-2])
        if only_bold:
            weak.append(f'{e["id"]} (line {e["line"]}): entirely a bold lead-in — {anchor!r}')
        elif len(stripped) < MIN_ANCHOR_CHARS:
            weak.append(f'{e["id"]} (line {e["line"]}): {len(stripped)} chars — {anchor!r}')
    assert not weak, (
        f"an anchor must quote enough of the rule that deleting the rule deletes the anchor "
        f"(>= {MIN_ANCHOR_CHARS} chars, and never just a bold heading):\n  " + "\n  ".join(weak))


def test_every_entry_points_at_an_agent_facing_doc():
    """Rationale for something that is not part of the method is not rationale, it is a note."""
    strays = [f'{e["id"]} → {e["where"]}' for e in make_entries()
              if e["where"] not in METHOD_DOCS]
    assert not strays, (
        f"a rationale entry must name one of the method docs {sorted(METHOD_DOCS)}: "
        + ", ".join(strays))


def test_entry_ids_are_unique():
    """The ids are how one entry is referred to from another; a duplicate makes that ambiguous."""
    ids = [e["id"] for e in make_entries()]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    assert not dupes, f"duplicate rationale ids in {RATIONALE}: {dupes}"


def test_every_entry_carries_real_evidence():
    """An entry with no account in it is a pointer to nothing — the register split would have lost
    the incident rather than moved it."""
    thin = [f'{e["id"]}: {len(e["evidence"])} chars' for e in make_entries()
            if len(e["evidence"].strip()) < 40]
    assert not thin, ("a rationale entry must carry the account that was moved out of the method, "
                      "not a stub: " + ", ".join(thin))


def test_the_method_never_points_readers_at_the_rationale_record():
    """The method tells agents to IGNORE `internal/`. A method doc that links here would contradict
    that in the same breath — which is the contradiction this split was careful to avoid. The link
    runs the other way only: the record points at the method, and the anchors above keep it honest.
    """
    offenders = [rel for rel in sorted(METHOD_DOCS)
                 if "method-rationale" in make_doc_text(rel)]
    assert not offenders, (
        "the agent-facing method must not reference the author's rationale record "
        f"({RATIONALE}); it is under internal/, which the method tells agents to ignore: "
        + ", ".join(offenders))
