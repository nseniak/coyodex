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

import re
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
def _served_map(mutate: Any) -> Iterator[str]:
    """The same server, over a map this test has changed first — for the shapes the committed
    fixture cannot hold (a step with no use case behind it, say)."""
    import json
    with tempfile.TemporaryDirectory() as td:
        folder = make_served_map(Path(td), "alpha")
        f = folder / ".coyodex" / "project-map.json"
        m = json.loads(f.read_text())
        mutate(m)
        f.write_text(json.dumps(m))
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
        # …and the LEGEND, which is an overlay pinned over the diagram. It sat clear of the old
        # Interfaces picture and covers the top-left card of the new one, so a hover in a test
        # resolved the element and then timed out on "another element intercepts pointer events".
        # Closed here rather than per test: any page whose content reaches the top-left has it.
        page.evaluate("() => { const b = document.getElementById('legendclose'); if (b) b.click(); }")
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
      * the line WRAPS: every row but the last ends in an elbow that turns down, and every row but
        the first opens with a hook coming in from above. Only the walk's final row ends in the
        arrow head, because only there does the walk actually stop.

    Read from the rendered page, not from the source: every other viewer test asserts on text."""
    with _served() as url, _page(url + "#v=hp") as page:
        _settle(page)
        counts = page.evaluate("""() => ({
            steps: document.querySelectorAll('.walk-step').length,
            boxes: document.querySelectorAll('.walk-box').length,
            hands: document.querySelectorAll('.walk-hand').length,
            elbows: document.querySelectorAll('.walk-elbow').length,
            hooks: document.querySelectorAll('.walk-hook').length,
            closed: document.querySelectorAll('.walk-box.walk-closes').length,
        })""")
        assert counts == {"steps": 14, "boxes": 11, "hands": 6,
                          "elbows": 5, "hooks": 5, "closed": 1}, counts
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
        # Per ROW, because each row draws its own line: every bullet on it, and the person naming it,
        # must share that line's centre to the decimal.
        off = page.evaluate("""() => {
            const mid = (el) => { const r = el.getBoundingClientRect(); return +(r.top + r.height / 2).toFixed(1); };
            const bad = [];
            [...document.querySelectorAll('.walk-row')].forEach((row, i) => {
                const line = +(row.querySelector('.walk-line').getBoundingClientRect().top + 21).toFixed(1);
                const dots = [...new Set([...row.querySelectorAll('.walk-dot')].map(mid))];
                // The person's BLOCK is what sits on the line: an icon with the name under it, so the
                // line runs between the two. And where two people share a row, the little "or"
                // between them sits on their ICONS, not on their block — its own middle would fall
                // in the names, and it would read as a word joining them rather than a choice.
                const one = row.querySelector('.walk-one, .walk-nowho');
                const or = row.querySelector('.walk-or');
                const ico = row.querySelector('.walk-ico');
                if (dots.length !== 1 || dots[0] !== line) bad.push({ row: i, dots, line });
                else if (one && Math.abs(mid(one) - line) > 1) bad.push({ row: i, one: mid(one), line });
                else if (or && Math.abs((or.getBoundingClientRect().top + 10.5) - mid(ico)) > 1.5) {
                    bad.push({ row: i, or: +(or.getBoundingClientRect().top + 10.5).toFixed(1),
                               ico: mid(ico) });
                }
            });
            return bad;
        }""")
        assert off == [], off
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
    rings it — the same answer a card list gives to "show in context". The walk is a stack of rows
    now, so the step is brought into view inside ITS OWN row, which is the only thing that scrolls."""
    with _served() as url, _page(url + "#v=hp&sel=hpstep:HP12") as page:
        _settle(page)
        seen = page.evaluate("""() => {
            const el = document.querySelector('.walk-step[data-step="HP12"]');
            if (!el) return null;
            const strip = el.closest('.walk-strip');
            const r = el.getBoundingClientRect(), b = strip.getBoundingClientRect();
            return { onScreen: r.left >= b.left - 1 && r.right <= b.right + 1,
                     row: strip.querySelectorAll('.walk-step').length > 0 };
        }""")
        assert seen == {"onScreen": True, "row": True}, seen
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
            const all = [...document.querySelectorAll('.walk-box')];
            const heights = [...new Set(all.map((b) => Math.round(b.getBoundingClientRect().height)))];
            const px = (el, k) => parseFloat(getComputedStyle(el).getPropertyValue(k)) || 0;
            // Pairs WITHIN a row: two boxes of one person, so the line must cross the gap. Across
            // rows there is nothing to bridge — the row break is the hand-over.
            const gaps = [];
            for (const row of document.querySelectorAll('.walk-row')) {
                const boxes = [...row.querySelectorAll('.walk-box')];
                for (let i = 0; i < boxes.length - 1; i++) {
                    const a = boxes[i].querySelector('.walk-line').getBoundingClientRect();
                    const b = boxes[i + 1].querySelector('.walk-line').getBoundingClientRect();
                    const reach = -px(boxes[i], '--walk-r') - px(boxes[i + 1], '--walk-l');
                    gaps.push({ joined: reach >= b.left - a.right,
                                closes: boxes[i].classList.contains('walk-closes') });
                }
            }
            // …and every part of the wrap must sit ON the line it continues, never near it.
            const off = [];
            document.querySelectorAll('.walk-row').forEach((row, i) => {
                const bs = [...row.querySelectorAll('.walk-box')];
                const f = bs[0].querySelector('.walk-line').getBoundingClientRect();
                const l = bs[bs.length - 1].querySelector('.walk-line').getBoundingClientRect();
                const left = f.left + px(bs[0], '--walk-l');
                const right = l.right + px(bs[bs.length - 1], '--walk-r');
                const mid = f.top + 21;
                const el = row.querySelector('.walk-elbow'), hk = row.querySelector('.walk-hook');
                if (el) {
                    const b = el.getBoundingClientRect();
                    if (Math.abs(b.left - right) > 1 || Math.abs(b.top + 1.5 - mid) > 1) off.push(i);
                }
                if (hk) {
                    const b = hk.getBoundingClientRect();
                    if (Math.abs(b.left + 1.5 - left) > 1.5 || Math.abs(b.bottom - 1.5 - mid) > 1) off.push(i);
                }
            });
            return { heights, gaps, off,
                     rows: document.querySelectorAll('.walk-row').length,
                     arrows: all.filter((b) => b.classList.contains('walk-closes')).length };
        }""")
        assert len(seen["heights"]) == 1, seen["heights"]
        # inside a row the line always crosses, and no box but the last of a row closes
        assert all(g["joined"] and not g["closes"] for g in seen["gaps"]), seen
        # ONE arrow head on the whole board: the walk stops once, at the end
        assert seen["arrows"] == 1 and seen["rows"] == 6, seen
        # every elbow starts at its row's line end, every hook lands on its row's line start
        assert seen["off"] == [], seen
        assert not page.js_errors, page.js_errors


def test_a_board_that_scrolls_sideways_shades_the_edge_there_is_more_on() -> None:
    """A board cut off at the window edge looks like a board that ENDS there. Each edge wears a
    shade, and each is shown only while there is something that way to scroll to — a shade that is
    always there says "more" at the end of the board too, which is a lie about the one thing it
    exists to answer. Walk the board from one end to the other and read which shade is up."""
    with _served() as url, _page(url + "#v=hp") as page:
        # Narrow, so a row HAS something to scroll to. At a wide window every row of the fixture's
        # walk fits, which is the point of the row break — and then there is no shadow to look at.
        page.set_viewport_size({"width": 700, "height": 720})
        _settle(page)
        seen = page.evaluate("""async () => {
            // the WIDEST row: the only one with anything to scroll to
            const board = [...document.querySelectorAll('.walk-strip')]
                .reduce((a, b) => (b.scrollWidth - b.clientWidth > a.scrollWidth - a.clientWidth ? b : a));
            const wrap = board.parentElement;
            // the shades are synced on the board's own scroll event, which is asynchronous
            const settle = () => new Promise((r) => setTimeout(r, 80));
            const at = () => ({ l: wrap.classList.contains('hfade-on-l'),
                                r: wrap.classList.contains('hfade-on-r') });
            const out = { wrapped: wrap.classList.contains('hfade-wrap'),
                          shades: wrap.querySelectorAll('.hfade').length, start: at() };
            board.scrollLeft = Math.round((board.scrollWidth - board.clientWidth) / 2);
            await settle();
            out.middle = at();
            board.scrollLeft = board.scrollWidth;
            await settle();
            out.end = at();
            return out;
        }""")
        assert seen == {"wrapped": True, "shades": 2,
                        "start": {"l": False, "r": True},
                        "middle": {"l": True, "r": True},
                        "end": {"l": True, "r": False}}, seen
        assert not page.js_errors, page.js_errors


def test_a_lane_with_a_fixed_left_part_shadows_it_instead_of_fading_it() -> None:
    """The journey rail's gutter names the two lanes and stays put while the boxes slide under it.
    Fading it out would fade the one thing that is not moving, so it gets no fade over it: it casts
    a shadow to its right instead, and only once the lane has been scrolled. Same signal, drawn the
    way a fixed thing should be."""
    with _served() as url, _page(url + "#v=actor&act=Org%20admin") as page:
        _settle(page)
        seen = page.evaluate("""async () => {
            const board = document.querySelector('.journey-board');
            const wrap = board.parentElement;
            const gutter = board.querySelector('.journey-gutter');
            const read = () => ({
                onL: wrap.classList.contains('hfade-on-l'),
                leftFade: getComputedStyle(wrap.querySelector('.hfade-l')).display,
                shadow: getComputedStyle(gutter).boxShadow !== 'none',
            });
            const out = { start: read() };
            board.scrollLeft = 600;
            await new Promise((r) => setTimeout(r, 80));
            out.scrolled = read();
            return out;
        }""")
        # the left fade is off on this lane at BOTH ends: the gutter answers for that edge
        assert seen["start"] == {"onL": False, "leftFade": "none", "shadow": False}, seen
        assert seen["scrolled"] == {"onL": True, "leftFade": "none", "shadow": True}, seen
        assert not page.js_errors, page.js_errors


def test_the_walk_keeps_the_step_a_link_named_in_the_address() -> None:
    """A link that names one step must still name it once you are there. The board rings the step and
    then the address was rewritten from the page's own state, which for a page with no diagram was
    "nothing selected" — so the address fell back to a bare `#v=hp`, and the link you copied, or a
    reload, came back to step 1. The step is claimed BEFORE the chrome writes the address."""
    with _served() as url, _page(url + "#v=hp&sel=hpstep:HP12") as page:
        _settle(page)
        assert page.evaluate("() => location.hash") == "#v=hp&sel=hpstep%3AHP12"
        page.reload()
        page.wait_for_selector("#crumb")
        _settle(page)
        seen = page.evaluate("""() => {
            const el = document.querySelector('.walk-step[data-step="HP12"]');
            const b = el.closest('.walk-strip');
            const r = el.getBoundingClientRect(), br = b.getBoundingClientRect();
            return { hash: location.hash, inside: r.left >= br.left - 1 && r.right <= br.right + 1 };
        }""")
        assert seen == {"hash": "#v=hp&sel=hpstep%3AHP12", "inside": True}, seen
        assert not page.js_errors, page.js_errors


def test_back_from_a_step_returns_to_that_step_not_to_the_start_of_the_walk() -> None:
    """Clicking a step and pressing Back put the reader at the start of the walk, screens away from
    where they were, because nothing remembered the place. The step you leave by is now the step you
    come back to: the address names it, and the page arrives scrolled to it."""
    with _served() as url, _page(url + "#v=hp") as page:
        _settle(page)
        left_by = page.evaluate("""() => {
            // a step near the END of the walk, so coming back to the top of the page would miss it
            const all = [...document.querySelectorAll('.walk-step[data-uc]')];
            const el = all[all.length - 1];
            el.scrollIntoView({ block: 'center' });
            el.click();
            return el.dataset.step;
        }""")
        _settle(page)
        assert page.evaluate("() => location.hash").startswith("#v=usecase")
        page.go_back()
        _settle(page)
        seen = page.evaluate("""(step) => {
            const el = document.querySelector(`.walk-step[data-step="${step}"]`);
            const wrap = document.querySelector('.usecases-wrap');
            const r = el.getBoundingClientRect(), w = wrap.getBoundingClientRect();
            return { hash: location.hash, scrolled: wrap.scrollTop > 0,
                     onScreen: r.top >= w.top - 1 && r.bottom <= w.bottom + 1 };
        }""", left_by)
        assert seen == {"hash": "#v=hp&sel=hpstep%3A" + left_by,
                        "scrolled": True, "onScreen": True}, seen
        assert not page.js_errors, page.js_errors


def test_the_walk_offers_no_door_it_cannot_open() -> None:
    """A step the map records with no use case behind it. The generator then invents a driver called
    "Actor", whom the map never declares. Both were drawn as live links: the person to a page that
    knows nothing about them, the step to "Not in this map" under a title promising to open
    something. Both are still DRAWN — the walk really does pass through them — and neither is a
    door. The guard is the one `journeyDriverLabelHtml` has always applied."""
    def strip_the_last_step(m: Any) -> None:
        m["happy_path"][-1]["uc"] = None

    with _served_map(strip_the_last_step) as url, _page(url + "#v=hp") as page:
        _settle(page)
        seen = page.evaluate("""() => {
            const person = document.querySelector('.walk-one-dead');
            const step = document.querySelector('.walk-step-dead');
            return {
                personDrawn: !!person, personIsButton: person ? person.tagName === 'BUTTON' : null,
                personName: person ? person.textContent.trim() : null,
                stepDrawn: !!step, stepIsDoor: step ? step.hasAttribute('data-uc') : null,
                stepTitle: step ? step.getAttribute('title') : null,
                liveButtons: document.querySelectorAll('.walk-one').length,
            };
        }""")
        assert seen["personDrawn"] and seen["personIsButton"] is False, seen
        assert seen["personName"] == "Actor", seen
        assert seen["stepDrawn"] and seen["stepIsDoor"] is False, seen
        assert seen["stepTitle"] == "This map does not say how this step works", seen
        assert not page.js_errors, page.js_errors


def test_the_arrow_head_that_turns_the_line_down_is_centred_on_it() -> None:
    """An absolutely positioned child is placed against its parent's PADDING box, and the elbow's
    padding box stops inside its own 3px right border. Offset from there, the head sat 3px left of
    the line it ends, which at a 4x zoom is plainly a head beside a line rather than on it.

    Measured, not eyeballed: the head's own centre against the border's own middle, on every elbow."""
    with _served() as url, _page(url + "#v=hp") as page:
        _settle(page)
        off = page.evaluate("""() => {
            const bad = [];
            [...document.querySelectorAll('.walk-elbow')].forEach((el, i) => {
                const b = el.getBoundingClientRect();
                const cs = getComputedStyle(el, '::after');
                const lineX = b.right - 1.5;                       // the 3px border's own middle
                const headRight = (b.right - 3) - parseFloat(cs.right);   // …from the PADDING box
                const headCx = headRight
                    - (parseFloat(cs.borderLeftWidth) + parseFloat(cs.borderRightWidth)) / 2;
                if (Math.abs(headCx - lineX) > 0.6) {
                    bad.push({ i, headCx: +headCx.toFixed(2), lineX: +lineX.toFixed(2) });
                }
            });
            return bad;
        }""")
        assert off == [], off
        assert page.evaluate("() => document.querySelectorAll('.walk-elbow').length") == 5
        assert not page.js_errors, page.js_errors


def test_the_walk_counts_the_features_it_touches_out_of_all_there_are() -> None:
    """The walk is usually a selection, and the page should say so. It cannot say so in WORDS: on the
    four maps this viewer reads it is 9 of 10 and 8 of 10, but on the other two it is 7 of 7, every
    feature there is — and on any small product the walk naturally covers everything. "A subset of
    the features" would be a plain lie on half of them.

    So it is a count, and the "of N" appears only when there is something left out. The fixture's
    walk misses one feature, so it says "of"; a map whose walk reaches them all says only how many.
    """
    with _served() as url, _page(url + "#v=hp") as page:
        _settle(page)
        label = page.evaluate("() => document.querySelector('.block-lbl').textContent")
        assert re.fullmatch(r"14 steps, \d+ of \d+ features", label), label
        touched, total = (int(x) for x in re.findall(r"(\d+) of (\d+)", label)[0])
        assert touched < total, label
        assert not page.js_errors, page.js_errors


# ── the surface's SHAPE, and who is on the far side ─────────────────────────────────────────────
# The committed fixture records no interface at all, which is the empty case the tab is hidden on.
# Both screens below need one, so they mutate the map — the shapes the fixture cannot hold.

def _with_interface(kind: str) -> Any:
    """A `theirs` surface of `kind`, standing on the dependency UC1's walk already steps at (`D4`).

    That step is what the derivation reads on a `theirs` surface — and reads ONLY when the kind
    means a person goes there, which is the whole point of gating it."""
    def mutate(m: dict) -> None:
        m["interfaces"] = [{
            "id": "I1", "name": "Google sign-in", "what": "Where a person proves who they are.",
            "side": "theirs", "facing": "user", "kind": kind,
            "carries": [{"direction": "out", "what": "a sign-in request", "elements": []}],
        }]
        for d in m["deps"]:
            if d["id"] == "D4":
                d["interfaces"] = ["I1"]
    return mutate


def test_a_surface_card_says_what_shape_it_is() -> None:
    """"Show me every API this product exposes" was a question a reader answered off the surface's
    NAME, and no tool could answer at all.

    The picture answers it with a GLYPH now, not the word: eleven kinds is more than a reader learns,
    so eight drawings cover them and three groupings are genuinely one thing. `hosted-screen` and
    `screen` are both a browser window, which is what this asserts — the kind is not lost by being
    folded, it is drawn. The WORD is still on the surface's own page, where there is room to read."""
    for kind in ("hosted-screen", "screen"):
        with _served_map(_with_interface(kind)) as url, _page(url + "#v=interfaces") as page:
            _settle(page)
            box = page.evaluate("""() => {
                const b = document.querySelector('.ifd-box[data-iface="I1"]');
                const g = b.querySelector('.ifd-head .ifd-glyph');
                return { d: [...g.querySelectorAll('rect, path')].map(e =>
                            e.getAttribute('d') || 'rect').join('|'),
                         w: g.getBoundingClientRect().width };
            }""")
            # the browser-window drawing: a rounded rect with one line across it, near the top
            assert box["d"] == "rect|M1.5 6.5h15", box
            assert 12 <= box["w"] <= 18, box       # sized by CSS, not by the tag's attributes
            assert not page.js_errors, page.js_errors


