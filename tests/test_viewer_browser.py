#!/usr/bin/env python3
"""The gate that can see a browser bug.

Every other viewer test reads `viewer.js` as TEXT and asserts on its source. That catches a renamed
function and a dropped line; it cannot catch a screen that renders wrong, a history step that lands
somewhere else, or a page that throws. Two real defects in the URL work shipped past 2104 green
tests and were caught only by a person driving a browser by hand.

This file closes that hole. It starts the real server on a real port, opens real Chromium, clicks,
and reads what is on screen. `playwright` is optional: without it the whole file skips, so a
Python-only environment still gets a clean run, the same bargain `test_viewer_js.py` makes with node.

Conventions: top-level test functions, no classes/fixtures (helpers are `make_*` / `_*`).
"""
from __future__ import annotations

import shutil
import tempfile
import threading
from contextlib import contextmanager
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterator

import pytest

from coyodex.viewer.recents import RecentsStore
from coyodex.viewer.serve import Handler, build_projects

_FIXTURE_MAP = Path(__file__).resolve().parent / "fixtures" / "mcpolis-project-map.json"


def make_served_map(parent: Path, name: str) -> Path:
    """`parent/name` holding the committed fixture map, ready for `build_projects`."""
    d = parent / name
    (d / ".coyodex").mkdir(parents=True)
    shutil.copy(_FIXTURE_MAP, d / ".coyodex" / "project-map.json")
    return d


@contextmanager
def _served() -> Iterator[str]:
    """The real HTTP server on an ephemeral port, yielding the map's base URL."""
    with tempfile.TemporaryDirectory() as td:
        folder = make_served_map(Path(td), "alpha")
        projects = build_projects([str(folder)])
        slug = next(iter(projects))
        Handler.store = RecentsStore()
        Handler.projects = projects
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            yield f"http://127.0.0.1:{httpd.server_address[1]}/p/{slug}/"
        finally:
            httpd.shutdown()
            httpd.server_close()


@contextmanager
def _page(url: str) -> Iterator[Any]:
    """A Chromium page on `url`, with the first-run overlay dismissed and JS errors collected.

    Errors are attached as `page.js_errors`: a viewer that throws while rendering has failed, even
    when the assertion under test would otherwise pass."""
    playwright = pytest.importorskip("playwright.sync_api", reason="playwright not installed")
    with playwright.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as exc:  # the driver is installed but the browser binary is not
            pytest.skip(f"chromium not available: {exc}")
        page = browser.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.js_errors = errors  # type: ignore[attr-defined]
        page.goto(url)
        page.wait_for_selector("#crumb")
        page.evaluate("() => { const b = document.getElementById('coachok'); if (b) b.click(); }")
        try:
            yield page
        finally:
            browser.close()


def _crumb(page: Any) -> str:
    return str(page.evaluate("() => (document.getElementById('crumb').textContent || '').trim()"))


def _settle(page: Any) -> None:
    """Let a navigation's render (and its drill animation) finish before reading the screen."""
    page.wait_for_timeout(700)


def test_a_reload_comes_back_to_the_screen_you_were_on() -> None:
    """The whole point of the change: the URL names the screen, so a reload keeps your place."""
    with _served() as url, _page(url) as page:
        page.evaluate("() => document.querySelector('button[data-view=\"glossary\"]').click()")
        _settle(page)
        assert page.evaluate("() => location.hash") == "#v=glossary"
        page.reload()
        page.wait_for_selector("#crumb")
        _settle(page)
        assert page.evaluate("() => location.hash") == "#v=glossary"
        assert "Glossary" in _crumb(page)
        assert not page.js_errors, page.js_errors


def test_back_after_an_address_bar_paste_walks_the_real_screens() -> None:
    """The review's exact repro. A pasted hash starts a NEW stack without a page load, so every entry
    behind it belongs to the stack just thrown away. While the entry stamp was keyed on the page load
    those stale indexes still matched: Back rendered whatever now sat at that index, and the URL was
    then rewritten over the entry, losing the screen it named for the life of the tab.

    Read the steps as a walk: Tests, then Glossary, then Features. Before the fix it was Tests, then
    Subsystems, then Tests."""
    with _served() as url, _page(url) as page:
        page.evaluate("() => document.querySelector('button[data-view=\"glossary\"]').click()")
        _settle(page)
        page.evaluate("() => { location.hash = '#v=tests'; }")
        _settle(page)
        page.evaluate("() => document.querySelector('button[data-view=\"container\"]').click()")
        _settle(page)

        walked = []
        for _ in range(3):
            page.go_back()
            _settle(page)
            walked.append(page.evaluate("() => location.hash"))
        assert walked == ["#v=tests", "#v=glossary", "#v=usecases"], walked
        assert "Features" in _crumb(page)
        assert not page.js_errors, page.js_errors


