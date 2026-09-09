"""Tests for `coyodex contract <name>` — the verb that hands an agent its half of a contract.

The bug this verb exists to remove was silent: a build filled the skeptic template with one text
replacement and sent the whole file, so ten skeptics received the LEAD's instructions as their own
and four were told to read a claims file that does not exist. Nothing in the map or the gates could
see it. So the tests below pin the boundary itself, in both template shapes, and pin that no
lead-facing sentence survives into what an agent receives.
"""
from __future__ import annotations

import io
import contextlib
import json
from pathlib import Path

import pytest

from coyodex import contract

REPO_ROOT = Path(__file__).resolve().parent.parent

# Sentences that exist ONLY to instruct the lead. Any one of them in a rendered contract means the
# header crossed the boundary — the exact failure a real build paid for.
_LEAD_ONLY = ("Copy this file", "do not retype it from prose", "instructions to you, the",
              "Everything below the line is what the agent reads")


def make_quoted_template() -> str:
    return ("# Title\n\nLead instructions here.\n\n> You are an agent.\n>\n> Do the thing.\n")


def make_plain_template() -> str:
    return ("# Title\n\nLead instructions here.\n\n---\n\nYou are an agent.\n\nDo the thing.\n")


def render(name: str) -> str:
    return contract.render(name, REPO_ROOT)


# --- the boundary, both shapes -----------------------------------------------------------------

def test_a_quoted_template_yields_its_block_with_the_marker_stripped() -> None:
    assert contract.agent_half(make_quoted_template()) == "You are an agent.\n\nDo the thing."


def test_a_plain_template_yields_everything_after_its_divider() -> None:
    assert contract.agent_half(make_plain_template()) == "You are an agent.\n\nDo the thing."


def test_a_template_with_no_boundary_raises_rather_than_handing_over_the_header() -> None:
    """Silently returning the whole file is the failure this verb exists to remove, so the
    no-boundary case must be loud."""
    try:
        contract.agent_half("# Title\n\nLead instructions only.\n")
    except ValueError as exc:
        assert "no agent boundary" in str(exc)
        return
    raise AssertionError("a template with no boundary must raise")


def test_two_dividers_are_ambiguous_and_refused() -> None:
    try:
        contract.agent_half("# T\n\n---\n\nmiddle\n\n---\n\nagent\n")
    except ValueError as exc:
        assert "ambiguous" in str(exc)
        return
    raise AssertionError("two dividers must raise rather than guess which one is the boundary")


# --- the real templates ------------------------------------------------------------------------

def test_every_real_contract_renders_and_starts_with_the_agents_own_words() -> None:
    for name in contract.CONTRACTS:
        text = render(name)
        assert text.strip(), f"{name} rendered empty"
        assert text.lstrip().startswith("You are"), (
            f"{name} does not open by addressing the agent — the boundary is in the wrong place")


def test_no_lead_facing_sentence_survives_into_any_rendered_contract() -> None:
    for name in contract.CONTRACTS:
        text = render(name)
        leaked = [phrase for phrase in _LEAD_ONLY if phrase in text]
        assert not leaked, f"{name} leaks lead-only text {leaked} into the agent's prompt"


def test_no_quote_marker_survives_into_a_rendered_contract() -> None:
    """A `> ` left on every line is how an agent learns it was handed a document rather than a
    brief; it also breaks the fenced JSON examples the contracts carry."""
    for name in contract.CONTRACTS:
        stray = [line for line in render(name).splitlines() if line.startswith(">")]
        assert not stray, f"{name} still carries {len(stray)} quoted line(s)"


# --- the writing rules ride along, but only where they can be acted on --------------------------

def test_the_authoring_contracts_carry_the_writing_rules() -> None:
    for name in sorted(contract.AUTHORING):
        assert "One idea per sentence" in render(name), (
            f"{name} agents author reader-facing prose and received no writing rule")


def test_the_other_contracts_do_not_pay_for_rules_they_cannot_act_on() -> None:
    for name in set(contract.CONTRACTS) - contract.AUTHORING:
        assert "One idea per sentence" not in render(name), (
            f"{name} agents author no reader-facing prose; the rules are prompt weight there")


