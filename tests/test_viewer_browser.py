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
            # `FEATURES` is module-scoped inside viewer.js and unreachable from `evaluate`, so the
            # STORED kind is read back off the served bundle — same origin, so a plain fetch does it.
            box = page.evaluate("""async () => {
                const b = document.querySelector('.ifd-box[data-iface="I1"]');
                const g = b.querySelector('.ifd-head .ifd-glyph');
                const v = await (await fetch('api/view')).json();
                return { d: [...g.querySelectorAll('rect, path')].map(e =>
                            e.getAttribute('d') || 'rect').join('|'),
                         w: g.getBoundingClientRect().width,
                         word: b.querySelector('.ifd-kind').textContent,
                         kind: v.features.interfaces.find(x => x.id === 'I1').kind };
            }""")
            # the browser-window drawing: a rounded rect with one line across it, near the top
            assert box["d"] == "rect|M1.5 6.5h15", box
            assert 12 <= box["w"] <= 18, box       # sized by CSS, not by the tag's attributes
            # …and the WORD beside it, which is where the glyph stops being enough. `screen` shows as
            # WEBSITE: the map defines the kind as "anything served to a browser", so that is what it
            # has always meant, and "screen" was a word the reader had to translate. The stored kind
            # is untouched — asserted here, since a rename that reached the model would break every
            # map on disk and nothing else in the suite would notice.
            assert box["word"] == ("their website" if kind == "hosted-screen" else "website"), box
            assert box["kind"] == kind, box
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


def test_a_surface_draws_one_wire_and_wears_a_head_per_direction_it_carries() -> None:
    """ONE WIRE PER SURFACE, and the HEADS are what say which way things cross. A surface that
    answers as well as asks wears a head at each end; one that only asks wears one.

    This was two wires 20px either side of the card's middle, and the merge is only safe because the
    sentences merged with it: a double-headed line whose two labels landed on the same spot was the
    reason the pair was split in the first place."""
    with _served_map(_two_sided_interfaces()) as url, _page(url + "#v=interfaces") as page:
        _settle(page)
        wires = page.evaluate("""() => {
            const out = {};
            for (const p of document.querySelectorAll('#ifdstage path[data-iface]'))
                (out[p.dataset.iface] = out[p.dataset.iface] || []).push({
                    into: !!p.getAttribute('marker-end'),      // points AT the product: `in`
                    back: !!p.getAttribute('marker-start') });  // points back at the card: `out`
            return out;
        }""")
        # Whatever it carries, a surface is ONE line. The direction lives in the heads, never in the
        # count — a reader who sees two lines leaving one card reads two crossings, not one exchange.
        assert len(wires["I1"]) == 1, wires
        assert len(wires["I2"]) == 1, wires
        # I1 carries both directions, so both ends are pointed. I2 carries one, so ONE end is: a head
        # with no sentence behind it is a claim the reader can hover and get nothing from, and half
        # the surfaces on both live maps carry one direction only.
        assert wires["I1"][0] == {"into": True, "back": True}, wires
        assert sorted(wires["I2"][0].values()) == [False, True], wires
        assert not page.js_errors, page.js_errors


