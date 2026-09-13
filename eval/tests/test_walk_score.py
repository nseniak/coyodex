"""`coyomap-eval walk-score`: two maps against a gold table, one verdict per way in."""
from __future__ import annotations

import contextlib
import io
import json
import tempfile
from pathlib import Path

from coyomap.model import (
    Component,
    EntryPoint,
    ExtraSection,
    Flow,
    FlowStep,
    Interface,
    ProjectModel,
    UseCase,
    to_canonical_json,
)
from coyomap_eval import walk_score


def make_way_in(i: int) -> EntryPoint:
    return EntryPoint(id=f"EP{i}", kind="http-route", activation="external", component="C1",
                      trigger=f"way in {i}", source=f"a.py:{i * 10}")


def make_before() -> ProjectModel:
    """Six ways in on one interface; UC1 names EP1 and nothing else has a story."""
    m = ProjectModel(title="T", goal="G")
    m.components = [Component(id="C1", name="Doors", purpose="p", source="a.py:1")]
    m.entry_points = [make_way_in(i) for i in range(1, 7)]
    m.interfaces = [Interface(id="I1", name="Dashboard", what="w", side="ours", facing="user",
                              ways_in=[f"EP{i}" for i in range(1, 7)])]
    m.use_cases = [UseCase(id="UC1", name="Do it", actors=["R1"], entry_points=["EP1"])]
    return m


def make_after() -> ProjectModel:
    """The walk's answer: EP2 gets a NEW use case, EP3 is NAMED on UC1, a step now RUNS EP4, EP5 is
    RECORDED, EP6 is left alone."""
    m = make_before()
    m.use_cases = [UseCase(id="UC1", name="Do it", actors=["R1"], entry_points=["EP1", "EP3"]),
                   UseCase(id="UC2", name="Do the other thing", actors=["R1"], capability="CAP1",
                           entry_points=["EP2"])]
    m.flows = [Flow(uc="UC1", title="Do it", steps=[
        FlowStep(n=1, src="C1", dst="C1", phrase="handles", where="a.py:42")])]
    m.extras = [ExtraSection(heading="Unclaimed surfaces", body="EP5: a dev-only page.")]
    return m


def test_walk_score_classifies_every_gold_way_in() -> None:
    gold = {"EP2": ["new"], "EP3": ["named"], "EP4": ["run"], "EP5": ["recorded"], "EP6": ["new"]}
    s = walk_score.score(make_before(), make_after(), gold)
    assert [u.id for u in s.new_use_cases] == ["UC2"]
    assert s.new_use_cases[0].capability == "CAP1" and s.new_use_cases[0].ways_in == ["EP2"]
    assert s.named_on_existing == {"UC1": ["EP3"]}
    assert s.recorded == {"EP5": "a dev-only page."}
    got = {v.way_in: (v.outcome, v.verdict) for v in s.verdicts}
    assert got == {"EP2": ("new", "ok"), "EP3": ("named", "ok"), "EP4": ("run", "ok"),
                   "EP5": ("recorded", "ok"), "EP6": ("untouched", "untouched")}
    assert s.tally() == {"ok": 4, "wrong": 0, "untouched": 1}
    assert "6 external way(s) in" in s.coverage_line


def test_walk_score_calls_a_record_where_the_gold_wanted_a_story_wrong() -> None:
    s = walk_score.score(make_before(), make_after(), {"EP5": ["new", "named"]})
    assert s.verdicts[0].verdict == "wrong" and s.verdicts[0].outcome == "recorded"
    # A whole-surface record covers its ways in; a component record too.
    after = make_after()
    after.extras = [ExtraSection(heading="Unclaimed surfaces", body="I1: an ops surface.")]
    assert walk_score.score(make_before(), after, {"EP6": ["recorded"]}).verdicts[0].verdict == "ok"


def test_walk_score_cli_exits_one_on_an_untouched_way_in() -> None:
    with tempfile.TemporaryDirectory() as td:
        t = Path(td)
        (t / "before.json").write_text(to_canonical_json(make_before()), encoding="utf-8")
        (t / "after.json").write_text(to_canonical_json(make_after()), encoding="utf-8")
        (t / "gold.json").write_text(json.dumps({"EP2": ["new"], "EP6": ["new"]}), encoding="utf-8")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = walk_score.main([str(t / "before.json"), str(t / "after.json"),
                                  "--gold", str(t / "gold.json"), "--json"])
        d = json.loads(buf.getvalue())
        assert rc == 1 and d["tally"] == {"ok": 1, "wrong": 0, "untouched": 1}
        (t / "gold.json").write_text(json.dumps({"EP2": ["new"]}), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            assert walk_score.main([str(t / "before.json"), str(t / "after.json"),
                                    "--gold", str(t / "gold.json")]) == 0
        (t / "gold.json").write_text(json.dumps({"EP2": ["maybe"]}), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            assert walk_score.main([str(t / "before.json"), str(t / "after.json"),
                                    "--gold", str(t / "gold.json")]) == 2