# --- the command line ----------------------------------------------------------------------------

def test_an_unknown_contract_name_is_refused_with_the_valid_set() -> None:
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        assert contract.main(["nonsense"]) == 2
    assert "unknown contract" in err.getvalue()


def test_no_argument_prints_usage_and_fails_so_a_typo_is_never_silent() -> None:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        assert contract.main([]) == 2
    assert "usage: coyodex contract" in out.getvalue()


def test_the_verb_prints_the_contract_to_stdout() -> None:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        assert contract.main(["skeptic"]) == 0
    assert out.getvalue().lstrip().startswith("You are a fresh-context skeptic")


# --- `--slots` / `--fill` / `--brief`: the filled contract and the pointer that names it ---------
#
# A slot left unfilled reaches an agent as the literal `«REPO»`, and no gate sees it: the fragment
# that comes back is well-formed and simply about the wrong thing. A hand-composed brief grows —
# one build typed 159,993 bytes of brief across six fan-outs. Both jobs move into the verb here.

#: Slots whose CONTENT is checked, not only its presence — `_slot_content_faults`. A uniform
#: placeholder cannot satisfy those, so the builder gives each one a value of the right shape.
_CONTENTFUL_SLOTS = {"SERVES": "UC7 rename a page, R1 the owner"}


def make_slot_values(name: str, value: str = "filled") -> dict[str, str]:
    """Every slot of one contract, each filled with the same placeholder."""
    out = {k: value for k in contract.slots(name)}
    for key, real in _CONTENTFUL_SLOTS.items():
        if key in out:
            out[key] = real
    return out


def test_the_skeleton_lists_only_slots_the_agent_actually_receives() -> None:
    """The lead's half above the divider talks ABOUT «angle-bracket» slots. A skeleton listing
    those would ask the lead to fill words that reach nobody."""
    keys = contract.slots("rules")
    assert "angle-bracket" not in keys
    assert set(keys) == {"REPO", "PROJECT", "COYODEX_HOME", "MAP", "BLOCK", "AGENT_ID"}


def test_the_skeleton_is_json_with_every_slot_empty() -> None:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        assert contract.main(["rules", "--slots"]) == 0
    assert json.loads(out.getvalue()) == {k: "" for k in contract.slots("rules")}


def test_a_clean_fill_leaves_no_slot_behind() -> None:
    text = contract.fill("rules", make_slot_values("rules"))
    assert "«" not in text and "»" not in text


def test_every_shipped_contract_can_be_filled_from_its_own_skeleton() -> None:
    """The skeleton and the filler must agree for all six, or a phase ships a verb that refuses
    the very keys it just printed."""
    for name in contract.CONTRACTS:
        assert "«" not in contract.fill(name, make_slot_values(name))


def test_a_missing_slot_is_refused_and_named() -> None:
    with pytest.raises(ValueError, match="no value given for"):
        contract.fill("rules", {"REPO": "/repo"})


def test_a_blank_value_is_refused_because_no_gate_can_see_one() -> None:
    values = make_slot_values("rules")
    values["REPO"] = "   "
    with pytest.raises(ValueError, match="blank"):
        contract.fill("rules", values)


def test_a_value_that_is_still_a_slot_name_is_refused() -> None:
    values = make_slot_values("rules")
    values["MAP"] = "«MAP»"
    with pytest.raises(ValueError, match="guillemets"):
        contract.fill("rules", values)


def test_a_key_that_is_no_slot_of_this_contract_is_refused_with_the_real_list() -> None:
    values = make_slot_values("rules")
    values["NOPE"] = "x"
    with pytest.raises(ValueError, match="no such slot"):
        contract.fill("rules", values)


def test_every_fault_is_reported_in_one_run() -> None:
    """Learning three missing slots must cost one run, not three — the brief→re-read loop this
    verb exists to end."""
    with pytest.raises(ValueError) as exc:
        contract.fill("rules", {"REPO": "  ", "NOPE": "x"})
    message = str(exc.value)
    assert "no such slot" in message and "no value given for" in message and "blank" in message