def test_hovering_a_surface_lights_its_wire_and_opens_its_one_box_of_crossings() -> None:
    """At rest every wire is grey and unlabelled. Hover makes ONE surface the picture — and its
    crossings arrive as ONE box holding a row per direction, not as a box per direction. The pair
    used to stack to 206px against a 109px card on the live map; merged, every sentence is still
    there and the stack is gone."""
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
                labels: on.length,
                rows: on.flatMap(l => [...l.querySelectorAll('.ifd-elabel-row')]
                                        .map(r => r.dataset.dir)),
            };
        }""")
        assert set(shown["hot"]) == {"I1"}, shown
        assert set(shown["cold"]) == {"I2"}, shown
        assert shown["labels"] == 1, shown             # one box…
        assert sorted(shown["rows"]) == ["in", "out"], shown   # …holding both directions
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
        # A WAY IN on the dashboard, because that is what a screen people come to HAS. `opens` is
        # derived from it, and `opens` is what the actor page cuts its two groups by — a surface with
        # no address anything outside can invoke is one the product starts the exchange at.
        m["entry_points"] = (m.get("entry_points") or []) + [
            {"id": "EP900", "kind": "HTTP route", "trigger": "`GET /dashboard`",
             "source": "backend/src/mcpolis/entrypoints/app.py:1", "component": "C1"}]
        m["interfaces"] = [
            {"id": "I1", "name": "The dashboard", "what": "Screens a person signs in to.",
             "side": "ours", "facing": "user", "kind": "screen", "ways_in": ["EP900"],
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


def test_the_pinned_section_bar_casts_a_shadow_only_once_it_is_attached() -> None:
    """A sticky bar looks identical pinned and at rest, so nothing on screen says whether the page is
    running underneath it or has simply ended there. A shadow falling from its grey line is what says
    it — and only while it is attached, or the shadow becomes decoration on a strip sitting in the
    flow with the page's own top edge right above it.

    A sticky element has no CSS state of its own, so the reading is geometric: the bar is attached
    exactly when it has reached its own `top: 0` and stopped travelling with the page.

    The TRANSITION is suppressed for the measurement. It is 150ms of real animation, and a headless
    run reads a frame partway through it — the shadow then computes as a transparent zero and the
    test fails on timing rather than on the rule."""
    with _served() as url, _page(url + "#v=capability&cap=CAP2") as page:
        # A SHORT WINDOW, so the page is taller than the pane and the bar can pin at all. The default
        # is tall enough to hold this feature's whole page, and a bar that never reaches its own top
        # tests nothing.
        page.set_viewport_size({"width": 1280, "height": 520})
        _settle(page)
        out = page.evaluate("""() => {
            const w = document.querySelector('.usecases-wrap');
            const nav = w.querySelector('.tab-index');
            if (!nav) return {noBar: true};
            nav.style.transition = 'none';
            const read = () => ({stuck: nav.classList.contains('tab-index-stuck'),
                                 shadow: getComputedStyle(nav).boxShadow});
            w.scrollTop = 0; w.dispatchEvent(new Event('scroll'));
            const rest = read();
            // How far this page must scroll before the bar reaches its own top at all.
            const reach = nav.getBoundingClientRect().top - w.getBoundingClientRect().top;
            w.scrollTop = w.scrollHeight; w.dispatchEvent(new Event('scroll'));
            const stuck = read();
            w.scrollTop = 0; w.dispatchEvent(new Event('scroll'));
            const back = read();
            nav.style.transition = '';
            return {rest, stuck, back, reach, room: w.scrollHeight - w.clientHeight};
        }""")
        assert not out.get("noBar"), out
        assert out["room"] > out["reach"], ("the page must be tall enough to pin the bar at all", out)
        assert out["rest"] == {"stuck": False, "shadow": "none"}, out
        assert out["stuck"]["stuck"] and out["stuck"]["shadow"] != "none", out
        # …and it is cast DOWNWARD only: a positive y with a negative spread, so it never haloes the
        # bar's own sides, where it would read as a floating panel rather than an edge.
        assert "0px 5px" in out["stuck"]["shadow"] and "-6px" in out["stuck"]["shadow"], out
        assert out["back"] == {"stuck": False, "shadow": "none"}, ("…and it lets go", out)
        assert not page.js_errors, page.js_errors


def test_an_item_pages_sections_each_say_what_they_are_and_what_is_in_them() -> None:
    """A page about one element is a stack of sections, and each one has to answer three questions on
    its own: what is this, how much of it is there, and what am I looking at. The actor page answered
    none of them. Its board carried the actor's own figure and name — which the hero one line above
    had just drawn — and nothing said the boxes were USE CASES, or which use cases were in there and
    which were not.

    Three parts, and none of them is decoration: the heading names the section, the count states its
    size, and the sentence says what is in it. A pinned chip bar indexes them, so a reader knows what
    the page holds before scrolling and can jump between the parts.

    NO HEIGHT CAP anywhere. The picture inside a section is drawn as tall as it needs to be, so
    nothing scrolls vertically inside itself; the page scrolls, once. Sideways is a different matter —
    the board is genuinely wider than any window, and that scroll stays."""
    with _served_map(_both_shores_carry_people_and_a_pipe()) as url, \
            _page(url + "#v=actor&act=Org creator") as page:
        _settle(page)
        secs = page.evaluate("""() => [...document.querySelectorAll('.item-sec')].map((s) => ({
            title: s.querySelector('.item-sec-title').firstChild.textContent.trim(),
            count: s.querySelector('.item-sec-n').textContent,
            note: s.querySelector('.item-sec-note').textContent.slice(0, 24),
        }))""")
        assert [s["title"] for s in secs] == ["Use cases", "Interfaces"], secs
        assert all(s["note"] and s["count"] != "" for s in secs), secs
        # The bar states the same numbers the headings do — one page, one set of counts.
        chips = page.evaluate("""() => [...document.querySelectorAll('.tab-index-chip')].map((c) => ({
            title: c.firstChild.textContent.trim(),
            count: c.querySelector('.tab-index-n').textContent }))""")
        assert chips == [{"title": s["title"], "count": s["count"]} for s in secs], (chips, secs)
        # …and the actor's name is drawn ONCE in the page body, by the hero.
        names = page.evaluate(
            "() => [...document.querySelectorAll('#diagram .page-hero-subject,"
            " #diagram .journey-actorname')].map((e) => e.textContent)")
        assert names == ["Org creator"], names
        # NOTHING SCROLLS VERTICALLY inside a section — not the frame, not anything in it.
        tall = page.evaluate("""() => {
            const bad = [];
            for (const f of document.querySelectorAll('.item-sec-frame'))
              for (const el of [f, ...f.querySelectorAll('*')])
                if (el.scrollHeight > el.clientHeight + 1
                    && ['auto', 'scroll'].includes(getComputedStyle(el).overflowY))
                  bad.push(el.className);
            return bad;
        }""")
        assert tall == [], tall
        # The hero's rule went with them: the page is a stack of announced sections now, and the
        # SPACE above the name is what sets the block off from the trail instead.
        hero = page.evaluate(
            "() => { const cs = getComputedStyle(document.querySelector('#diagram .page-hero'));"
            "  return {b: cs.borderBottomWidth, p: parseFloat(cs.paddingTop)}; }")
        assert hero["b"] == "0px" and hero["p"] >= 14, hero
        # …and the GREY LINE is between the sections, with room on both sides of it. Never above the
        # first: the chip bar draws its own line under itself and a second one below it is two rules
        # for one boundary.
        rules = page.evaluate("""() => [...document.querySelectorAll('.item-sec')].map((s) => {
            const cs = getComputedStyle(s);
            return {top: parseFloat(cs.borderTopWidth), pad: parseFloat(cs.paddingTop),
                    below: parseFloat(cs.marginBottom)};
        })""")
        assert rules[0]["top"] == 0, rules
        assert all(r["top"] == 1 for r in rules[1:]), rules
        assert all(r["below"] >= 24 for r in rules[:-1]), rules
        # …and the air around that line is DELIBERATELY UNEVEN. Below it sits exactly the gap the chip
        # bar leaves under its own grey line, so every grey line on the page stands the same distance
        # above the heading it introduces. Even air on both sides was drawn first and read as a rule
        # floating between two blocks, belonging to neither.
        gaps = page.evaluate("""() => {
            const w = document.querySelector('.usecases-wrap');
            const nav = w.querySelector('.tab-index');
            const secs = [...w.querySelectorAll('.item-sec')];
            const top = (s) => s.querySelector('.item-sec-title').getBoundingClientRect().top;
            return {bar: Math.round(top(secs[0]) - nav.getBoundingClientRect().bottom),
                    sep: Math.round(top(secs[1]) - secs[1].getBoundingClientRect().top),
                    above: Math.round(secs[1].getBoundingClientRect().top
                                      - secs[0].getBoundingClientRect().bottom)};
        }""")
        assert abs(gaps["sep"] - gaps["bar"]) <= 2, gaps
        assert gaps["above"] >= gaps["sep"] * 2, gaps
        # A CHIP LANDS YOU ON THE TITLE IT NAMES. The section was left out of the rule that clears the
        # pinned bar, so clicking a chip put its heading under the very bar that was clicked.
        landed = page.evaluate("""() => {
            const w = document.querySelector('.usecases-wrap');
            const nav = w.querySelector('.tab-index');
            const chip = nav.querySelector('.tab-index-chip');
            const sec = w.querySelector('#' + chip.dataset.target);
            w.scrollTop = w.scrollHeight;
            sec.scrollIntoView({block: 'start'});
            const t = sec.querySelector('.item-sec-title').getBoundingClientRect();
            return {title: t.top, bar: nav.getBoundingClientRect().bottom};
        }""")
        assert landed["title"] >= landed["bar"], landed
        assert not page.js_errors, page.js_errors


def test_an_actors_page_names_the_surfaces_they_stand_at_and_says_which_shore() -> None:
    """The far-side derivation read BACKWARDS. A surface's page already named the people at it, and
    no page named the surfaces for a person — the link was one-way for as long as the actors column
    was empty.

    The two headings are not one sentence turned round: the actor COMES TO our surface, and the
    product SENDS THEM to theirs. Google sign-in is where mcpolis sends three roles, and calling that
    "where they reach the product" would be false.

    It is a PICTURE, read left to right: what crosses, the surface it crosses at, and what this actor
    does there. The two groups are sub-headings inside the middle column.

    THE GROUPS CUT BY DIRECTION, not by whose surface it is. `side` says who defines a surface and
    the headings claim which way the actor goes, and those are different questions: the fixture's
    dashboard is ours AND is where the creator comes in, while Google sign-in is theirs AND is where
    the product starts the exchange. On the live maps the difference was drawn wrong on 4 of 35
    rows — every one of them Outgoing email, our surface, with no way in and one outbound sentence."""
    with _served_map(_both_shores_carry_people_and_a_pipe()) as url, \
            _page(url + "#v=actor&act=Org creator") as page:
        _settle(page)
        seen = page.evaluate("""() => [...document.querySelectorAll(
                '#asfstage .asf-shore, #asfstage .ifd-box .ifd-name')]
            .map((el) => (el.classList.contains('asf-shore') ? 'SHORE:' : 'surface:')
                + el.textContent)""")
        assert seen == ["SHORE:Where they reach the product", "surface:The dashboard",
                        "SHORE:Where the product reaches them", "surface:Google sign-in"], seen
        # The reader's OWN actor is marked on every card; the other people at the same surface stay
        # drawn, because "who else stands here" is context the card should keep.
        marked = page.evaluate(
            "() => [...document.querySelectorAll('.ifd-chip-me')].map((c) => c.textContent.trim())")
        assert marked == ["Org creator", "Org creator"], marked
        assert not page.js_errors, page.js_errors


def test_a_surface_names_the_features_that_arrive_at_an_actor_not_only_the_ones_they_drive() -> None:
    """WHO DRIVES IT AND WHO IS AT THE DOOR ARE DIFFERENT QUESTIONS, and the far-side list is built
    from the DOOR. Asking only "does this use case name my actor" therefore reported "not stated" on
    a surface the map has plenty to say about: the actor is on that surface BECAUSE of a door, and
    the features had to be found by the same rule that put them there.

    MCP Hero is the real case. Outgoing email carries one use case, "Warn a member that a server
    sign-in expired" — its actor is the UPKEEP JOB, the product's own timer, and two of its steps are
    `Outgoing email -> Organization admin` and `Outgoing email -> Team member`. The admin never
    drives that story; it arrives at them. Their page said nothing about the one thing that surface
    does for them.

    Here the same shape: a use case the ORG ADMIN drives, whose walk hands out through the dashboard
    to the Org creator, who drives none of it."""
    def mutate(m: dict) -> None:
        m["interfaces"] = [
            {"id": "I1", "name": "The dashboard", "what": "Screens a person signs in to.",
             "side": "ours", "facing": "user", "kind": "screen",
             "carries": [{"direction": "out", "what": "what the product tells them",
                          "elements": []}]},
        ]
        # UC2 is the ORG ADMIN's story. Its walk is made to hand out through the dashboard to the ORG
        # CREATOR, who drives none of it — so the only thing that can put the creator on that surface,
        # or name a feature for them there, is the door.
        flow = next(f for f in m["flows"] if f["uc"] == "UC2")
        last = flow["steps"][-1]
        step = lambda n, src, dst, phrase: {
            "n": n, "src": src, "dst": dst, "phrase": phrase, "note": "", "where": None,
            "no_call_site": False, "subflow": None}
        flow["steps"].append(step(len(flow["steps"]) + 1, last["src"], "I1", "writes the notice out"))
        flow["steps"].append(step(len(flow["steps"]) + 1, "I1", "R1", "reaches the org creator"))
    with _served_map(mutate) as url, _page(url + "#v=actor&act=Org creator") as page:
        _settle(page)
        seen = page.evaluate("""() => {
            const cell = document.querySelector('#asfstage .asf-featcell[data-iface="I1"]');
            const box = cell && cell.querySelector('.asf-feats');
            return box ? [...box.querySelectorAll('.asf-feat span')].map((f) => f.textContent)
                       : 'NONE: ' + (cell ? cell.textContent.trim() : 'no cell at all');
        }""")
        assert isinstance(seen, list) and seen, seen
        # …and the wire is drawn, because there is now an answer for it to land on.
        wires = page.evaluate(
            "() => document.querySelectorAll('#asfstage path[data-iface=I1]').length")
        assert wires == 2, wires
        assert not page.js_errors, page.js_errors


def test_an_actors_surfaces_picture_lines_each_one_up_with_what_they_reach_there() -> None:
    """The third column answers "and what do I get through it?", per surface — so its box has to sit
    at its own surface's height. Only a shared grid row can promise that: two independently stacked
    columns line up at the top and drift apart at the first card whose sentence wraps to a different
    number of lines. Measured, not eyeballed: the two middles must meet, because the wire between
    them is drawn from one to the other.

    The features are THIS actor's, joined through their own use cases — the surface's own feature
    list would answer a different question, every feature ANYONE reaches there."""
    with _served_map(_both_shores_carry_people_and_a_pipe()) as url, \
            _page(url + "#v=actor&act=Org creator") as page:
        _settle(page)
        rows = page.evaluate("""() => {
            const st = document.querySelector('#asfstage');
            return [...st.querySelectorAll('.ifd-box')].map((b) => {
              const cell = st.querySelector(
                  '.asf-featcell[data-iface="' + CSS.escape(b.dataset.iface) + '"]');
              const box = cell && cell.querySelector('.asf-feats');
              return {
                surface: b.querySelector('.ifd-name').textContent,
                cardMid: Math.round(b.offsetTop + b.offsetHeight / 2),
                featMid: box ? Math.round(box.offsetTop + box.offsetHeight / 2) : null,
                feats: box ? [...box.querySelectorAll('.asf-feat span')].map((f) => f.textContent)
                           : cell.textContent.trim(),
              };
            });
        }""")
        assert rows, rows
        for r in rows:
            if r["featMid"] is not None:
                assert abs(r["cardMid"] - r["featMid"]) <= 1, r
            assert r["feats"], r
        # …and every wire the picture draws belongs to a surface: this actor to it, and it to its
        # features. A surface the map can name no feature for draws the second wire nowhere.
        wired = page.evaluate("""() => {
            const st = document.querySelector('#asfstage');
            const per = {};
            for (const p of st.querySelectorAll('svg.ifd-wires path[data-iface]'))
              per[p.dataset.iface] = (per[p.dataset.iface] || 0) + 1;
            const named = {};
            for (const c of st.querySelectorAll('.asf-featcell'))
              named[c.dataset.iface] = !!c.querySelector('.asf-feats');
            return Object.keys(per).map((k) => [per[k], named[k]]);
        }""")
        assert wired and all(n == (c == 2) for c, n in wired), wired
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


def test_the_opening_move_leads_the_box_and_says_it_is_the_opening_move() -> None:
    """Who speaks first is written now, not drawn. A WAY IN is an address something outside invokes,
    so a surface holding one is opened from outside and its `in` row leads; a surface holding none is
    one the product reaches for, so its `out` row does.

    EACH ROW CARRIES ITS DIRECTION WORD. The two sentences used to ride two wires with one arrowhead
    each, so the word would have restated what the reader could see. One merged wire has a head at
    BOTH ends and cannot say which sentences belong to which, so `in` and `out` move into the text —
    the same two words the surface's own page sets its crossings table in.

    AND THE ORDER IS MARKED `first` / `then`. Order alone does not read as order: the picture used to
    say it with POSITION — the opening move was the upper wire — and two rows of equal weight in one
    box read as a table of facts, not as a sequence."""
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
                    .filter(l => l.dataset.iface === id);
                const rows = [...ls[0].querySelectorAll('.ifd-elabel-row')];
                out[id] = { boxes: ls.length,
                            dirs: rows.map(r => r.dataset.dir),
                            words: rows.map(r => r.querySelector('.ifd-elabel-dir').textContent),
                            ords: rows.map(r => { const o = r.querySelector('.ifd-elabel-ord');
                                                  return o ? o.textContent : null; }),
                            texts: rows.map(r => [...r.querySelectorAll('.ifd-what-line')]
                                                   .map(e => e.textContent)) };
            }
            return out;
        }""")
        for id_ in ("I1", "I2"):
            assert got[id_]["boxes"] == 1, got            # one box, whatever it carries
            assert got[id_]["ords"] == ["first", "then"], got
        # I1 holds a way in, so the incoming row leads. I2 holds none, so the outgoing one does.
        assert got["I1"]["dirs"] == ["in", "out"], got
        assert got["I2"]["dirs"] == ["out", "in"], got
        # …and the word is really ON each row, not merely implied by its position.
        assert got["I1"]["words"] == ["in", "out"], got
        assert got["I2"]["words"] == ["out", "in"], got
        assert got["I1"]["texts"] == [["what the caller asks for"],
                                      ["the answer it gets back"]], got
        assert not page.js_errors, page.js_errors


