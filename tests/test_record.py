#!/usr/bin/env python3
"""Tests for `coyodex record` — the one writer for a recorded exception.

Every advisory family names an extras heading an operator may write a `<id>: <why>` line under, and
there was no command to write one. A live build hand-appended into one fragment's extras SIX times,
with no check that the heading was one a tool reads, no check on the line's shape, no dedup, and no
way to correct a record whose facts moved — it find-and-replaced its own paragraph two turns later
with a fragile `body.find(...)` + `assert`.

Run either way (needs an editable install: `make deps`):
    python3 tests/test_record.py
    pytest tests/test_record.py
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from coyodex.model import ExtraSection, ProjectModel
from coyodex.record import KNOWN_HEADINGS, append_line, main


def make_fragment(tmp: str, extras: list[dict] | None = None) -> Path:
    p = Path(tmp) / "behavioral.json"
    p.write_text(json.dumps({"title": "T", "goal": "g", "extras": extras or []}), encoding="utf-8")
    return p


def make_model(heading: str = "", body: str = "") -> ProjectModel:
    m = ProjectModel(title="T", goal="g")
    if heading:
        m.extras = [ExtraSection(heading=heading, body=body)]
    return m


def test_appending_creates_the_section_when_it_is_absent():
    m = make_model()
    changed, msg = append_line(m, "Balance exceptions", "UC5: two clauses, one goal — checkout.")
    assert changed and "recorded under" in msg
    assert m.extras[0].heading == "Balance exceptions"
    assert "UC5:" in m.extras[0].body


def test_appending_keeps_the_lines_already_there():
    m = make_model("Balance exceptions", "UC1: first — why.\n")
    append_line(m, "Balance exceptions", "UC2: second — why.")
    body = m.extras[0].body
    assert "UC1: first" in body and "UC2: second" in body


def test_recording_the_same_line_twice_is_a_no_op():
    m = make_model("Balance exceptions", "UC1: first — why.\n")
    changed, msg = append_line(m, "Balance exceptions", "UC1: first — why.")
    assert not changed and "already recorded" in msg
    assert m.extras[0].body.count("UC1:") == 1


def test_replace_rewrites_the_line_instead_of_appending_a_second_one():
    """The stale-paragraph problem: a live build wrote a fourteen-component list, then had to
    find-and-replace its own text with a hand-rolled body.find() + assert."""
    m = make_model("Balance exceptions", "isolated: 14 components — why.\n")
    changed, msg = append_line(m, "Balance exceptions", "isolated: 7 components — the corrected why.",
                               replace_prefix="isolated:")
    assert changed and "replaced under" in msg
    assert m.extras[0].body.count("isolated:") == 1
    assert "7 components" in m.extras[0].body


def test_replace_says_so_when_nothing_matched():
    m = make_model("Balance exceptions", "UC1: first — why.\n")
    changed, msg = append_line(m, "Balance exceptions", "isolated: 7 — why.",
                               replace_prefix="isolated:")
    assert not changed and "nothing replaced" in msg


def test_the_heading_must_be_one_a_check_actually_reads():
    """A line under an invented heading silences nothing, and the operator believes it was handled."""
    with tempfile.TemporaryDirectory() as tmp:
        frag = make_fragment(tmp)
        assert main(["--map", str(frag), "--heading", "My notes", "--line", "UC1: because"]) == 2


def test_every_known_heading_is_accepted():
    with tempfile.TemporaryDirectory() as tmp:
        for heading in KNOWN_HEADINGS:
            frag = make_fragment(tmp)
            assert main(["--map", str(frag), "--heading", heading,
                         "--line", "UC1: a stated reason"]) == 0, heading


def test_a_key_with_no_why_is_refused():
    """A key alone is a dismissal — the rule every escape family already states."""
    with tempfile.TemporaryDirectory() as tmp:
        frag = make_fragment(tmp)
        assert main(["--map", str(frag), "--heading", "Balance exceptions", "--line", "UC5:"]) == 2
        assert main(["--map", str(frag), "--heading", "Balance exceptions", "--line", "UC5"]) == 2


def test_the_heading_match_is_case_and_space_tolerant_like_the_readers():
    with tempfile.TemporaryDirectory() as tmp:
        frag = make_fragment(tmp, [{"heading": "Balance exceptions", "body": "UC1: a — why.\n"}])
        assert main(["--map", str(frag), "--heading", "  balance EXCEPTIONS ",
                     "--line", "UC2: b — why."]) == 0
        doc = json.loads(frag.read_text())
        sections = [x for x in doc["extras"] if x["heading"] == "Balance exceptions"]
        assert len(sections) == 1, "must not create a second section that differs only in case"
        assert "UC1:" in sections[0]["body"] and "UC2:" in sections[0]["body"]


def test_an_unreadable_map_is_refused_rather_than_created():
    with tempfile.TemporaryDirectory() as tmp:
        missing = str(Path(tmp) / "nope.json")
        assert main(["--map", missing, "--heading", "Balance exceptions", "--line", "UC1: w"]) == 2
        assert not Path(missing).exists()


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"ok   {fn.__name__}")


# --- the extras fragment is seeded, not demanded (retro 2026-08-14) -------------------------------
# A build ran 21 well-formed `record` calls in one turn and every one failed with `cannot read …
# extras.json — no such file`: no fan-out agent owns creating that fragment. The workaround was
# `echo '{"extras": []}' >`, i.e. the hand-rolled write this command exists to replace.

def test_a_missing_extras_fragment_is_seeded_and_the_record_lands(capsys):
    with tempfile.TemporaryDirectory() as td:
        target = Path(td) / "extras.json"
        assert main(["--map", str(target), "--heading", "Audit exceptions",
                     "--line", "HP5: seeded out of band by the demo"]) == 0
        assert "seeded" in capsys.readouterr().out
        doc = json.loads(target.read_text())
        assert doc["extras"][0]["heading"] == "Audit exceptions"
        assert "HP5" in doc["extras"][0]["body"]


def test_seeding_is_limited_to_extras_json_so_a_typo_is_still_refused(capsys):
    with tempfile.TemporaryDirectory() as td:
        target = Path(td) / "project-mapp.json"          # a plausible typo
        assert main(["--map", str(target), "--heading", "Audit exceptions", "--line", "HP5: why"]) == 2
        assert "no such file" in capsys.readouterr().err
        assert not target.exists(), "a typo'd path must never be created"


def test_seeding_does_not_invent_a_missing_parent_directory(capsys):
    with tempfile.TemporaryDirectory() as td:
        target = Path(td) / "nope" / "extras.json"
        assert main(["--map", str(target), "--heading", "Audit exceptions", "--line", "HP5: why"]) == 2
        capsys.readouterr()
        assert not target.parent.exists()


def test_a_missing_target_is_reported_before_the_argument_shape(capsys):
    """Probing the failure with a malformed line reported the ARGUMENT complaint first and hid the
    real cause — the operator learned about their `--line` and not about the path that did not
    exist."""
    with tempfile.TemporaryDirectory() as td:
        target = Path(td) / "gone.json"
        assert main(["--map", str(target), "--heading", "Audit exceptions",
                     "--line", "no-why-here"]) == 2
        err = capsys.readouterr().err
        assert "no such file" in err, err
        assert "states no why" not in err, err


def test_a_failed_record_leaves_no_stray_seeded_fragment_behind():
    """Seeding ran before the argument check, so a call that exited 2 on a malformed --line still
    created `{"extras": []}` on disk."""
    with tempfile.TemporaryDirectory() as td:
        target = Path(td) / "extras.json"
        assert main(["--map", str(target), "--heading", "Audit exceptions",
                     "--line", "no-why-here"]) == 2
        assert not target.exists(), "a refused call must not leave a fragment behind"