def test_the_brief_is_the_id_the_path_and_one_fixed_sentence() -> None:
    text = contract.brief("h1", Path("/abs/scratch/h1.md"))
    assert text.splitlines() == ["h1", "/abs/scratch/h1.md", contract.BRIEF_SENTENCE]
    assert len(text.encode("utf-8")) <= contract.BRIEF_MAX_BYTES


def test_a_relative_brief_path_is_refused_rather_than_resolved() -> None:
    """Resolving it would build a plausible absolute path out of the lead's cwd — the
    wrong-directory mistake, made silently, inside an agent's prompt."""
    with pytest.raises(ValueError, match="not absolute"):
        contract.brief("h1", Path("h1.md"))


def test_an_agent_id_with_a_space_is_refused() -> None:
    with pytest.raises(ValueError, match="one word"):
        contract.brief("h 1", Path("/abs/h1.md"))


def test_a_brief_over_the_pointer_cap_is_refused() -> None:
    with pytest.raises(ValueError, match="pointer cap"):
        contract.brief("h1", Path("/" + "d" * contract.BRIEF_MAX_BYTES + "/h1.md"))


def test_fill_writes_the_file_and_brief_prints_the_pointer(tmp_path: Path) -> None:
    slots = tmp_path / "slots.json"
    slots.write_text(json.dumps(make_slot_values("rules")), encoding="utf-8")
    out = tmp_path / "r3.md"
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(io.StringIO()):
        assert contract.main(["rules", "--fill", str(slots), "--out", str(out),
                              "--brief", "r3"]) == 0
    assert "«" not in out.read_text(encoding="utf-8")
    assert stdout.getvalue().splitlines() == ["r3", str(out), contract.BRIEF_SENTENCE]


def test_a_refused_fill_writes_no_file(tmp_path: Path) -> None:
    slots = tmp_path / "slots.json"
    slots.write_text(json.dumps({"REPO": "/repo"}), encoding="utf-8")
    out = tmp_path / "r3.md"
    with contextlib.redirect_stderr(io.StringIO()):
        assert contract.main(["rules", "--fill", str(slots), "--out", str(out)]) == 2
    assert not out.exists()


def test_a_refused_brief_leaves_no_contract_nothing_points_at(tmp_path: Path) -> None:
    """The brief is composed before the write on purpose: a filled contract with no sendable
    pointer is a file the fan-out will never open."""
    slots = tmp_path / "slots.json"
    slots.write_text(json.dumps(make_slot_values("rules")), encoding="utf-8")
    with contextlib.redirect_stderr(io.StringIO()):
        assert contract.main(["rules", "--fill", str(slots), "--out", "relative.md",
                              "--brief", "r3"]) == 2
    assert not Path("relative.md").exists()


def test_fill_refuses_to_print_the_contract_to_stdout(tmp_path: Path) -> None:
    """A filled contract on stdout is one pipe away from being pasted, which is the 13 KB brief
    the pointer exists to replace."""
    slots = tmp_path / "slots.json"
    slots.write_text(json.dumps(make_slot_values("rules")), encoding="utf-8")
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        assert contract.main(["rules", "--fill", str(slots)]) == 2
    assert "needs --out" in err.getvalue()


def test_slots_does_not_combine_with_fill(tmp_path: Path) -> None:
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        assert contract.main(["rules", "--slots", "--fill", "x.json", "--out", "y.md"]) == 2
    assert "does not combine" in err.getvalue()


def test_an_unreadable_slots_file_is_refused_by_name(tmp_path: Path) -> None:
    bad = tmp_path / "slots.json"
    bad.write_text("{not json", encoding="utf-8")
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        assert contract.main(["rules", "--fill", str(bad), "--out", str(tmp_path / "o.md")]) == 2
    assert "not readable JSON" in err.getvalue()