def test_a_surface_carrying_one_direction_is_not_marked_first() -> None:
    """`first` is a promise that something follows it. A surface with one direction has nothing to
    follow, so its single row carries the direction word alone."""
    def mutate(m: dict) -> None:
        m["interfaces"] = [
            {"id": "I1", "name": "One way only", "what": "It only reports.", "side": "theirs",
             "facing": "operator", "kind": "api",
             "carries": [{"direction": "out", "what": "what went wrong", "elements": []}]},
        ]
    with _served_map(mutate) as url, _page(url + "#v=interfaces") as page:
        _settle(page)
        got = page.evaluate("""() => {
            const l = document.querySelector('.ifd-elabel');
            return { rows: l.querySelectorAll('.ifd-elabel-row').length,
                     ords: l.querySelectorAll('.ifd-elabel-ord').length,
                     dirs: [...l.querySelectorAll('.ifd-elabel-dir')].map(e => e.textContent) };
        }""")
        assert got == {"rows": 1, "ords": 0, "dirs": ["out"]}, got
        assert not page.js_errors, page.js_errors


def test_a_surfaces_wire_reaches_its_card_and_lands_on_the_product() -> None:
    """Both ends of the line are asserted, because both used to be wrong in their own way.

    AT THE CARD: no gap. A line that stops short of the thing it points at is a line the reader has
    to join up themselves. 14px of clearance was tried and Nitsan reversed it twice. What made the
    clearance seem necessary was the BRACKET — the picked card's 2px indigo border closing a
    surface's TWO wires into one line bent twice — and a surface draws ONE wire now, so the bracket
    cannot form at all.

    AT THE PRODUCT: on the circle's edge, along a radius. Aimed anywhere else the lines would cross
    inside the shape, and a hub with lines crossing through it stops reading as one thing."""
    def mutate(m: dict) -> None:
        m["interfaces"] = [
            {"id": "I1", "name": "Both ways", "what": "It answers as well as asks.",
             "side": "ours", "facing": "user", "kind": "screen",
             "carries": [{"direction": "in", "what": "what is asked", "elements": []},
                         {"direction": "out", "what": "what comes back", "elements": []}]},
        ]
    with _served_map(mutate) as url, _page(url + "#v=interfaces") as page:
        _settle(page)
        page.eval_on_selector('.ifd-box[data-iface="I1"]', "e => e.click()")
        page.wait_for_timeout(300)
        got = page.evaluate("""() => {
            const b = document.querySelector('.ifd-box[data-iface="I1"]');
            const right = b.offsetLeft + b.offsetWidth;
            const hub = document.getElementById('ifdhub');
            const cx = hub.offsetLeft + hub.offsetWidth / 2;
            const cy = hub.offsetTop + hub.offsetHeight / 2;
            const r = hub.offsetWidth / 2;
            const ps = [...document.querySelectorAll('#ifdstage path[data-iface="I1"]')];
            const n = ps[0].getAttribute('d').match(/-?[\\d.]+/g).map(Number);
            return { wires: ps.length,
                     startGap: Math.abs(n[0] - right),
                     endOffCircle: Math.abs(Math.hypot(n[n.length - 2] - cx,
                                                       n[n.length - 1] - cy) - r),
                     heads: [!!ps[0].getAttribute('marker-start'),
                             !!ps[0].getAttribute('marker-end')],
                     borderW: getComputedStyle(b).borderRightWidth };
        }""")
        assert got["wires"] == 1, got
        assert got["heads"] == [True, True], got     # both ways, so both ends are pointed
        # It REACHES its card — no gap to join up by eye.
        assert got["startGap"] <= 1, got
        # …and it LANDS ON the product, on the circle itself rather than short of it or inside it.
        assert got["endOffCircle"] <= 1, got
        # …and the picked card really is wearing the shared 2px edge, so the single line above is
        # leaving from inside the span that used to close the bracket.
        assert got["borderW"] == "2px", got
        assert not page.js_errors, page.js_errors