def test_a_surface_a_person_goes_to_draws_the_person_and_one_we_merely_call_draws_nobody() -> None:
    """The same surface, the same walk, the same dependency — only the KIND differs, and it decides
    whether anyone is on the far side. Ungated, the join puts human roles behind a server.

    And the empty answer is a SENTENCE, not a blank: "nobody goes there" is the correct answer for a
    crash reporter, and a page that just stopped would read as unfinished."""
    with _served_map(_with_interface("hosted-screen")) as url, \
            _page(url + "#v=interfaces&iface=I1") as page:
        _settle(page)
        names = page.evaluate(
            "() => [...document.querySelectorAll('.ecard[data-key] .ecard-name')]"
            ".map(e => e.textContent)")
        assert "Org creator" in names, names
        assert not page.js_errors, page.js_errors
    with _served_map(_with_interface("api")) as url, \
            _page(url + "#v=interfaces&iface=I1") as page:
        _settle(page)
        names = page.evaluate(
            "() => [...document.querySelectorAll('.ecard[data-key] .ecard-name')]"
            ".map(e => e.textContent)")
        assert names == [], names
        text = page.evaluate("() => document.querySelector('.usecases-wrap').textContent")
        assert "no person goes there" in text, text
        assert not page.js_errors, page.js_errors