# --- a filled contract is an agent's whole brief ----------------------------------------------
# Under pointer dispatch the agent reads its brief from the file whenever it gets round to it, so
# overwriting one rewrites the instructions of something that may still be running. On the
# 2026-08-29 mcpolis build turn 125 hand-wrote `briefs/t1.md` for an agent launched at turn 127, and
# turn 160's generator looped `--out …/briefs/{aid}.md` with `aid="t1"` and rewrote it mid-flight —
# exit 0, no warning. The lead saw only the downstream fragment-name collision, 19 turns later.

def _fill_to(tmp: Path, out: Path, extra: list[str] | None = None) -> tuple[int, str]:
    import contextlib, io, json as _json
    from coyodex.contract import main, slots
    values = {k: "x" for k in slots("skeptic")}
    src = tmp / "slots.json"
    src.write_text(_json.dumps(values), encoding="utf-8")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        rc = main(["skeptic", "--fill", str(src), "--out", str(out), *(extra or [])])
    return rc, buf.getvalue()


def test_filling_over_an_existing_brief_is_refused():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        out = tmp / "brief.md"
        out.write_text("AN AGENT IS READING THIS", encoding="utf-8")
        rc, msg = _fill_to(tmp, out)
        body = out.read_text(encoding="utf-8")
    assert rc == 2, msg
    assert "already exists" in msg, msg
    assert body == "AN AGENT IS READING THIS", body


def test_force_overwrites_when_the_lead_knows_nothing_is_reading_it():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        out = tmp / "brief.md"
        out.write_text("stale", encoding="utf-8")
        rc, msg = _fill_to(tmp, out, ["--force"])
        body = out.read_text(encoding="utf-8")
    assert rc == 0, msg
    assert body != "stale", body


def test_a_fresh_path_still_writes():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        out = tmp / "nested" / "brief.md"
        rc, msg = _fill_to(tmp, out)
    assert rc == 0, msg


# --- a slot key must be typable (retro 2026-09-01, argus row 8) -----------------------------------
# `contract harvest --slots` returned keys like
# `«absolute paths this agent owns; list a directory first, then read each file»`. Nobody types
# that, so all four brief generators filled the skeleton BY POSITION — across 51 of 55 briefs — and
# a positional fill is silent when it is wrong. `trace` already used bare tokens.

def test_no_shipped_contract_has_a_prose_slot_key():
    from coyodex.contract import CONTRACTS, slots
    for name in CONTRACTS:
        slots(name)          # raises ValueError naming the offending keys


def test_a_prose_slot_key_is_refused_with_the_key_it_objects_to(tmp_path):
    import re
    from coyodex import contract
    home = tmp_path / "home"
    (home / "method" / "templates").mkdir(parents=True)
    (home / "method" / "templates" / "toy-contract.md").write_text(
        "lead half\n\n> agent half with «FINE» and «a whole sentence nobody types».\n",
        encoding="utf-8")
    contract.CONTRACTS["toy"] = "toy-contract.md"
    try:
        with pytest.raises(ValueError, match=re.escape("a whole sentence nobody types")):
            contract.slots("toy", root=home)
    finally:
        del contract.CONTRACTS["toy"]


def test_the_doors_contract_ships_and_names_its_own_slots():
    """The doors rule is ~9 KB of method.md and was hand-paraphrased into every brief; the argus
    build's was 9,031 bytes with no gate on the paraphrase."""
    from coyodex.contract import render, slots
    assert set(slots("doors")) == {"FLOWS", "MAP", "REPO", "SURFACES", "AGENT_ID", "COYODEX_HOME"}
    text = render("doors")
    # The rule the hand-written brief dropped.
    assert "kind: service" in text and "audience: internal" in text
    # The two halves a paraphrase most often loses.
    assert "EVERY EXCHANGE IN BETWEEN" in text
    assert "add NO door" in text


# --- the cd rule must travel in the BRIEF (retro 2026-09-02, mcpolis N4) --------------------------
# The rule lived only in `method.md`, which no sub-agent reads. On the 2026-09-02 build 8 of 75
# agents stepped into the coyodex clone, 33 times, and one build before that the same slip edited
# the clone's committed map. A rule an agent never sees is not a rule.