@pytest.mark.parametrize("fragment", [
    "#v=data&store=%29",              # a paren: `'#' + id` was not a valid selector, querySelector threw
    "#v=capability&cap=constructor",  # an inherited property name read as a lookup HIT
    "#v=__proto__",                   # …the same, as the view kind itself
    "#v=container&sel=__proto__",     # …and as a selection key, which was then CALLED
    "#v=subsystem&sid=S99",           # an ordinary stale id: the map was rebuilt under the link
])
def test_a_crafted_or_stale_link_still_draws_a_page_with_a_trail(fragment: str) -> None:
    """A link is text a reader can type or keep from an older map. Whatever it says, the viewer owes
    them a page that says where they are. Each fragment below aborted the render before the trail was
    drawn; opened cold, the page had no breadcrumb and no lit tab at all."""
    with _served() as url, _page(url + fragment) as page:
        _settle(page)
        assert _crumb(page), f"no trail at all for {fragment}"
        assert page.evaluate("() => !!document.querySelector('button[data-view].active')"), fragment
        assert not page.js_errors, page.js_errors


def test_a_stale_link_shows_no_internal_id_on_screen() -> None:
    """The viewer shows names; ids are internal. Every id-to-name lookup fell back to the id, which a
    stale link reaches — an adversarial review found 8 fragments that printed one into the trail."""
    with _served() as url, _page(url) as page:
        for fragment, gone in (("#v=subsystem&sid=S99", "S99"),
                               ("#v=element&id=C999", "C999"),
                               ("#v=usecase&uc=UC99", "UC99")):
            page.evaluate("(h) => { location.hash = h; }", fragment)
            _settle(page)
            crumb = _crumb(page)
            assert gone not in crumb, f"{fragment} put the id in the trail: {crumb!r}"
            assert "Not in this map" in crumb, crumb
        assert not page.js_errors, page.js_errors


def test_the_happy_path_draws_one_line_broken_at_every_change_of_person() -> None:
    """The Happy Path board, which replaced a sequence diagram Mermaid shrank to 9.5px of step text
    on this very map. Three things make it the walk rather than a list of steps:

      * a BOX is a run of consecutive steps sharing one feature AND one person, so the fixture's 14
        steps draw 11 boxes;
      * the line BREAKS wherever the person changes, and that person stands in the break — 6 of
        them here, one per hand-over;
      * an arrow head closes a box only when somebody else is about to take over, so a box that
        merely changes feature runs on unbroken into the next.

    Read from the rendered page, not from the source: every other viewer test asserts on text."""
    with _served() as url, _page(url + "#v=hp") as page:
        _settle(page)
        counts = page.evaluate("""() => ({
            steps: document.querySelectorAll('.walk-step').length,
            boxes: document.querySelectorAll('.walk-box').length,
            hands: document.querySelectorAll('.walk-hand').length,
            closed: document.querySelectorAll('.walk-box.walk-closes').length,
        })""")
        assert counts == {"steps": 14, "boxes": 11, "hands": 6, "closed": 6}, counts
        # …and no sequence diagram is left anywhere on the page.
        assert page.evaluate("() => !document.querySelector('#diagram svg .actor-line')")
        assert not page.js_errors, page.js_errors


def test_every_bullet_of_the_walk_sits_on_the_line() -> None:
    """A BUTTON centres its own content box, and as a stretched flex item every step is as tall as
    the tallest — which put the bullet of a step with a short title 8px below the line it is meant to
    sit on. Measured, never eyeballed: the bullet's centre, the line's centre and the centre of the
    person's glyph must all be one number."""
    with _served() as url, _page(url + "#v=hp") as page:
        _settle(page)
        mids = page.evaluate("""() => {
            const mid = (el) => { const r = el.getBoundingClientRect(); return +(r.top + r.height / 2).toFixed(1); };
            const line = document.querySelector('.walk-line').getBoundingClientRect();
            return {
              dots: [...new Set([...document.querySelectorAll('.walk-dot')].map(mid))],
              icons: [...new Set([...document.querySelectorAll('.walk-ico')].map(mid))],
              line: +(line.top + 21).toFixed(1),
            };
        }""")
        assert mids["dots"] == [mids["line"]], mids
        assert mids["icons"] == [mids["line"]], mids
        assert not page.js_errors, page.js_errors