def _two_sided_interfaces() -> Any:
    """Two surfaces, one on each shore, one of them carrying BOTH directions.

    Both-direction is the common case, not a corner: 4 of coyodex's 11 surfaces and 7 of mcpolis's
    12 carry two crossings, and two wires joining the same pair of edges have the same midpoint."""
    def mutate(m: dict) -> None:
        m["interfaces"] = [
            {"id": "I1", "name": "The dashboard", "what": "Screens a person signs in to.",
             "side": "ours", "facing": "user", "kind": "screen",
             "carries": [{"direction": "in", "what": "what the person asks for", "elements": []},
                         {"direction": "out", "what": "the page they get back", "elements": []}]},
            {"id": "I2", "name": "Crash reporting", "what": "Where a crash is reported.",
             "side": "theirs", "facing": "operator", "kind": "api",
             "carries": [{"direction": "out", "what": "a crash report", "elements": []}]},
        ]
        for d in m["deps"]:
            if d["id"] == "D4":
                d["interfaces"] = ["I2"]
    return mutate


def test_the_interfaces_picture_draws_one_wire_per_direction_each_surface_carries() -> None:
    """The COUNT is the shape's honesty: a surface that answers as well as asks draws two wires, and
    a their-surface is not always an exit — the cut is by side, the arrows carry direction."""
    with _served_map(_two_sided_interfaces()) as url, _page(url + "#v=interfaces") as page:
        _settle(page)
        wires = page.evaluate("""() => {
            const p = [...document.querySelectorAll('#ifdstage path[data-iface]')];
            const out = {};
            for (const x of p) (out[x.dataset.iface] = out[x.dataset.iface] || []).push(1);
            return out;
        }""")
        # I1 carries both directions and draws two; I2 carries one and draws ONE. A wire is drawn
        # only where something crosses — drawing both and letting the empty label fall away leaves a
        # line a reader can hover and get nothing from, and half the surfaces on both live maps
        # carry one direction only.
        assert len(wires["I1"]) == 2, wires
        assert len(wires["I2"]) == 1, wires
        assert not page.js_errors, page.js_errors