def test_every_dispatched_contract_carries_the_cd_rule():
    from coyodex.contract import CONTRACTS, render
    # `harvest-t5` is an ADDENDUM appended to one harvest brief, which carries the rule itself.
    for name in CONTRACTS:
        if name == "harvest-t5":
            continue
        assert "NEVER `cd` into the coyodex clone" in render(name), name


def test_the_cd_rule_says_it_persists_BEYOND_this_command():
    """"across `;` and `&&`" was the whole sentence, and the expensive half is the rest of the
    session — a later command that mentions no clone at all still reads the wrong map."""
    from coyodex.contract import render
    text = render("trace")
    assert "rest of your session" in text, text[:400]


# --- what a slot is filled WITH (retro 2026-09-02, mcpolis findings 5 and 6) ----------------------
# A filled slot is a filled slot, so no other check could see either of these.

def _harvest_values(**over) -> dict[str, str]:
    from coyodex.contract import slots
    base = {k: "x" for k in slots("harvest")}
    base.update({"SERVES": "UC7 rename a page, R1 the owner", "SLICE_KIND": "structural",
                 "EXPECTED_COMPONENTS": "6"})
    base.update(over)
    return base


def test_a_SERVES_naming_no_behavioural_id_is_refused():
    """All 14 harvest briefs on one build filled it with a map-section name. Assertion 31 went
    1.00 -> 0.00 and the harvest returned components with no backbone edge at all."""
    from coyodex.contract import fill
    with pytest.raises(ValueError, match="names no behavioural id"):
        fill("harvest", _harvest_values(SERVES="T5 domain model"))


def test_a_SERVES_naming_any_behavioural_id_passes():
    from coyodex.contract import fill
    for value in ("UC7 rename a page", "R1 the owner", "CAP2 billing", "HP3 the third step"):
        fill("harvest", _harvest_values(SERVES=value))


def test_a_component_budget_is_NOT_judged_by_the_slice_kind_text():
    """This check was written and REVERTED. `«SLICE_KIND»` is free text — a real value is a
    sentence — so matching it against words like `config` or `entit` refused legitimate structural
    slices, and the remedy it demanded (write `0`) put "Expect roughly 0 components" in front of a
    slice that really had seven. Catching the real fault needs an enum of slice kinds, which the
    contract does not have."""
    from coyodex.contract import fill
    for kind in ("config loading and startup", "HTTP routing and config parsing",
                 "deployment scripts and the CI workflow", "the entity store adapters",
                 "T5 entities"):
        fill("harvest", _harvest_values(SLICE_KIND=kind, EXPECTED_COMPONENTS="7"))


def test_a_path_in_a_batch_id_slot_is_refused() -> None:
    """The contract composes `claims-«CLAIMS».json` and `verdicts-«BATCH».json` itself; a path in
    either slot names a file that exists nowhere, in every brief — 38 of 38 on one build."""
    values = make_slot_values("skeptic")
    values["CLAIMS"] = ".coyodex/verify/claims-backbone-1.json"
    with pytest.raises(ValueError, match="looks like a path"):
        contract.fill("skeptic", values)
    values["CLAIMS"], values["BATCH"] = "backbone-1", "backbone-1a"
    assert "«" not in contract.fill("skeptic", values)


def test_the_closer_contracts_claims_block_may_carry_paths() -> None:
    """The closer's «CLAIMS» is a pasted block of claims and `dump` output, `path:line` and all; the
    skeptic-only path check must not refuse it — its first version did, on the real build's slots."""
    values = make_slot_values("closer")
    values["CLAIMS"] = "- C1 reads E1 [backend/src/app.py:12]\n  dump: {\"where\": \"backend/src/app.py:12\"}"
    assert "«" not in contract.fill("closer", values)


# --- N skeptic briefs from an `audit --batches` directory (retro 2026-09-08, row 19) -------------

def _batches_dir(tmp: Path) -> Path:
    import json as _json
    d = tmp / "verify"
    d.mkdir()
    for bid, theme in (("security", "security"), ("backbone", "backbone"), ("small", "mixed")):
        (d / f"claims-{bid}.json").write_text(_json.dumps({"theme": theme, "claims": []}),
                                               encoding="utf-8")
    return d