def test_a_surface_card_has_one_door_and_it_is_the_name() -> None:
    """The people and the providers are FACTS about a surface, not places to go.

    They were buttons — a chip opened that actor's page, a provider line opened that dependency in
    the tree — which put three kinds of target on one small card and made a fact read as somewhere to
    click. The same split every other card on this viewer makes: the name leaves, the body pins.

    The glossary links inside the SENTENCE are exempt and deliberately not counted: they are an
    app-wide treatment on every sentence the viewer draws, not a control this card invented."""
    with _served_map(_both_shores_carry_people_and_a_pipe()) as url, \
            _page(url + "#v=interfaces") as page:
        _settle(page)
        got = page.evaluate("""() => [...document.querySelectorAll('.ifd-box')].map(b => ({
            name: b.querySelector('.ifd-name').textContent,
            doors: [...b.querySelectorAll('button, a, [role=button]')]
                     .filter(e => !e.classList.contains('gloss-link'))
                     .map(e => e.className),
            chips: b.querySelectorAll('.ifd-chip-actor').length,
            provs: b.querySelectorAll('.ifd-prov').length,
        }))""")
        assert got, got
        for card in got:
            assert card["doors"] == ["ifd-name"], card
        # …and the facts are still drawn, so this is not passing by them having disappeared.
        assert sum(c["chips"] for c in got) > 0, got
        assert sum(c["provs"] for c in got) > 0, got
        assert not page.js_errors, page.js_errors