def test_hovering_a_surface_lights_its_own_wires_and_separates_its_two_labels() -> None:
    """At rest every wire is grey and unlabelled. Hover makes ONE surface the picture — and its two
    crossings join the same pair of edges, so without a nudge the two labels land exactly on top of
    each other and the reader sees one sentence where the map holds two."""
    with _served_map(_two_sided_interfaces()) as url, _page(url + "#v=interfaces") as page:
        _settle(page)
        page.hover('.ifd-box[data-iface="I1"]')
        page.wait_for_timeout(250)
        shown = page.evaluate("""() => {
            const on = [...document.querySelectorAll('.ifd-elabel.ifd-lab-on')];
            return {
                hot: [...document.querySelectorAll('#ifdstage path.ifd-hot')]
                        .map(p => p.dataset.iface),
                cold: [...document.querySelectorAll('#ifdstage path.ifd-cold')]
                        .map(p => p.dataset.iface),
                labels: on.map(l => ({ text: l.textContent, top: l.offsetTop })),
            };
        }""")
        assert set(shown["hot"]) == {"I1"}, shown
        assert set(shown["cold"]) == {"I2"}, shown
        assert len(shown["labels"]) == 2, shown
        tops = sorted(l["top"] for l in shown["labels"])
        assert tops[1] - tops[0] >= 18, shown          # two sentences, two lines
        assert not page.js_errors, page.js_errors