def test_the_walk_has_three_doors_and_each_opens_that_thing_s_own_page() -> None:
    """A step opens the flow of the use case it realizes — the same flow the Features tab drills to,
    so a use case keeps ONE home. A feature's name opens that feature's page, a person's name theirs.
    """
    with _served() as url, _page(url + "#v=hp") as page:
        _settle(page)
        page.evaluate("() => document.querySelector('.walk-step').click()")
        _settle(page)
        assert page.evaluate("() => location.hash").startswith("#v=usecase&uc="), \
            page.evaluate("() => location.hash")

        page.evaluate("() => { location.hash = '#v=hp'; }")
        _settle(page)
        page.evaluate("() => document.querySelector('.walk-fname').click()")
        _settle(page)
        assert page.evaluate("() => location.hash").startswith("#v=capability&cap=")

        page.evaluate("() => { location.hash = '#v=hp'; }")
        _settle(page)
        page.evaluate("() => document.querySelector('.walk-one').click()")
        _settle(page)
        assert page.evaluate("() => location.hash").startswith("#v=actor&act=")
        assert not page.js_errors, page.js_errors


def test_a_link_naming_one_step_arrives_scrolled_to_it() -> None:
    """A station on an actor's rail, a feature's rail and a story arrow's label all navigate here
    naming one step. The board has no scene to select into, so it scrolls that step into view and
    rings it — the same answer a card list gives to "show in context". Step 12 of the fixture's 14
    is well off the right edge on arrival, so a board that ignored the name would leave it there."""
    with _served() as url, _page(url + "#v=hp&sel=hpstep:HP12") as page:
        _settle(page)
        seen = page.evaluate("""() => {
            const el = document.querySelector('.walk-step[data-step="HP12"]');
            if (!el) return null;
            const r = el.getBoundingClientRect(), b = document.querySelector('.walk-board').getBoundingClientRect();
            return { scrolled: document.querySelector('.walk-board').scrollLeft > 0,
                     inside: r.left >= b.left - 1 && r.right <= b.right + 1 };
        }""")
        assert seen == {"scrolled": True, "inside": True}, seen
        assert not page.js_errors, page.js_errors


def test_every_feature_box_is_the_same_height_and_the_line_bridges_the_gap() -> None:
    """Two claims the eye makes about the board, and neither is safe to eyeball.

    Every box is as tall as the tallest step title in the WHOLE walk, not as tall as its own: a
    short feature's tint used to end above its neighbours and read as a stub. And the 14px gap the
    boxes now stand apart does not cut the line — a box whose person carries on into the next
    reaches half that gap on each side, so the two read as one line running through them. Only a
    change of PERSON breaks it, and that break carries an arrow head."""
    with _served() as url, _page(url + "#v=hp") as page:
        _settle(page)
        seen = page.evaluate("""() => {
            const boxes = [...document.querySelectorAll('.walk-box')];
            const heights = [...new Set(boxes.map((b) => Math.round(b.getBoundingClientRect().height)))];
            const px = (el, k) => parseFloat(getComputedStyle(el).getPropertyValue(k)) || 0;
            const joined = [], broken = [];
            for (let i = 0; i < boxes.length - 1; i++) {
                const a = boxes[i].querySelector('.walk-line').getBoundingClientRect();
                const b = boxes[i + 1].querySelector('.walk-line').getBoundingClientRect();
                const gap = b.left - a.right;
                const reach = -px(boxes[i], '--walk-r') - px(boxes[i + 1], '--walk-l');
                (reach >= gap ? joined : broken).push(boxes[i].classList.contains('walk-closes'));
            }
            return { heights, joined, broken,
                     arrows: boxes.filter((b) => b.classList.contains('walk-closes')).length };
        }""")
        assert len(seen["heights"]) == 1, seen["heights"]
        # a joined pair is never one that closes; a broken pair always is, and wears the arrow head
        assert not any(seen["joined"]), seen
        assert all(seen["broken"]), seen
        assert seen["arrows"] == 6, seen
        assert not page.js_errors, page.js_errors