def _skeptic_slots_file(tmp: Path, **over: str) -> Path:
    import json as _json
    from coyodex.contract import slots
    values = {k: "x" for k in slots("skeptic") if k not in ("BATCH", "CLAIMS")}
    values.update(over)
    src = tmp / "slots.json"
    src.write_text(_json.dumps(values), encoding="utf-8")
    return src


def _from_batches(tmp: Path, extra: list[str] | None = None) -> tuple[int, str]:
    import contextlib, io
    from coyodex.contract import main
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        rc = main(["skeptic", "--from-batches", str(tmp / "verify"), "--fill",
                   str(tmp / "slots.json"), "--out-dir", str(tmp / "briefs"), *(extra or [])])
    return rc, buf.getvalue()


def test_from_batches_writes_one_brief_per_claims_file_and_votes_by_theme(tmp_path: Path) -> None:
    """Every build hand-wrote this loop, with `--force` on all 38 briefs. One brief per
    `claims-*.json`, BATCH and CLAIMS filled from the file name; `--votes security=3` writes
    three voters over the one security claims file."""
    _batches_dir(tmp_path)
    _skeptic_slots_file(tmp_path)
    rc, out = _from_batches(tmp_path, ["--votes", "security=3"])
    assert rc == 0, out
    names = sorted(p.name for p in (tmp_path / "briefs").glob("skeptic-*.md"))
    assert names == ["skeptic-backbone.md", "skeptic-security-a.md", "skeptic-security-b.md",
                     "skeptic-security-c.md", "skeptic-small.md"], names
    voter = (tmp_path / "briefs" / "skeptic-security-b.md").read_text(encoding="utf-8")
    assert "claims-security.json" in voter and "security-b" in voter and "«" not in voter
    assert "5 brief(s) written, 0 skipped" in out and out.count("Read it COMPLETELY") == 5, out


def test_from_batches_never_rewrites_an_existing_brief(tmp_path: Path) -> None:
    _batches_dir(tmp_path)
    _skeptic_slots_file(tmp_path)
    (tmp_path / "briefs").mkdir()
    (tmp_path / "briefs" / "skeptic-backbone.md").write_text("AN AGENT IS READING THIS",
                                                              encoding="utf-8")
    rc, out = _from_batches(tmp_path)
    assert rc == 0, out
    assert (tmp_path / "briefs" / "skeptic-backbone.md").read_text(encoding="utf-8") == \
        "AN AGENT IS READING THIS"
    assert "2 brief(s) written, 1 skipped" in out, out


def test_from_batches_refuses_a_slots_file_that_names_batch_or_claims(tmp_path: Path) -> None:
    _batches_dir(tmp_path)
    _skeptic_slots_file(tmp_path, BATCH="b1")
    rc, out = _from_batches(tmp_path)
    assert rc == 2 and "fills «BATCH» and «CLAIMS» itself" in out, out
    assert not (tmp_path / "briefs").exists() or not list((tmp_path / "briefs").glob("*"))


def test_a_harvest_fill_records_its_component_budget(tmp_path: Path) -> None:
    """`lint-fragment --expect` holds one slice to its budget; nothing summed them (60 budgeted,
    114 shipped). The fill records each brief's budget where `finalize` adds them up."""
    import contextlib, io, json as _json
    from coyodex.contract import main
    repo = tmp_path / "repo"
    repo.mkdir()
    values = _harvest_values(REPO_ABS=str(repo), **{"agent-id": "t1"}, EXPECTED_COMPONENTS="~6")
    src = tmp_path / "slots.json"
    src.write_text(_json.dumps(values), encoding="utf-8")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        rc = main(["harvest", "--fill", str(src), "--out", str(tmp_path / "t1.md")])
    assert rc == 0, buf.getvalue()
    doc = _json.loads((repo / ".coyodex" / "verify" / "budgets.json").read_text(encoding="utf-8"))
    assert doc == {"harvest": {"t1": 6}}, doc