def test_the_picture_fits_without_pushing_the_page_sideways() -> None:
    """Five columns against the Features page's three. Five columns of CARDS would be about 1900px
    and would not fit 1440, which is why the product is a narrow spine and the two outer columns
    hold chips. MEASURED, never eyeballed."""
    with _served_map(_two_sided_interfaces()) as url, _page(url + "#v=interfaces") as page:
        for width in (1440, 1280):
            page.set_viewport_size({"width": width, "height": 900})
            _settle(page)
            m = page.evaluate("""() => {
                const st = document.getElementById('ifdstage');
                const wrap = st.parentElement;
                return { doc: document.documentElement.scrollWidth, win: window.innerWidth,
                         overflows: wrap.scrollWidth > wrap.clientWidth };
            }""")
            assert m["doc"] <= m["win"], (width, m)
            assert not m["overflows"], (width, m)
        assert not page.js_errors, page.js_errors


def test_a_surface_with_no_kind_still_draws_a_box() -> None:
    """Degrading: no `kind` recorded means the default outline and no word. The picture still
    draws — it is never allowed to invent a shape the map did not author."""
    def mutate(m: dict) -> None:
        _two_sided_interfaces()(m)
        m["interfaces"][0]["kind"] = ""
    with _served_map(mutate) as url, _page(url + "#v=interfaces") as page:
        _settle(page)
        got = page.evaluate("""() => {
            const b = document.querySelector('.ifd-box[data-iface="I1"]');
            return { name: b.querySelector('.ifd-name').textContent,
                     glyphs: b.querySelectorAll('.ifd-head .ifd-glyph').length };
        }""")
        # It draws, it is named, and it takes the FALLBACK glyph rather than none: a box with a hole
        # where every sibling has a mark reads as a rendering fault, not as a missing field.
        assert got["name"] == "The dashboard", got
        assert got["glyphs"] == 1, got
        assert not page.js_errors, page.js_errors


def test_the_picture_is_the_list_and_there_is_no_second_copy_under_it() -> None:
    """This REPLACES a test that asserted the opposite, and the reason it flipped is the picture.

    There were two card lists under it, "Our surfaces" and "Their surfaces", on the rule that a
    picture is not a replacement for a list you can read down. That rule was right about the old
    picture, whose boxes were a name and two words. It is not right about this one: the boxes ARE
    cards, in a stated order, carrying the same sentence the list carried. Keeping both drew every
    surface twice on one page — and those two headings were the last place the words "our surface"
    and "their surface" survived."""
    with _served_map(_two_sided_interfaces()) as url, _page(url + "#v=interfaces") as page:
        _settle(page)
        got = page.evaluate("""() => ({
            boxes: [...document.querySelectorAll('.ifd-box')].map(
                b => b.querySelector('.ifd-name').textContent),
            sentences: [...document.querySelectorAll('.ifd-box .ifd-what')].map(e => e.textContent),
            cards: document.querySelectorAll('.usecases-wrap .ecard[data-key]').length,
            text: document.querySelector('.usecases-wrap').textContent,
        })""")
        assert sorted(got["boxes"]) == ["Crash reporting", "The dashboard"], got
        assert "Screens a person signs in to." in got["sentences"], got
        assert got["cards"] == 0, got                       # no second copy
        assert "Our surfaces" not in got["text"], got       # and the words are gone with it
        assert "Their surfaces" not in got["text"], got
        assert not page.js_errors, page.js_errors


def _both_shores_carry_people_and_a_pipe() -> Any:
    """One surface on EACH shore that has both a person standing at it and a pipe it is reached
    through — the shape the picture used to draw only half of.

    The person on the `ours` surface arrives through a DOOR (`R1 → I1`), which is the arm that fills
    the far side on most surfaces and the reason this shape is now common: 9 chips across the two
    live maps were derived and undrawn. The person on the `theirs` surface comes from the walk
    reaching `D4`, gated on a kind that means a person goes there."""
    def mutate(m: dict) -> None:
        m["interfaces"] = [
            {"id": "I1", "name": "The dashboard", "what": "Screens a person signs in to.",
             "side": "ours", "facing": "user", "kind": "screen",
             "carries": [{"direction": "in", "what": "what the person asks for", "elements": []}]},
            {"id": "I2", "name": "Google sign-in", "what": "Where a person proves who they are.",
             "side": "theirs", "facing": "user", "kind": "hosted-screen",
             "carries": [{"direction": "out", "what": "a sign-in request", "elements": []}]},
        ]
        for d in m["deps"]:
            if d["id"] == "D4":
                d["interfaces"] = ["I2"]
            if d["id"] == "D6":
                d["interfaces"] = ["I1"]
        for f in m["flows"]:
            if f["uc"] == "UC1":
                f["steps"].insert(0, {"n": 0, "src": "R1", "dst": "I1",
                                      "phrase": "opens the dashboard", "note": "", "where": None,
                                      "no_call_site": False, "subflow": None})
    return mutate


def test_the_picture_draws_the_people_and_the_pipe_on_both_shores() -> None:
    """The two shores were drawing DIFFERENT HALVES of the same fact: `ours` drew the people and
    dropped the pipes, `theirs` drew the pipes and dropped the people. Nine things the two live maps
    state went undrawn — coyodex's Agent skill reaches three agent hosts, its GitHub and code-editor
    handoffs each have a reader standing at them, mcpolis mails through a service and sends three
    people to Google. Every one of them was already on the surface's own page.

    Both now live INSIDE the card, so the two halves cannot drift apart again — there is no longer a
    per-shore builder to get wrong. The ORDER is still asserted, and it is the same on both shores:
    the far side is the answer, the pipe is only how it is reached, so the person is never second."""
    with _served_map(_both_shores_carry_people_and_a_pipe()) as url, \
            _page(url + "#v=interfaces") as page:
        _settle(page)
        cells = page.evaluate("""() => {
            const out = {};
            for (const b of document.querySelectorAll('.ifd-box')) {
                out[b.dataset.iface] = [
                    ...[...b.querySelectorAll('.ifd-chip-actor')].map(e => 'who:' + e.textContent),
                    ...[...b.querySelectorAll('.ifd-prov')].map(e => 'pipe:' + e.textContent)];
            }
            return out;
        }""")
        assert cells["I1"] == ["who:Org creator", "pipe:SMTP / Google Workspace"], cells
        assert cells["I2"] == ["who:Org creator", "who:Team member",
                               "pipe:Google OAuth IdP"], cells
        assert not page.js_errors, page.js_errors