def test_a_story_label_stands_at_the_far_box_and_covers_nothing() -> None:
    """A stake label used to ride its wire's MIDPOINT on one nowrap line. Two faults followed: the
    pill was wider than the gutter it crossed, so it lay over the actor box and the feature box at
    both ends of its own wire; and nothing but its colour said which of a card's several arrows it
    belonged to.

    It stands at the FAR end of its wire now — beside the box that is not the one you picked, which
    is the box that identifies it — always above that end, and capped to the gutter so it wraps
    instead of reaching any card. Every card on the page is picked in turn, so all three cases are
    measured: an actor's labels land on the features, an area's on the features, and a feature's go
    out both ways at once."""
    with _served() as url, _page(url) as page:
        _settle(page)
        got = page.evaluate("""() => {
            const st = document.getElementById('storystage');
            const sb = st.getBoundingClientRect();
            const R = (e) => { const r = e.getBoundingClientRect();
                return { l: r.left - sb.left, t: r.top - sb.top,
                         r: r.right - sb.left, b: r.bottom - sb.top }; };
            const ov = (a, b) => !(a.r <= b.l || b.r <= a.l || a.b <= b.t || b.b <= a.t);
            let shown = 0, onCard = 0, onLabel = 0, notAbove = 0, offFarBox = 0;
            let wrapped = 0, atHead = 0, atTail = 0, offTop = 0;
            for (const c of st.querySelectorAll('.story-card')) {
                const key = c.dataset.sfeat ? 'sfeat' : c.dataset.sactor ? 'sactor' : 'sarea';
                c.click();
                const cards = [...st.querySelectorAll('.story-card')].map(R);
                const labs = [...st.querySelectorAll('.story-elabel.story-lab-on')];
                for (const l of labs) {
                    const r = R(l);
                    const head = l.dataset.labfrom === key;   // lit by the tail card -> far end is the head
                    const ax = parseFloat(head ? l.dataset.labtx : l.dataset.labsx);
                    const ay = parseFloat(head ? l.dataset.labty : l.dataset.labsy);
                    shown++;
                    if (head) atHead++; else atTail++;
                    if (r.b - r.t > 26) wrapped++;               // more than one line of text
                    if (r.b > ay + 0.5) notAbove++;              // never below its own end
                    // …and pinned by the edge facing that end, within a pixel.
                    if (Math.abs(head ? r.r - (ax - 8) : r.l - (ax + 8)) > 1) offFarBox++;
                    if (r.t < 0) offTop++;                       // never pushed off the stage
                    if (cards.some((k) => ov(r, k))) onCard++;
                    if (labs.some((m) => m !== l && ov(r, R(m)))) onLabel++;
                }
            }
            return { shown, onCard, onLabel, notAbove, offFarBox, wrapped, atHead, atTail, offTop };
        }""")
        assert got["shown"] > 20, got            # the fixture really does light labels
        assert got["atHead"] > 0 and got["atTail"] > 0, got   # …reaching both ways
        assert got["wrapped"] > 0, got           # …and the cap really does wrap a long one
        assert got["onCard"] == 0, got           # nothing covers a box
        assert got["onLabel"] == 0, got          # nothing covers another label
        assert got["notAbove"] == 0, got         # each sits above the end it hangs off
        assert got["offFarBox"] == 0, got        # …pinned to the box that identifies it
        assert got["offTop"] == 0, got           # …and inside the stage
        assert not page.js_errors, page.js_errors


