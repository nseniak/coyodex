"""The retro-check convention only works if both ends keep pointing at each other.

`method/retro-checks/` holds forward-declared checks: each method/tool change commits a file
stating the observable outcome it promises, and the retro (eval/retro/method.md, Step 0c) diffs
the directory across the two builds' tool commits and makes the promises come due. The mechanism
has two silent failure modes, both of the class that already bit the skills (a pointer at a
renamed doc, stale for weeks): the retro step and the convention README drift apart, or check
files stop carrying the parts the retro needs to settle them. These tests hold the shape.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CHECKS_DIR = REPO_ROOT / "method" / "retro-checks"
RETRO_METHOD = REPO_ROOT / "eval" / "retro" / "method.md"

_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}-[a-z0-9][a-z0-9-]*\.md$")


def make_retro_method_text() -> str:
    return RETRO_METHOD.read_text(encoding="utf-8")


def make_armed_checks() -> list[Path]:
    """Check files the retro would run: top level only, README excluded."""
    return sorted(
        p for p in CHECKS_DIR.glob("*.md") if p.name != "README.md"
    )


def test_retro_step_and_convention_point_at_each_other():
    """Step 0c names the README as the convention's home; both sides must exist and agree.

    The retro method is read live at retro time, weeks after the change chat is gone — a broken
    pointer here fails silently, deep in a retro, exactly like the stale skill pointers did."""
    text = make_retro_method_text()
    assert "### Step 0c" in text, "eval/retro/method.md lost its Step 0c"
    assert "method/retro-checks/README.md" in text, "Step 0c no longer names the convention README"
    assert (CHECKS_DIR / "README.md").is_file(), "the convention README Step 0c points at is gone"
    readme = (CHECKS_DIR / "README.md").read_text(encoding="utf-8")
    assert "Step 0c" in readme, "README no longer names the retro step that runs the checks"


def test_retro_report_template_carries_the_checks_section():
    """A step whose output has no slot in the report template gets skipped without a trace."""
    assert "## Retro-checks" in make_retro_method_text()


def test_retirement_directory_exists():
    """Step 0c proposes moves into verified/; the target must exist for the proposal to be real."""
    assert (CHECKS_DIR / "verified").is_dir()


def test_armed_check_files_are_dated_and_settleable():
    """A check the retro cannot settle is worse than none: it reads as coverage and proves nothing.

    Three structural demands from the README, enforced mechanically: the date-slug name (the
    range diff is the discovery mechanism, and an undated name hides when the promise was made),
    a `## Checks` section, and one regression sign per expectation — a check without a failure
    signature can only ever confirm."""
    armed = make_armed_checks()
    for path in armed:
        assert _NAME.match(path.name), f"{path.name}: not <YYYY-MM-DD>-<slug>.md"
        body = path.read_text(encoding="utf-8")
        assert "## Checks" in body, f"{path.name}: no '## Checks' section"
        n_expect = len(re.findall(r"\bexpect:", body))
        n_regression = len(re.findall(r"\bregression sign:", body))
        assert n_expect >= 1, f"{path.name}: no 'expect:' items"
        assert n_regression >= n_expect, (
            f"{path.name}: {n_expect} expect items but only {n_regression} regression signs; "
            "every expectation needs its failure signature"
        )


def test_retired_checks_say_WHY_they_stopped_running():
    """A file under `verified/` is no longer run, and it must say which of the two doors it came
    through — or a reader cannot tell a proven promise from an abandoned one.

    THERE ARE TWO DOORS, and the second was added the day a check was superseded before any build
    could prove it. Demanding a `verified in` line from a SUPERSEDED file would force a false
    claim: nothing verified it. So a retired file says either what proved it, or what replaced it.
    `2026-09-03-what-crosses-is-a-pair.md` is the case — its checks grade a field that no longer
    exists, and one of them grades as a PASS the exact shape that made coyodex's own map stop
    validating."""
    for path in sorted((CHECKS_DIR / "verified").glob("*.md")):
        body = path.read_text(encoding="utf-8")
        assert "verified in" in body or "SUPERSEDED AND NOT VERIFIED" in body, (
            f"verified/{path.name}: says neither which build proved it, nor what superseded it")
        if "SUPERSEDED AND NOT VERIFIED" in body:
            assert "Its successor is" in body or "carried into" in body, (
                f"verified/{path.name}: superseded, but names no successor to read instead")