# ── the map inspector (Ctrl+Shift) ───────────────────────────────────────────────────────────────
# These are browser tests because the whole feature IS browser behaviour: which DOM element the
# cursor is over, which listener sees the click first, and what the popup then says. A source-text
# assertion could not tell any of that apart from a resolver that silently finds nothing.

_INSPECT_JS = """
(sel) => {
  const el = document.querySelector(sel);
  if (!el) return { error: 'no element for ' + sel };
  const opts = { bubbles: true, cancelable: true, view: window, ctrlKey: true, shiftKey: true };
  el.dispatchEvent(new MouseEvent('mousemove', opts));
  el.dispatchEvent(new MouseEvent('click', opts));
  return { ok: true };
}
"""
_READ_POP_JS = """
() => {
  const pop = document.querySelector('.insp-pop');
  if (!pop || pop.hidden) return { open: false };
  return {
    open: true,
    kind: pop.querySelector('.insp-kind').textContent,
    path: pop.querySelector('.insp-path').textContent.replace('project-map.json › ', ''),
    body: pop.textContent,
    refs: [...pop.querySelectorAll('.insp-ref')].map((r) => r.textContent),
  };
}
"""


def _inspect(page: Any, selector: str) -> dict:
    """Ctrl+Shift+click `selector` and read the popup. The wait covers the stored map's own fetch:
    the first such click of a session lands before /api/rawmap has answered, and the handler holds
    the click until it does."""
    started = page.evaluate(_INSPECT_JS, selector)
    assert "error" not in started, started
    page.wait_for_timeout(700)
    return dict(page.evaluate(_READ_POP_JS))


def test_the_inspector_answers_with_the_record_the_map_stores() -> None:
    """The whole point: the popup says WHICH slot of the stored file drew this box, and what that
    slot holds — not what the view bundle made of it."""
    with _served() as url, _page(url + "#v=usecases") as page:
        _settle(page)
        got = _inspect(page, "article.story-card.story-feature[data-sfeat]")
        assert got["open"], got
        assert got["kind"] == "feature", got
        assert re.fullmatch(r"capabilities\[\d+\]", got["path"]), got
        assert '"id"' in got["body"] and '"purpose"' in got["body"], got
        assert not page.js_errors, page.js_errors


def test_a_click_without_both_keys_is_an_ordinary_click() -> None:
    """The inspector overlaps two bindings that already exist (⌘ multi-selects, Shift frames), so
    the one thing it must never do is change what a plain click means."""
    with _served() as url, _page(url + "#v=usecases") as page:
        _settle(page)
        page.click("article.story-card.story-feature[data-sfeat] button")
        _settle(page)
        pop = page.evaluate(_READ_POP_JS)
        assert not pop["open"], pop
        assert "Features" in _crumb(page), _crumb(page)
        assert not page.js_errors, page.js_errors


def test_the_smaller_things_answer_too_not_just_the_boxes() -> None:
    """A step of the happy path and a way in are drawn from records of their own, and neither carries
    an id on screen: the step is found by its id attribute, the way in by its POSITION in one
    component's list. Both were invisible to a resolver that only knew about drawn boxes."""
    with _served() as url, _page(url + "#v=hp") as page:
        _settle(page)
        step = _inspect(page, ".walk-step[data-step]")
        assert step["open"] and step["kind"] == "happy-path step", step
        assert re.fullmatch(r"happy_path\[\d+\]", step["path"]), step
        assert not page.js_errors, page.js_errors
    # A component's own details page is where a way in is drawn ("Triggered by"); the info pane
    # beside a diagram carries only the card.
    with _served() as url, _page(url + "#v=element&id=C1") as page:
        _settle(page)
        way = _inspect(page, ".tb-ep[data-ep-idx]")
        assert way["open"] and way["kind"] == "way in", way
        assert re.fullmatch(r"entry_points\[\d+\]", way["path"]), way
        assert not page.js_errors, page.js_errors


def test_an_id_inside_a_record_opens_that_record_and_back_returns() -> None:
    """A record is mostly ids pointing at other records, and reading one by hand meant scrolling the
    file. Following one must also be undoable, or the popup is a one-way trip."""
    with _served() as url, _page(url + "#v=hp") as page:
        _settle(page)
        first = _inspect(page, ".walk-step[data-step]")
        assert first["open"], first
        moved = page.evaluate("""
            () => {
              const pop = document.querySelector('.insp-pop');
              const r = [...pop.querySelectorAll('.insp-ref')].find((x) => /^UC\\d+$/.test(x.textContent));
              if (!r) return { error: 'no use-case id in the step record' };
              r.click();
              return { ok: true };
            }""")
        assert "error" not in moved, moved
        page.wait_for_timeout(300)
        after = dict(page.evaluate(_READ_POP_JS))
        assert after["kind"] == "use case", after
        assert re.fullmatch(r"use_cases\[\d+\]", after["path"]), after
        page.click(".insp-pop .insp-back")
        page.wait_for_timeout(300)
        back = dict(page.evaluate(_READ_POP_JS))
        assert back["path"] == first["path"], (back, first)
        assert not page.js_errors, page.js_errors


def test_a_click_on_something_the_map_does_not_store_says_so() -> None:
    """Silence is the one answer a debug tool must not give: it makes a resolver gap and a broken
    tool look identical. A miss reports what the click landed on instead."""
    with _served() as url, _page(url + "#v=usecases") as page:
        _settle(page)
        got = _inspect(page, "#crumb")
        assert got["open"], got
        assert got["kind"] == "not stored", got
        assert got["path"] == "—", got
        assert "Nothing under the cursor" in got["body"], got
        assert not page.js_errors, page.js_errors