def test_a_crossings_sentence_never_covers_the_card_it_belongs_to() -> None:
    """The label used to straddle its wire's midpoint. At 320px against a 155px gutter that put 75px
    of it over the very box the reader had just picked, hiding the name and the people.

    It now starts where its wire starts and grows AWAY from the card, overhanging the middle and the
    far column instead — both dimmed while it shows, and neither is what the reader is looking at.
    ONE box per surface, so what is asserted is that the single box clears the card on both shores."""
    def mutate(m: dict) -> None:
        # BOTH directions on BOTH shores, so the box is at its TALLEST and the test sees both growth
        # directions. `_both_shores_carry_people_and_a_pipe` carries one crossing each, which would
        # have let this pass against the smallest box the picture can draw.
        both = [{"direction": "in", "what": "what the caller asks for, at some length so the label "
                                            "is wide enough to reach the card", "elements": []},
                {"direction": "out", "what": "the answer it gets back, also long enough to matter "
                                             "when it is placed", "elements": []}]
        m["interfaces"] = [
            {"id": "I1", "name": "Ours", "what": "On our shore.", "side": "ours",
             "facing": "user", "kind": "screen", "carries": list(both)},
            {"id": "I2", "name": "Theirs", "what": "On theirs.", "side": "theirs",
             "facing": "user", "kind": "api", "carries": list(both)},
        ]
    with _served_map(mutate) as url, _page(url + "#v=interfaces") as page:
        _settle(page)
        for iid in ("I1", "I2"):     # one on each shore: they grow in opposite directions
            page.eval_on_selector(f'.ifd-box[data-iface="{iid}"]', "e => e.click()")
            page.wait_for_timeout(250)
            got = page.evaluate("""(iid) => {
                const b = document.querySelector(`.ifd-box[data-iface="${iid}"]`);
                const br = b.getBoundingClientRect();
                const ls = [...document.querySelectorAll('.ifd-elabel.ifd-lab-on')];
                return { shown: ls.length,
                         over: ls.filter(l => { const r = l.getBoundingClientRect();
                                   return r.left < br.right && r.right > br.left; }).length };
            }""", iid)
            assert got["shown"] == 1, (iid, got)
            assert got["over"] == 0, (iid, got)
        assert not page.js_errors, page.js_errors