def test_the_stored_map_is_served_byte_for_byte() -> None:
    """The path the popup prints is only useful if it names a slot in the file on disk, which needs
    the endpoint to hand over that file rather than a re-serialisation of the model."""
    import urllib.request
    with _served() as url:
        with urllib.request.urlopen(url + "api/rawmap") as r:
            body = r.read()
        assert body == _FIXTURE_MAP.read_bytes()


def test_the_secondary_click_opens_it_too_and_no_native_menu_appears() -> None:
    """macOS makes Control-click the SECONDARY click: the system turns it into a context menu and no
    ordinary click is ever produced. Held to `click` alone, the gesture opened the browser's own menu
    and nothing else — on the one platform this tool is written for."""
    with _served() as url, _page(url + "#v=usecases") as page:
        _settle(page)
        prevented = page.evaluate("""
            () => {
              const el = document.querySelector('article.story-card.story-feature[data-sfeat]');
              const e = new MouseEvent('contextmenu',
                { bubbles: true, cancelable: true, view: window, ctrlKey: true, shiftKey: true });
              el.dispatchEvent(e);
              return e.defaultPrevented;
            }""")
        assert prevented, "the native context menu was left to open"
        page.wait_for_timeout(700)
        got = dict(page.evaluate(_READ_POP_JS))
        assert got["open"] and got["kind"] == "feature", got
        assert not page.js_errors, page.js_errors


def test_while_the_two_keys_are_held_the_page_itself_is_deaf() -> None:
    """The gesture overlaps two live bindings (⌘ multi-selects on ctrlKey, the arrow handlers on
    shiftKey), and panning, wheel-zoom, hover and the double-click drill all went on running under
    the inspector. Held, the page must receive nothing; released, it must receive everything."""
    probe = """
        () => {
          window.__seen = [];
          for (const t of ['mousedown', 'mouseup', 'click', 'dblclick', 'contextmenu', 'wheel'])
            document.addEventListener(t, (e) => window.__seen.push(t), false);
        }"""
    fire = """
        (held) => {
          const el = document.querySelector('article.story-card.story-feature[data-sfeat]');
          const mods = held ? { ctrlKey: true, shiftKey: true } : {};
          const o = { bubbles: true, cancelable: true, view: window, ...mods };
          for (const t of ['mousedown', 'mouseup', 'dblclick', 'contextmenu'])
            el.dispatchEvent(new MouseEvent(t, o));
          el.dispatchEvent(new WheelEvent('wheel', { ...o, deltaY: -240 }));
          return window.__seen.slice();
        }"""
    with _served() as url, _page(url + "#v=usecases") as page:
        _settle(page)
        page.evaluate(probe)
        held = page.evaluate(fire, True)
        assert held == [], held
        page.evaluate("() => { window.__seen = []; }")
        free = page.evaluate(fire, False)
        assert set(free) == {"mousedown", "mouseup", "dblclick", "contextmenu", "wheel"}, free
        assert not page.js_errors, page.js_errors


def test_an_actors_page_names_the_surfaces_they_stand_at_and_says_which_shore() -> None:
    """The far-side derivation read BACKWARDS. A surface's page already named the people at it, and
    no page named the surfaces for a person — the link was one-way for as long as the actors column
    was empty.

    The two headings are not one sentence turned round: the actor COMES TO our surface, and the
    product SENDS THEM to theirs. Google sign-in is where mcpolis sends three roles, and calling that
    "where they reach the product" would be false."""
    with _served_map(_both_shores_carry_people_and_a_pipe()) as url, \
            _page(url + "#v=actor&act=Org creator") as page:
        _settle(page)
        seen = page.evaluate("""() => {
            const out = [];
            for (const el of document.querySelectorAll(
                    '.usecases-wrap .card-group-head, .usecases-wrap .ecard[data-key]')) {
                out.push(el.classList.contains('card-group-head')
                    ? 'HEAD:' + el.textContent
                    : 'card:' + el.querySelector('.ecard-name').textContent);
            }
            return out;
        }""")
        assert seen == ["HEAD:Where they reach the product", "card:The dashboard",
                        "HEAD:Where the product sends them", "card:Google sign-in"], seen
        assert not page.js_errors, page.js_errors


def test_an_actor_at_no_surface_says_so_and_the_products_own_work_says_why() -> None:
    """Two different facts, two different sentences. An actor the map puts at no surface is a plain
    absence; the product's OWN scheduled work — a service role that is internal — is inside the
    product and crosses nothing, which is a complete answer. One sentence for both would report the
    timer as an unfinished map."""
    def outsider(m: dict) -> None:
        _both_shores_carry_people_and_a_pipe()(m)
    with _served_map(outsider) as url, _page(url + "#v=actor&act=Superadmin") as page:
        _settle(page)
        text = page.evaluate("() => document.querySelector('.usecases-wrap').textContent")
        assert "No surface in this map has this actor standing at it." in text, text
        assert not page.js_errors, page.js_errors

    def inside(m: dict) -> None:
        _both_shores_carry_people_and_a_pipe()(m)
        for r in m["roles"]:
            if r["id"] == "R5":
                r["kind"], r["audience"] = "service", "internal"
    with _served_map(inside) as url, _page(url + "#v=actor&act=Superadmin") as page:
        _settle(page)
        text = page.evaluate("() => document.querySelector('.usecases-wrap').textContent")
        assert "crosses no surface" in text, text
        assert not page.js_errors, page.js_errors


def _walk_ordered_interfaces() -> Any:
    """Four surfaces the walk reaches in a KNOWN order, and two it never reaches.

    UC1 is the fixture's first happy-path use case and its flow steps at `D4`; UC2 comes later.

    THE IDS DISAGREE WITH THE WALK ON PURPOSE. "First" is `I9` and "Second" is `I2`, so a build that
    lost the walk order and fell back to sorting by id would put them the other way round. Without
    that the test passes against no ordering at all — which it did, until a mutation said so."""
    def mutate(m: dict) -> None:
        m["interfaces"] = [
            {"id": "I3", "name": "Late and staffy", "what": "Never on the walk, operator-facing.",
             "side": "ours", "facing": "operator", "kind": "screen",
             "carries": [{"direction": "in", "what": "a", "elements": []}]},
            {"id": "I2", "name": "Second", "what": "Reached later on the walk.",
             "side": "ours", "facing": "user", "kind": "screen",
             "carries": [{"direction": "in", "what": "b", "elements": []}]},
            {"id": "I5", "name": "Never", "what": "Never on the walk, user-facing.",
             "side": "ours", "facing": "user", "kind": "screen",
             "carries": [{"direction": "in", "what": "c", "elements": []}]},
            {"id": "I9", "name": "First", "what": "Reached at the start of the walk.",
             "side": "ours", "facing": "user", "kind": "screen",
             "carries": [{"direction": "in", "what": "d", "elements": []}]},
            {"id": "I4", "name": "Theirs on the walk", "what": "Stands on the dep UC1 steps at.",
             "side": "theirs", "facing": "user", "kind": "api",
             "carries": [{"direction": "out", "what": "e", "elements": []}]},
        ]
        for d in m["deps"]:
            if d["id"] == "D4":
                d["interfaces"] = ["I4"]
        door = {"phrase": "opens it", "note": "", "where": None, "no_call_site": False,
                "subflow": None}
        for f in m["flows"]:
            if f["uc"] == "UC1":
                f["steps"].insert(0, dict(door, n=0, src="R1", dst="I9"))
            if f["uc"] == "UC2":
                f["steps"].insert(0, dict(door, n=0, src="R2", dst="I2"))
    return mutate


def test_the_picture_reads_down_in_the_order_the_walk_touches_each_surface() -> None:
    """The same rule the Features page's column uses, applied to surfaces: first touch on the happy
    path, unbroken, then the ones the walk never reaches in a block after it.

    On MCP Hero that reads as the product's own story — a prospect reads the public website, signs up
    on the dashboard, a member uses the gateway, an operator the console — and it puts the one staff
    surface last WITHOUT a staff rule, because the operator's steps are the end of the walk. The
    untouched block keeps user-before-staff, since the walk has nothing to say about a surface it
    never reaches."""
    with _served_map(_walk_ordered_interfaces()) as url, _page(url + "#v=interfaces") as page:
        _settle(page)
        got = page.evaluate("""() => ({
            ours: [...document.querySelectorAll('.ifd-col-ours .ifd-name')].map(e => e.textContent),
            theirs: [...document.querySelectorAll('.ifd-col-theirs .ifd-name')].map(e => e.textContent),
        })""")
        assert got["ours"] == ["First", "Second", "Never", "Late and staffy"], got
        assert got["theirs"] == ["Theirs on the walk"], got
        assert not page.js_errors, page.js_errors


def test_the_opening_move_is_the_upper_wire_and_the_labels_carry_no_direction_word() -> None:
    """Who speaks first is drawn, not written. A WAY IN is an address something outside invokes, so a
    surface holding one is opened from outside and its `in` is the upper wire; a surface holding none
    is one the product reaches for, so its `out` is.

    The two labels carry NO direction word: each rides its own wire and that wire has an arrowhead,
    so "in" and "out" restated in text what the reader could already see. That makes the ORDER the
    only thing saying which is which, which is why it is asserted rather than assumed.

    They must also never touch. The picture once drew ONE curve and its exact reverse, so a reader
    saw a single line with a head at each end and both sentences landed on one spot."""
    def mutate(m: dict) -> None:
        both = [{"direction": "in", "what": "what the caller asks for", "elements": []},
                {"direction": "out", "what": "the answer it gets back", "elements": []}]
        # The committed fixture's entry points carry no ids, so one is named here. A way in has to be
        # a REAL entry point of the map: `ways_in` is what the derivation reads, and a made-up id
        # would make this test pass against a surface the map does not actually hold a way into.
        m["entry_points"][0]["id"] = "EP1"
        m["interfaces"] = [
            {"id": "I1", "name": "Opened from outside", "what": "It holds a way in.",
             "side": "ours", "facing": "user", "kind": "screen", "ways_in": ["EP1"],
             "carries": list(both)},
            {"id": "I2", "name": "We reach for it", "what": "It holds none.",
             "side": "theirs", "facing": "user", "kind": "api", "carries": list(both)},
        ]
    with _served_map(mutate) as url, _page(url + "#v=interfaces") as page:
        _settle(page)
        got = page.evaluate("""() => {
            const out = {};
            for (const id of ['I1', 'I2']) {
                const ls = [...document.querySelectorAll('.ifd-elabel')]
                    .filter(l => l.dataset.iface === id)
                    .sort((a, b) => parseFloat(a.style.top) - parseFloat(b.style.top));
                ls.forEach(l => { l.style.visibility = 'hidden'; l.style.display = 'block'; });
                const box = ls.map(l => ({ t: parseFloat(l.style.top) - l.offsetHeight / 2,
                                           b: parseFloat(l.style.top) + l.offsetHeight / 2 }));
                ls.forEach(l => { l.style.display = ''; l.style.visibility = ''; });
                out[id] = { texts: ls.map(l => l.textContent),
                            gap: Math.round(box[1].t - box[0].b) };
            }
            return out;
        }""")
        # I1 holds a way in, so the incoming sentence leads. I2 holds none, so the outgoing one does.
        assert got["I1"]["texts"] == ["what the caller asks for", "the answer it gets back"], got
        assert got["I2"]["texts"] == ["the answer it gets back", "what the caller asks for"], got
        for id_ in ("I1", "I2"):
            assert got[id_]["gap"] > 0, got                       # they never overlap
            for t in got[id_]["texts"]:
                assert "in" != t[:2] and "out" != t[:3], got      # no direction word, just the sentence
        assert not page.js_errors, page.js_errors