def _crossing_naming_a_record() -> Any:
    """One surface whose two crossings name real records of the fixture map."""
    def mutate(m: dict) -> None:
        m["interfaces"] = [
            {"id": "I1", "name": "Both ways", "what": "It answers as well as asks.",
             "side": "ours", "facing": "user", "kind": "screen",
             "carries": [{"direction": "in", "what": "what is asked", "elements": ["E1"]},
                         {"direction": "out", "what": "what comes back",
                          "elements": ["E2", "E12", "E3", "E4"]}]},
        ]
    return mutate


def test_a_record_on_a_label_is_a_door_and_its_tooltip_is_what_the_record_MEANS() -> None:
    """The records a crossing carries, at the END OF ITS OWN SENTENCE and on the same line, each a
    door — the same treatment and the same three-deep cap the Features page gives a feature's records
    on its own wire labels, so one record looks and behaves the same wherever a line names it.

    THEY BELONG TO ONE CROSSING, not to a direction. `elements` sits on each crossing and the picture
    used to union them across every sentence in a direction and draw one row underneath: measured
    across the six maps, 15 of the 17 groups with more than one sentence give those sentences
    DIFFERENT records, and on 5 groups the row listed records belonging only to a sentence the cap
    had hidden — a record on screen with nothing it answered to.

    The tooltip is the record's own MEANING, not "Show X in context": that restated the underline,
    and a reader hovering a record wants to know what the record is. It comes from `cardFacts`, so
    the tooltip and the record's own card cannot say different things.

    It is THE APP'S tooltip, not the browser's `title`. A native tooltip's delay belongs to the
    browser — about a second, and nothing in the viewer can shorten it. This one is ours and waits
    half as long as an action icon's, which is asserted here by hovering and watching the clock."""
    with _served_map(_crossing_naming_a_record()) as url, _page(url + "#v=interfaces") as page:
        _settle(page)
        page.eval_on_selector('.ifd-box[data-iface="I1"]', "e => e.click()")
        page.wait_for_timeout(300)
        # KEYED ON THE DIRECTION, not on DOM order: the rows are written opener-first, and this
        # surface holds no way in, so its `out` row leads.
        got = page.evaluate("""() => {
            const out = {};
            for (const r of document.querySelectorAll('.ifd-elabel.ifd-lab-on .ifd-elabel-row')) {
                out[r.dataset.dir] = {
                    recs: [...r.querySelectorAll('.ifd-what-rec')].map(e => e.textContent),
                    titles: [...r.querySelectorAll('.ifd-what-rec')].map(
                                e => e.getAttribute('title')),
                    marks: r.querySelectorAll('.ifd-what-recs svg').length,
                    tail: r.querySelector('.ifd-what-recs').textContent };
            }
            return out;
        }""")
        one, many = got["in"], got["out"]
        assert one["recs"] == ["Organization"], one
        # four records, three drawn, and the tail SAYS the rest are there rather than dropping them
        assert many["recs"] == ["Subscription", "PlanName", "Membership"], many
        assert many["tail"].endswith("+1 more"), many
        # the DATA glyph SEPARATES the sentence from its records, so the line says what kind of thing
        # it has started naming
        assert one["marks"] == 1 and many["marks"] == 1, got
        # and NOT the browser's tooltip, whose delay the viewer cannot touch
        assert one["titles"] == [None], one

        # THE APP'S TOOLTIP, and it is QUICKER THAN AN ICON'S. The window has to straddle 125ms and
        # stop short of the 250ms an action icon waits, or the test cannot tell the two apart — a
        # first attempt checked at 260ms, which both delays pass, and a mutation to 250 sailed through
        # it. Quiet at 60ms, up by 190ms: 65ms of slack on each side of the real delay.
        # NAMED, not "the first one": the rows are written opener-first, so the first record in DOM
        # order belongs to the other row.
        page.locator(".ifd-what-rec").filter(has_text="Organization").first.hover()
        page.wait_for_timeout(60)
        assert not page.evaluate(
            "() => document.getElementById('tip').classList.contains('on')"), "tip too eager"
        page.wait_for_timeout(130)
        tip = page.evaluate("""() => ({ on: document.getElementById('tip').classList.contains('on'),
                                        text: document.getElementById('tip').textContent })""")
        assert tip["on"], tip
        assert tip["text"].startswith("A tenant"), tip
        assert not page.js_errors, page.js_errors


def test_the_pinned_surface_is_part_of_where_you_are() -> None:
    """A pinned card is not a passing highlight, it is WHERE YOU ARE: the address restates it, so a
    link carries it, and leaving the view and coming back finds the picture as you left it.

    It rides the same `sel` field the Features page's pin uses. The two pages share the field and not
    their ids, so each takes only the keys it draws — asserted here by the key in the address."""
    with _served_map(_two_sided_interfaces()) as url, _page(url + "#v=interfaces") as page:
        _settle(page)
        page.eval_on_selector('.ifd-box[data-iface="I2"]', "e => e.click()")
        page.wait_for_timeout(300)
        assert "sel=siface%3AI2" in page.evaluate("() => location.hash"), page.evaluate(
            "() => location.hash")
        # leave the view entirely, then come back
        page.evaluate("() => document.querySelector('button[data-view=\\\"glossary\\\"]').click()")
        _settle(page)
        page.evaluate("() => document.querySelector('button[data-view=\\\"interfaces\\\"]').click()")
        _settle(page)
        back = page.evaluate("""() => ({
            picked: [...document.querySelectorAll('.ifd-box.ifd-picked')].map(e => e.dataset.iface),
            labels: document.querySelectorAll('.ifd-elabel.ifd-lab-on').length })""")
        assert back["picked"] == ["I2"], back
        assert back["labels"] >= 1, back        # …and its sentences came back lit with it
        assert not page.js_errors, page.js_errors


def test_a_click_that_is_not_on_a_box_drops_the_pin() -> None:
    """One rule, and it needs saying because there was no rule at all before: the picture had no
    outside-click handler, and what looked like one working was the gutter happening to clear the
    class. The product's own shape, a column heading and the page below the diagram each left a
    surface pinned for good.

    The listener also has to be REMOVED between renders. It lives on `document`, which outlives the
    diagram, so every re-render would otherwise leave another behind — each holding a dead render's
    closure and each still writing to the address bar."""
    with _served_map(_two_sided_interfaces()) as url, _page(url + "#v=interfaces") as page:
        _settle(page)
        # every one of these is outside a box, and every one must mean the same thing
        for where in ("#ifdhub", ".ifd-col-ours .ifd-colhead", ".ifd-stage", ".usecases-wrap"):
            page.eval_on_selector('.ifd-box[data-iface="I1"]', "e => e.click()")
            page.wait_for_timeout(200)
            assert page.evaluate(
                "() => document.querySelectorAll('.ifd-box.ifd-picked').length") == 1, where
            page.eval_on_selector(where, "e => e.click()")
            page.wait_for_timeout(200)
            got = page.evaluate("""() => ({
                picked: document.querySelectorAll('.ifd-box.ifd-picked').length,
                hash: location.hash })""")
            assert got["picked"] == 0, (where, got)
            assert "sel=" not in got["hash"], (where, got)
        assert not page.js_errors, page.js_errors


def test_the_box_of_crossings_points_back_at_the_wire_it_belongs_to() -> None:
    """A label is 300px wide and wider than the gutter its wire leaves through, and the placement
    pass moves it 6px clear so the two never overlap. Touching nothing and pointing nowhere, it read
    as floating beside the picture rather than labelling a line.

    The tail is the fix, and this asserts the thing that makes it a fix: its TIP lands on its own
    wire. Not that a triangle exists — a triangle pointing at nothing would pass that.

    The box goes BELOW its wire unless below would run off the bottom of the picture, which is the
    only constraint left now that a surface has one box rather than two to keep apart."""
    def mutate(m: dict) -> None:
        both = [{"direction": "in", "what": "what the caller asks for", "elements": []},
                {"direction": "out", "what": "the answer it gets back", "elements": []}]
        m["interfaces"] = [
            {"id": "I1", "name": "Ours", "what": "On our shore.", "side": "ours",
             "facing": "user", "kind": "screen", "carries": list(both)},
            {"id": "I2", "name": "Theirs", "what": "On theirs.", "side": "theirs",
             "facing": "user", "kind": "api", "carries": list(both)},
        ]
    with _served_map(mutate) as url, _page(url + "#v=interfaces") as page:
        _settle(page)
        for iid in ("I1", "I2"):        # one on each shore: the tail sits on the card side of each
            page.eval_on_selector(f'.ifd-box[data-iface="{iid}"]', "e => e.click()")
            page.wait_for_timeout(250)
            got = page.evaluate("""(iid) => {
                const st = document.getElementById('ifdstage').getBoundingClientRect();
                // the wire leaves the card at the card's own middle, in client space
                const b = document.querySelector(`.ifd-box[data-iface="${iid}"]`);
                const wireY = st.top + b.offsetTop + b.offsetHeight / 2;
                return [...document.querySelectorAll('.ifd-elabel.ifd-lab-on')].map(l => {
                    const r = l.getBoundingClientRect();
                    const down = l.classList.contains('ifd-tail-down');
                    const up = l.classList.contains('ifd-tail-up');
                    const cs = getComputedStyle(l, '::before');
                    // the outline triangle is 8px deep, so its tip is 8px beyond the label's edge
                    const tipY = down ? r.bottom + 8 : r.top - 8;
                    return { down, up, side: l.dataset.side,
                             offLeft: cs.left, offRight: cs.right,
                             offWire: Math.abs(wireY - tipY) };
                });
            }""", iid)
            assert len(got) == 1, (iid, got)     # one surface, one box
            g = got[0]
            assert g["down"] != g["up"], (iid, g)          # exactly one tail, pointing one way
            # THE TIP LANDS ON ITS WIRE, and slightly past it: the placement pass leaves a 6px gap
            # and the tail is 8px deep, so it crosses the line by 2 rather than stopping short of
            # it. Three pixels of tolerance covers that plus sub-pixel layout.
            assert g["offWire"] <= 3, (iid, g)
            # …and it sits on the CARD side, which is where the wire starts on that shore. Only the
            # side that is SET is asserted: a computed style resolves the other one to a used value
            # rather than `auto`, so checking for `auto` fails against correct code.
            assert g["offLeft" if g["side"] == "ours" else "offRight"] == "22px", (iid, g)
        assert not page.js_errors, page.js_errors
