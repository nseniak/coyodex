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
from urllib.parse import urlsplit
from urllib.request import urlopen

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
def _page(url: str, stylesheet: str | None = None) -> Iterator[Any]:
    """A Chromium page on `url`, with the first-run overlay dismissed and JS errors collected.

    Errors are attached as `page.js_errors`: a viewer that throws while rendering has failed, even
    when the assertion under test would otherwise pass.

    `stylesheet` serves that text in place of the viewer's own, from the FIRST layout on — the only
    way to test what the viewer does when its stylesheet cannot give the drawing room."""
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
        if stylesheet is not None:
            page.route("**/static/viewer.css", lambda route: route.fulfill(
                status=200, content_type="text/css", body=stylesheet))
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
            closed: document.querySelectorAll('.walk-box.walk-closes').length
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

    THE STEP ITSELF IS THE DOOR, and nothing pops up when it is clicked: the board is a picture to
    read across, and a card over it is in the way. What says "this one" is the step's own BOX, which
    lights on hover and stays lit when a link arrives here naming a step.
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
                shadow: getComputedStyle(gutter).boxShadow !== 'none'
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
                liveButtons: document.querySelectorAll('.walk-one').length
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
            "side": "theirs", "facing": "user", "kind": kind
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
                const g = b.querySelector('.ibox-head .ibox-gly');
                const v = await (await fetch('api/view')).json();
                return { d: [...g.querySelectorAll('rect, path')].map(e =>
                            e.getAttribute('d') || 'rect').join('|'),
                         w: g.getBoundingClientRect().width,
                         word: b.querySelector('.ibox-pill:not(.ibox-pill-alt)').textContent,
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
    """Two surfaces, one on each shore, and BOTH SHAPES the page has to draw: one people come to, one
    only the product reaches.

    I1 holds a way in, so use cases and the people driving them derive onto it. I2 stands on a dep a
    walk step is drawn at, so journeys reach it with nobody at the far side — 5 of MCP Hero's 16 are
    like that, and the box says something different for each."""
    def mutate(m: dict) -> None:
        m["entry_points"][0]["id"] = "EP1"
        for u in m["use_cases"]:
            if u["id"] in ("UC1", "UC2"):
                u["entry_points"] = ["EP1"]
        m["interfaces"] = [
            {"id": "I1", "name": "The dashboard", "what": "Screens a person signs in to.",
             "side": "ours", "facing": "user", "kind": "screen", "ways_in": ["EP1"]
             },
            {"id": "I2", "name": "Crash reporting", "what": "Where a crash is reported.",
             "side": "theirs", "facing": "operator", "kind": "api"
             },
        ]
        for d in m["deps"]:
            if d["id"] == "D4":
                d["interfaces"] = ["I2"]
    return mutate


def test_every_surface_draws_one_plain_line_to_the_product() -> None:
    """ONE LINE PER SURFACE, and it says only that this surface is one of the places the product
    meets the outside.

    NO HEADS. They carried the crossings' `in` and `out`, and the page stopped reading the crossings:
    what data moves turned out to be a written summary of what the walks already show, so the page
    reads the walks instead. Deriving a head from the walks would be a guess dressed as a fact —
    they disagree with the map's own answer on one of MCP Hero's sixteen surfaces."""
    with _served_map(_two_sided_interfaces()) as url, _page(url + "#v=interfaces") as page:
        _settle(page)
        got = page.evaluate("""() => {
            const out = {};
            for (const p of document.querySelectorAll('#ifdstage path[data-iface]'))
                (out[p.dataset.iface] = out[p.dataset.iface] || []).push({
                    start: !!p.getAttribute('marker-start'),
                    end: !!p.getAttribute('marker-end') });
            return { wires: out,
                     cards: [...document.querySelectorAll('.ifd-box')].map(b => b.dataset.iface) };
        }""")
        # EVERY card is joined, including one no use case reaches — the line is membership, not traffic
        for iid in got["cards"]:
            assert len(got["wires"].get(iid, [])) == 1, (iid, got)
            assert got["wires"][iid][0] == {"start": False, "end": False}, (iid, got)
        assert not page.js_errors, page.js_errors


def test_hovering_a_surface_lights_its_line_and_says_who_comes_and_what_for() -> None:
    """At rest every line is grey and unlabelled. Hover makes ONE surface the picture, and its box
    answers the page's question for that surface: who comes here, and what brings them.

    It used to say what DATA crosses. That is authored on the surface, and it is a written summary of
    what the walks already show — so the page reads the walks, and the two can no longer drift."""
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
                heads: on.flatMap(l => [...l.querySelectorAll('.ifd-elabel-dir')]
                                        .map(e => e.textContent)),
                doors: on.flatMap(l => [...l.querySelectorAll('.ifd-elabel-uc')]
                                        .map(e => e.textContent))
            };
        }""")
        assert set(shown["hot"]) == {"I1"}, shown
        assert set(shown["cold"]) == {"I2"}, shown
        assert shown["labels"] == 1, shown
        # a heading per person, naming them and counting what brings them
        assert shown["heads"] and all("use case" in h for h in shown["heads"]), shown
        # …and each use case under it is a door
        assert shown["doors"], shown
        assert not page.js_errors, page.js_errors


def test_what_we_own_holds_the_product_and_our_surfaces_and_keeps_its_distance() -> None:
    """The dashed box makes a claim, and it is asserted as a claim rather than as a drawing: the
    product and every surface we define are inside it, every surface we use is outside.

    A ring around the CIRCLE alone was built first and was false — the map's own words say an
    our-surface is one whose shape we define, so our dashboard and our command line ARE the product,
    and a ring left them outside it.

    AND IT KEEPS ITS DISTANCE. Stretched to the grid it drew its left border exactly on the cards'
    left edge and its top border through the `We define` heading, and its own title fell off the top
    of what the page will paint. `.ifd-wrap` is what clips the picture, so the room it needs had to
    come from there without moving the stage — the cards still share the breadcrumb's left edge.

    Three widths, because the gutters are `1fr`: a fixed width was right at 1440 and ran across the
    cards at 1024."""
    with _served_map(_two_sided_interfaces()) as url, _page(url + "#v=interfaces") as page:
        for width in (1440, 1280, 1024):
            page.set_viewport_size({"width": width, "height": 900})
            _settle(page)
            m = page.evaluate("""() => {
                const own = document.querySelector('.ifd-own');
                const o = own.getBoundingClientRect();
                const inside = (r) => r.left >= o.left && r.right <= o.right
                                   && r.top >= o.top && r.bottom <= o.bottom;
                const rects = (sel) => [...document.querySelectorAll(sel + ' .ifd-box')]
                    .map(c => c.getBoundingClientRect());
                const t = rects('.ifd-col-theirs');
                const stage = document.getElementById('ifdstage');
                const wrap = stage.parentElement;
                const w = wrap.getBoundingClientRect();
                const title = own.querySelector('span').getBoundingClientRect();
                const card = rects('.ifd-col-ours')[0];
                const head = document.querySelector('.ifd-col-ours .ifd-colhead')
                    .getBoundingClientRect();
                return {
                    holdsHub: inside(document.getElementById('ifdhub').getBoundingClientRect()),
                    ours: rects('.ifd-col-ours').map(inside),
                    // a their-surface must be wholly clear of it, not merely not-contained
                    theirsClear: t.every(r => r.left >= o.right),
                    hits: getComputedStyle(own).pointerEvents,
                    gapLeft: card.left - o.left,
                    gapRight: t.length ? t[0].left - o.right : 99,
                    belowHeading: o.top - head.bottom,
                    cardsSetTheTop:
                        document.querySelector('.ifd-col-ours .ifd-box').offsetTop
                        <= document.getElementById('ifdhub').offsetTop,
                    aboveFirstCard: card.top - o.top,
                    // `.ifd-wrap` is what clips, so "drawn whole" means inside ITS box
                    titleWhole: title.top >= w.top && title.bottom <= w.bottom
                             && title.left >= w.left && title.right <= w.right,
                    noScroll: wrap.scrollWidth === wrap.clientWidth
                           && wrap.scrollHeight === wrap.clientHeight,
                    // …and the picture still starts where the rest of the page does
                    stageLeft: Math.round(stage.getBoundingClientRect().left)
                };
            }""")
            assert m["holdsHub"], (width, m)
            assert m["ours"] and all(m["ours"]), (width, m)
            assert m["theirsClear"], (width, m)
            assert m["hits"] == "none", (width, m)   # it must not eat the click that drops the pin
            assert m["gapLeft"] >= 10, (width, m)
            assert m["gapRight"] >= 10, (width, m)
            assert m["aboveFirstCard"] >= 6, (width, m)
            # THE HEADING IS ONLY CLEARED WHERE THE CARDS SET THE TOP. On a picture this short the
            # circle is the tallest thing in it and starts at the stage's own edge, so holding the
            # product wins and the heading ends up inside the box — which is not wrong, since the
            # surfaces `We define` heads are the product too.
            if m["cardsSetTheTop"]:
                assert m["belowHeading"] >= 6, (width, m)
            assert m["titleWhole"], (width, m)
            assert m["noScroll"], (width, m)
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
            return { name: b.querySelector('.ibox-name').textContent,
                     glyphs: b.querySelectorAll('.ibox-head .ibox-gly').length };
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
                b => b.querySelector('.ibox-name').textContent),
            sentences: [...document.querySelectorAll('.ifd-box .ibox-what')].map(e => e.textContent),
            cards: document.querySelectorAll('.usecases-wrap .ecard[data-key]').length,
            text: document.querySelector('.usecases-wrap').textContent
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
             "side": "ours", "facing": "user", "kind": "screen", "ways_in": ["EP900"]
             },
            {"id": "I2", "name": "Google sign-in", "what": "Where a person proves who they are.",
             "side": "theirs", "facing": "user", "kind": "hosted-screen"
             },
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
                # …and a step at the `theirs` surface, naming NOBODY. The left column of this
                # picture is the walk now, so a surface with no step there has an empty cell and
                # draws one wire, not two — and an unattributed step is what the fallback shows.
                f["steps"].insert(1, {"n": -1, "src": "C1", "dst": "I2",
                                      "phrase": "sends them to Google to sign in", "note": "",
                                      "where": "backend/src/mcpolis/entrypoints/app.py:4",
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
                    ...[...b.querySelectorAll('.ibox-chip')].map(e => 'who:' + e.textContent),
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
    refs: [...pop.querySelectorAll('.insp-ref')].map((r) => r.textContent)
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
        got = _inspect(page, ".story-card.story-feature[data-sfeat]")
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
        page.click(".story-card.story-feature[data-sfeat] button")
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
              const el = document.querySelector('.story-card.story-feature[data-sfeat]');
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
          const el = document.querySelector('.story-card.story-feature[data-sfeat]');
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
            note: s.querySelector('.item-sec-note').textContent.slice(0, 24)
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
                '#asfstage .asf-shore, #asfstage .ifd-box .ibox-name')]
            .map((el) => (el.classList.contains('asf-shore') ? 'SHORE:' : 'surface:')
                + el.textContent)""")
        assert seen == ["SHORE:Where they reach the product", "surface:The dashboard",
                        "SHORE:Where the product reaches them", "surface:Google sign-in"], seen
        # The reader's OWN actor is marked on every card; the other people at the same surface stay
        # drawn, because "who else stands here" is context the card should keep.
        marked = page.evaluate(
            "() => [...document.querySelectorAll('.ibox-chip-me')].map((c) => c.textContent.trim())")
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
             "side": "ours", "facing": "user", "kind": "screen"
             },
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
                surface: b.querySelector('.ibox-name').textContent,
                cardMid: Math.round(b.offsetTop + b.offsetHeight / 2),
                featMid: box ? Math.round(box.offsetTop + box.offsetHeight / 2) : null,
                feats: box ? [...box.querySelectorAll('.asf-feat span')].map((f) => f.textContent)
                           : cell.textContent.trim()
              };
            });
        }""")
        assert rows, rows
        for r in rows:
            if r["featMid"] is not None:
                assert abs(r["cardMid"] - r["featMid"]) <= 1, r
            assert r["feats"], r
        # …and every wire the picture draws belongs to a surface: what this person does there, to
        # the surface, to the features they get through it. EACH wire needs the thing at its far end
        # to exist, and there are TWO such things — a surface no step of this actor's is drawn at
        # has nothing in the left cell and loses the first wire, exactly as a surface with no
        # feature loses the second.
        wired = page.evaluate("""() => {
            const st = document.querySelector('#asfstage');
            const per = {};
            for (const p of st.querySelectorAll('svg.ifd-wires path[data-iface]'))
              per[p.dataset.iface] = (per[p.dataset.iface] || 0) + 1;
            const has = {};
            for (const c of st.querySelectorAll('.asf-featcell'))
              has[c.dataset.iface] = { feats: !!c.querySelector('.asf-feats') };
            for (const c of st.querySelectorAll('.asf-crosscell'))
              (has[c.dataset.iface] = has[c.dataset.iface] || {}).cross = !!c.querySelector('.asf-cross');
            return Object.keys(per).map((k) => [per[k], !!has[k].cross, !!has[k].feats]);
        }""")
        assert wired, wired
        assert all(count == cross + feats for count, cross, feats in wired), wired
        assert any(count == 2 for count, _c, _f in wired), "the fixture exercises the full shape"
        assert not page.js_errors, page.js_errors

def _actor_wires_meet_their_cells(page: Any) -> dict:
    """How far the worst wire on an actor's page is from the two cells it joins, on screen NOW.

    Both ends of every wire, because both are read off the settled layout: the left one leaves what
    this person does at the surface, the right one arrives at the features they get through it."""
    return dict(page.evaluate("""() => {
        const st = document.getElementById('asfstage');
        const R = (el) => [el.offsetLeft + el.offsetWidth, el.offsetTop + el.offsetHeight / 2];
        const L = (el) => [el.offsetLeft, el.offsetTop + el.offsetHeight / 2];
        let worst = 0, wires = 0;
        for (const box of st.querySelectorAll('.ifd-box')) {
          const iid = box.dataset.iface, want = [];
          const c = st.querySelector('.asf-crosscell[data-iface="' + CSS.escape(iid) + '"] .asf-cross');
          if (c) want.push([R(c), L(box)]);
          const f = st.querySelector('.asf-featcell[data-iface="' + CSS.escape(iid) + '"] .asf-feats');
          if (f) want.push([R(box), L(f)]);
          const got = [...st.querySelectorAll(
              'svg.ifd-wires path[data-iface="' + CSS.escape(iid) + '"]')];
          for (let k = 0; k < want.length && k < got.length; k++) {
            const n = got[k].getAttribute('d').match(/-?[0-9.]+/g).map(Number);
            const d = Math.max(Math.hypot(n[0] - want[k][0][0], n[1] - want[k][0][1]),
                               Math.hypot(n[n.length - 2] - want[k][1][0],
                                          n[n.length - 1] - want[k][1][1]));
            if (d > worst) worst = d;
            wires++;
          }
        }
        return { wires, offCell: +worst.toFixed(1), stage: st.offsetWidth };
    }"""))


def test_an_actors_wires_meet_their_cells_in_a_narrow_window_and_after_a_RESIZE() -> None:
    """The same one-shot layout the Interfaces picture had, and the same two ways of being wrong:
    a stage that had not settled when the page first drew (18px off at 900px), and nothing at all
    recomputing afterwards (45px after a drag, and 445px on MCP Hero's widest actor).

    Here a wire runs cell to cell rather than to a circle, so BOTH of its ends are the claim: a line
    that starts beside what the person does and ends beside what they get is the only thing joining
    the three columns into one row."""
    with _served_map(_both_shores_carry_people_and_a_pipe()) as url, \
            _page(url + "#v=actor&act=Org creator") as page:
        page.set_viewport_size({"width": 900, "height": 900})
        page.reload()                    # a FRESH layout at the narrow width, not a resize
        page.wait_for_selector("#crumb")
        _settle(page)
        fresh = _actor_wires_meet_their_cells(page)
        assert fresh["wires"] >= 2, fresh
        assert fresh["offCell"] <= 1, fresh
        for width in (1900, 1152, 1024, 900):
            page.set_viewport_size({"width": width, "height": 900})
            _settle(page)
            got = _actor_wires_meet_their_cells(page)
            assert got["wires"] == fresh["wires"], (width, got, fresh)
            assert got["offCell"] <= 1, (width, got)
        assert not page.js_errors, page.js_errors


def test_an_actors_page_never_shows_ANOTHER_named_persons_steps() -> None:
    """The blocking finding of an adversarial review. The cell falls back when the walks name no
    step of this actor's own, and the fallback used to be EVERY step at the surface — including ones
    the map attributes to a different named role. On argus that told a reader the software
    "Assistant" picks a Google account and approves, a step belonging to the human "Visitor".

    The fallback is now to the UNATTRIBUTED steps only. A step naming nobody is machinery this actor
    can legitimately be shown; a step naming SOMEONE ELSE is another person's story."""
    def mutate(m: dict) -> None:
        _both_shores_carry_people_and_a_pipe()(m)
        for f in m["flows"]:
            if f["uc"] == "UC1":
                # R2 is a DIFFERENT person, and their step is the one that must not leak. It sits at
                # I2, where the actor under test (R1) has no step of their own.
                f["steps"].insert(2, {"n": -2, "src": "R2", "dst": "I2",
                                      "phrase": "picks the account and approves", "note": "",
                                      "where": None, "no_call_site": True, "subflow": None})
        m["roles"].append({"id": "R2", "name": "Somebody else", "kind": "human",
                           "audience": "user", "wants": "to sign in"})
    with _served_map(mutate) as url, _page(url + "#v=actor&act=Org creator") as page:
        _settle(page)
        text = page.evaluate("""() => [...document.querySelectorAll('.asf-crosscell')]
            .map((c) => c.textContent).join(' ')""")
        assert "picks the account and approves" not in text, text
        # …and the unattributed step at that same surface IS shown, or the fix would be a blanket
        # silence rather than a narrowing.
        assert "sends them to Google to sign in" in text, text
        assert not page.js_errors, page.js_errors


def test_an_actor_at_no_interface_says_so_and_the_products_own_work_says_why() -> None:
    """Two different facts, two different sentences. An actor the map puts at no surface is a plain
    absence; the product's OWN scheduled work — a service role that is internal — is inside the
    product and crosses nothing, which is a complete answer. One sentence for both would report the
    timer as an unfinished map."""
    def outsider(m: dict) -> None:
        _both_shores_carry_people_and_a_pipe()(m)
    with _served_map(outsider) as url, _page(url + "#v=actor&act=Superadmin") as page:
        _settle(page)
        text = page.evaluate("() => document.querySelector('.usecases-wrap').textContent")
        assert "No interface in this map has this actor standing at it." in text, text
        assert not page.js_errors, page.js_errors

    def inside(m: dict) -> None:
        _both_shores_carry_people_and_a_pipe()(m)
        for r in m["roles"]:
            if r["id"] == "R5":
                r["kind"], r["audience"] = "service", "internal"
    with _served_map(inside) as url, _page(url + "#v=actor&act=Superadmin") as page:
        _settle(page)
        text = page.evaluate("() => document.querySelector('.usecases-wrap').textContent")
        assert "crosses no interface" in text, text
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
             "side": "ours", "facing": "operator", "kind": "screen"
             },
            {"id": "I2", "name": "Second", "what": "Reached later on the walk.",
             "side": "ours", "facing": "user", "kind": "screen"
             },
            {"id": "I5", "name": "Never", "what": "Never on the walk, user-facing.",
             "side": "ours", "facing": "user", "kind": "screen"
             },
            {"id": "I9", "name": "First", "what": "Reached at the start of the walk.",
             "side": "ours", "facing": "user", "kind": "screen"
             },
            {"id": "I4", "name": "Theirs on the walk", "what": "Stands on the dep UC1 steps at.",
             "side": "theirs", "facing": "user", "kind": "api"
             },
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
            ours: [...document.querySelectorAll('.ifd-col-ours .ibox-name')].map(e => e.textContent),
            theirs: [...document.querySelectorAll('.ifd-col-theirs .ibox-name')].map(e => e.textContent)
        })""")
        assert got["ours"] == ["First", "Second", "Never", "Late and staffy"], got
        assert got["theirs"] == ["Theirs on the walk"], got
        assert not page.js_errors, page.js_errors


def test_the_people_at_a_surface_are_ordered_by_the_happy_path() -> None:
    """Surfaces are sorted by where the product's own story first reaches them, and so are the people
    inside each one. On MCP Hero's dashboard that is Visitor, then Organization admin, then Team
    member — the sequence the story takes, not the alphabet and not who is busiest.

    Ordering by size was tried first and reads as a ranking, which is a claim the map does not make.
    The story order is a fact it does."""
    def mutate(m: dict) -> None:
        # Two of the fixture's own use cases on one surface, driven by two different people. The
        # happy path takes UC1 (Org creator) before UC2 (Org admin), and the ALPHABET takes them the
        # other way round — so a page sorted by name and a page sorted by the story disagree here.
        m["entry_points"][0]["id"] = "EP1"
        for u in m["use_cases"]:
            if u["id"] in ("UC1", "UC2"):
                u["entry_points"] = ["EP1"]
        m["interfaces"] = [
            {"id": "I1", "name": "The door", "what": "One surface.", "side": "ours",
             "facing": "user", "kind": "screen", "ways_in": ["EP1"] },
        ]
    with _served_map(mutate) as url, _page(url + "#v=interfaces") as page:
        _settle(page)
        page.hover('.ifd-box[data-iface="I1"]')
        page.wait_for_timeout(250)
        got = page.evaluate("""() => ({
            chips: [...document.querySelectorAll('.ifd-box[data-iface="I1"] .ibox-chip')]
                     .map(e => e.textContent.trim()),
            heads: [...document.querySelectorAll('.ifd-elabel.ifd-lab-on .ifd-elabel-dir')]
                     .map(e => e.textContent)
        })""")
        # `Org admin` wins the alphabet; `Org creator` comes first on the story, and wins here.
        assert got["chips"] == ["Org creator", "Org admin"], got
        assert [h.split(" ·")[0] for h in got["heads"]] == ["Org creator", "Org admin"], got
        assert not page.js_errors, page.js_errors


def test_a_surface_no_use_case_reaches_is_drawn_quiet_and_sorted_last() -> None:
    """Three of MCP Hero's sixteen surfaces are named by no use case at all. A surface off the happy
    path but used by some journey is still part of the product's work; one no journey names is a
    different thing, and both the order and the drawing say so.

    Zero is A REAL ANSWER, said in words rather than as an empty space."""
    def mutate(m: dict) -> None:
        m["entry_points"][0]["id"] = "EP1"
        for u in m["use_cases"]:
            if u["id"] == "UC1":
                u["entry_points"] = ["EP1"]
        m["interfaces"] = [
            {"id": "I1", "name": "Untouched", "what": "No journey names it.", "side": "ours",
             "facing": "user", "kind": "screen" },
            {"id": "I2", "name": "Used", "what": "A journey comes here.", "side": "ours",
             "facing": "user", "kind": "screen", "ways_in": ["EP1"] },
        ]
    with _served_map(mutate) as url, _page(url + "#v=interfaces") as page:
        _settle(page)
        got = page.evaluate("""() => ({
            order: [...document.querySelectorAll('.ifd-col-ours .ifd-box')]
                     .map(b => b.dataset.iface),
            quiet: [...document.querySelectorAll('.ifd-col-ours .ifd-box')]
                     .map(b => b.classList.contains('ifd-box-quiet')),
            pills: [...document.querySelectorAll('.ifd-col-ours .ifd-box')]
                     .map(b => { const e = b.querySelector('.ibox-count');
                                 return e ? e.textContent : null; })
        })""")
        # the used one leads, the untouched one is last and drawn quiet
        assert got["order"] == ["I2", "I1"], got
        assert got["quiet"] == [False, True], got
        # …and NONE draws no pill at all: a label for an absence is one more thing to read
        assert got["pills"] == ["1 use case", None], got
        assert not page.js_errors, page.js_errors


def test_a_surfaces_own_page_tags_each_step_with_the_way_that_one_went() -> None:
    """The authored crossing table is gone with `interfaces[].carries[]`; each STEP now says which
    way it went, so the direction sits on the line that shows what happened rather than in a second
    block that could disagree with it.

    Same two verbs the table used, and the subject is still left out: a surface's own page is about
    one surface, so naming it on every line would repeat the page's own title. `both` says so
    plainly, because one exchange really does run each way."""
    def mutate(m: dict) -> None:
        m["interfaces"] = [
            {"id": "I1", "name": "Ours", "what": "On our shore.", "side": "ours",
             "facing": "user", "kind": "screen"
             },
        ]
        for f in m["flows"]:
            if f["uc"] == "UC1":
                f["steps"] = [
                    # A DOOR, so no direction: a role at a surface is a human action with no
                    # product end, and `validate` blocks one that carries a direction. An earlier
                    # version of this fixture put `in` here, pinning a shape the product rejects.
                    {"n": 1, "src": "R1", "dst": "I1",
                     "phrase": "types what they want", "note": "", "where": None,
                     "no_call_site": False, "subflow": None},
                    {"n": 4, "src": "I1", "dst": "C1", "direction": "in",
                     "phrase": "carries what they typed inward", "note": "",
                     "where": "backend/src/mcpolis/entrypoints/app.py:2",
                     "no_call_site": False, "subflow": None},
                    {"n": 2, "src": "C1", "dst": "I1", "direction": "out",
                     "phrase": "shows them the answer", "note": "",
                     "where": "backend/src/mcpolis/entrypoints/app.py:4",
                     "no_call_site": False, "subflow": None},
                    {"n": 3, "src": "C1", "dst": "I1", "direction": "both",
                     "phrase": "trades the code for the verified email", "note": "",
                     "where": "backend/src/mcpolis/entrypoints/app.py:9",
                     "no_call_site": False, "subflow": None},
                ]
    with _served_map(mutate) as url, _page(url + "#v=interfaces&iface=I1") as page:
        _settle(page)
        got = page.evaluate(
            "() => [...document.querySelectorAll('.ifs-dirtag')].map(e => e.textContent)")
        assert got == ["receives", "sends", "both ways"], got
        assert not page.js_errors, page.js_errors


def test_a_surfaces_wire_reaches_its_card_and_lands_on_the_product() -> None:
    """Both ends of the line are asserted, because both used to be wrong in their own way.

    AT THE CARD: no gap. A line that stops short of the thing it points at is a line the reader has
    to join up themselves. 14px of clearance was tried and Nitsan reversed it twice. What made the
    clearance seem necessary was the BRACKET — the picked card's 2px indigo border closing a
    surface's TWO wires into one line bent twice — and a surface draws ONE wire now, so the bracket
    cannot form at all.

    AT THE PRODUCT: on the circle's edge, along a radius. Aimed anywhere else the lines would cross
    inside the shape, and a hub with lines crossing through it stops reading as one thing.

    AND NO HEADS AT EITHER END. They carried the crossings' two directions, and the page no longer
    reads those — a head derived instead from the walks would be a guess dressed as a fact."""
    def mutate(m: dict) -> None:
        # A WAY IN, so a use case reaches it: the box is drawn for what comes through a surface, and
        # a surface nothing reaches is given no box at all.
        m["entry_points"][0]["id"] = "EP1"
        for u in m["use_cases"]:
            if u["id"] == "UC1":
                u["entry_points"] = ["EP1"]
        m["interfaces"] = [
            {"id": "I1", "name": "Both ways", "what": "It answers as well as asks.",
             "side": "ours", "facing": "user", "kind": "screen", "ways_in": ["EP1"]
             },
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
        assert got["heads"] == [False, False], got   # a plain line: membership, not traffic
        # It REACHES its card — no gap to join up by eye.
        assert got["startGap"] <= 1, got
        # …and it LANDS ON the product, on the circle itself rather than short of it or inside it.
        assert got["endOffCircle"] <= 1, got
        # …and the picked card really is wearing the shared 2px edge, so the single line above is
        # leaving from inside the span that used to close the bracket.
        assert got["borderW"] == "2px", got
        assert not page.js_errors, page.js_errors

def _wire_ends_on_the_product(page: Any) -> dict:
    """How far the worst wire's far end is from the product's rim, in the layout on screen NOW.

    ONLY the wires. The same drawing holds the picture's own frame, and measuring that against a
    circle it was never aimed at reports a number in the hundreds that means nothing at all."""
    return dict(page.evaluate("""() => {
        const st = document.getElementById('ifdstage');
        const hub = document.getElementById('ifdhub');
        const cx = hub.offsetLeft + hub.offsetWidth / 2;
        const cy = hub.offsetTop + hub.offsetHeight / 2;
        const r = hub.offsetWidth / 2;
        let worst = 0, wires = 0;
        for (const p of st.querySelectorAll('svg.ifd-wires path[data-iface]')) {
          const n = p.getAttribute('d').match(/-?[0-9.]+/g).map(Number);
          const d = Math.abs(Math.hypot(n[n.length - 2] - cx, n[n.length - 1] - cy) - r);
          if (d > worst) worst = d;
          wires++;
        }
        return { wires, offCircle: +worst.toFixed(1), stage: st.offsetWidth };
    }"""))


def test_a_surfaces_wire_lands_on_the_product_in_a_NARROW_window() -> None:
    """The picture was laid out ONCE, against a stage that had not finished settling.

    `#srcrail` is a 30px button the page unhides AFTER the view has rendered, so that one pass
    measured a stage 30px wider than the one the reader ends up looking at, and every wire ended
    that far off the circle: 35px at a 900px window, 14px at 1024. From 1152 up the stage is at its
    width cap in both layouts, which is why the picture looked right on the machine it was built on
    and wrong on a laptop.

    A RELOAD, not a resize: the defect is in the first layout, and only a fresh document has one.
    And only a browser has one at all, which is why no source test caught this."""
    with _served_map(_two_sided_interfaces()) as url, _page(url + "#v=interfaces") as page:
        page.set_viewport_size({"width": 900, "height": 900})
        page.reload()
        page.wait_for_selector("#crumb")
        _settle(page)
        got = _wire_ends_on_the_product(page)
        assert got["wires"] == 2, got
        assert got["offCircle"] <= 1, got
        assert not page.js_errors, page.js_errors


def test_a_surfaces_wire_follows_the_product_when_the_WINDOW_RESIZES() -> None:
    """Nothing recomputed on a resize at all — the wires stayed where the opening width put them.
    Measured on MCP Hero, opened at 1400 and dragged narrower: 25px off at 1100, 63px at 1024, 135px
    at 900, which is a spoke pointing into open space beside a circle it never touches.

    AND THE PICK SURVIVES IT. The re-layout builds the wires and the boxes fresh, so a surface the
    reader had picked has to be lit again on the new ones. Otherwise widening the window puts their
    pick out, and the picture answers for nothing while a card still wears the picked edge."""
    with _served_map(_two_sided_interfaces()) as url, _page(url + "#v=interfaces") as page:
        _settle(page)
        page.eval_on_selector('.ifd-box[data-iface="I1"]', "e => e.click()")
        page.wait_for_timeout(300)
        for width in (1900, 1152, 1024, 900):
            page.set_viewport_size({"width": width, "height": 900})
            _settle(page)
            got = _wire_ends_on_the_product(page)
            assert got["wires"] == 2, (width, got)
            assert got["offCircle"] <= 1, (width, got)
        lit = page.evaluate("""() => {
            const st = document.getElementById('ifdstage');
            const ids = (sel) => [...st.querySelectorAll(sel)].map((e) => e.dataset.iface).sort();
            return { hot: ids('svg.ifd-wires path.ifd-hot'),
                     cold: ids('svg.ifd-wires path.ifd-cold'),
                     labelled: ids('.ifd-elabel.ifd-lab-on') };
        }""")
        assert lit == {"hot": ["I1"], "cold": ["I2"], "labelled": ["I1"]}, lit
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
            name: b.querySelector('.ibox-name').textContent,
            doors: [...b.querySelectorAll('button, a, [role=button]')]
                     .filter(e => !e.classList.contains('gloss-link'))
                     .map(e => e.className),
            chips: b.querySelectorAll('.ibox-chip').length,
            provs: b.querySelectorAll('.ifd-prov').length
        }))""")
        assert got, got
        for card in got:
            assert card["doors"] == ["ibox-name"], card
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

    It now starts where its line starts and grows AWAY from the card, overhanging the middle and the
    far column instead — both dimmed while it shows, and neither is what the reader is looking at.
    ONE box per interface, so what is asserted is that the single box clears the card on both
    shores."""
    def mutate(m: dict) -> None:
        # ONE ON EACH SHORE, each with a way in so a use case reaches it — an interface nothing
        # reaches gets no box, and this test is about where a box goes.
        m["entry_points"][0]["id"] = "EP1"
        m["entry_points"][1]["id"] = "EP2"
        m["use_cases"][0]["entry_points"] = ["EP1"]
        m["use_cases"][1]["entry_points"] = ["EP2"]
        m["interfaces"] = [
            {"id": "I1", "name": "Ours", "what": "On our shore.", "side": "ours",
             "facing": "user", "kind": "screen", "ways_in": ["EP1"] },
            {"id": "I2", "name": "Theirs", "what": "On theirs.", "side": "theirs",
             "facing": "user", "kind": "hosted-screen", "ways_in": ["EP2"] },
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
             "side": "ours", "facing": "user", "kind": "screen"
             },
        ]
    return mutate


def test_a_use_case_on_the_box_is_a_door_and_the_rest_are_counted() -> None:
    """The box lists what brings each person here, and every one of them is a screen of its own — the
    same treatment the records it used to list already had.

    CAPPED AT THREE, with a tail that SAYS how many are held back. MCP Hero's dashboard brings its
    admin through 27 use cases; a box that listed them all would be taller than the picture, and one
    that showed three and stopped would be lying by omission. The tail is the shared `+n more`, the
    one look every capped list in this viewer uses."""
    def mutate(m: dict) -> None:
        # Five use cases through one surface, all driven by the same person: more than the cap.
        m["entry_points"][0]["id"] = "EP1"
        for u in m["use_cases"]:
            if u["id"] in ("UC2", "UC3", "UC4", "UC5", "UC6"):
                u["entry_points"] = ["EP1"]
        m["interfaces"] = [
            {"id": "I1", "name": "Busy", "what": "One person, many journeys.", "side": "ours",
             "facing": "user", "kind": "screen", "ways_in": ["EP1"] },
        ]
    with _served_map(mutate) as url, _page(url + "#v=interfaces") as page:
        _settle(page)
        page.eval_on_selector('.ifd-box[data-iface="I1"]', "e => e.click()")
        page.wait_for_timeout(300)
        got = page.evaluate("""() => {
            const l = document.querySelector('.ifd-elabel.ifd-lab-on');
            return { head: l.querySelector('.ifd-elabel-dir').textContent,
                     doors: [...l.querySelectorAll('.ifd-elabel-uc')].map(e => e.textContent),
                     tail: (l.querySelector('.ifd-what-more') || {}).textContent || '' };
        }""")
        assert "5 use cases" in got["head"], got        # the head counts them all…
        assert len(got["doors"]) == 3, got              # …the list shows three…
        assert got["tail"].strip().startswith("+2"), got   # …and the tail names the rest
        # …and a door really opens its use case
        page.click(".ifd-elabel-uc")
        page.wait_for_timeout(300)
        assert "uc=" in page.evaluate("() => location.hash"), page.evaluate("() => location.hash")
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


def test_the_leader_meets_its_arrow_at_a_right_angle_clear_of_the_head() -> None:
    """The leader is the placement made visible, so it is asserted as geometry, not as a decoration.

    PERPENDICULAR, and A CONSTANT LENGTH. It used to be drawn straight down and always 14px, and
    these arrows run from nearly flat to very steep — slopes 0.05 to 2.34 on MCP Hero — so the gap a
    reader actually saw ranged 5.5px to 14px across sixteen surfaces. Boxes on steep arrows looked
    glued on and boxes on flat ones looked loose.

    AND CLEAR OF THE HEAD. The anchor used to be wherever box and arrow came closest, which on four
    of those sixteen was within 2px of the arrow's end at the card — landing on the very arrowhead
    the box is moved aside to keep visible.

    All three are read back from the laid-out page: where the leader starts, how long it is, which
    way it is turned. A dashed line that merely EXISTS would pass a test that only looked for one."""
    def mutate(m: dict) -> None:
        # AS LONG AS THE REAL MAPS GET, not longer. MCP Hero's dashboard is the tallest box on any
        # of the three live maps at 378px — two sentences a direction, each wrapping three or four
        # lines. A fixture beyond that is a picture no build produces, and every box in it clamps,
        # which tests the exemption rather than the rule.
        # A WAY IN EACH, so every one is reached by a use case: an interface nothing reaches
        # gets no box at all, and this test is about where the boxes go.
        for n, ep in enumerate(m["entry_points"][:16], start=1):
            ep["id"] = f"EP{n}"
        for n, u in enumerate(m["use_cases"][:16], start=1):
            u["entry_points"] = [f"EP{n}"]
        m["interfaces"] = [
            {"id": f"I{n}", "name": f"Surface {n}", "what": "One of several.",
             "side": "ours" if n % 2 else "theirs", "facing": "user", "kind": "screen",
             "ways_in": [f"EP{n}"] }
            # SIXTEEN, the size of the largest live map. The stage's height comes from the
            # number of cards, and the room a box has to get off its line comes from the
            # stage. Eight interfaces make a 500px picture a 300px box cannot be placed in.
            for n in range(1, 17)
        ]
    with _served_map(mutate) as url, _page(url + "#v=interfaces") as page:
        _settle(page)
        got = page.evaluate("""() => {
            return [...document.querySelectorAll('.ifd-elabel')].map(l => {
                const [x0, y0, x1, y1] = String(l.dataset.wire).split(' ').map(Number);
                const bl = parseFloat(l.style.left), bt = parseFloat(l.style.top);
                // laid out to read its width: a `display: none` element measures 0, and the corner
                // the leader leaves from is either 0 or the box's full width across.
                l.style.visibility = 'hidden'; l.style.display = 'block';
                const w = l.offsetWidth;
                l.style.display = ''; l.style.visibility = '';
                const cs = getComputedStyle(l);
                const num = (k) => parseFloat(cs.getPropertyValue(k));
                const len = num('--lead-len');
                // where it starts (the box's own corner) and where it ends, from the same three
                // numbers the stylesheet draws it with: a line straight down, then rotated.
                const qx = bl + num('--lead-x'), qy = bt + num('--lead-y');
                const rot = num('--lead-rot') * Math.PI / 180;
                const ex = qx - len * Math.sin(rot), ey = qy + len * Math.cos(rot);
                const dx = x1 - x0, dy = y1 - y0, seg = Math.hypot(dx, dy);
                const t = ((ex - x0) * dx + (ey - y0) * dy) / (seg * seg);
                return {
                    clamped: !!l.dataset.clamped, len,
                    // how far the far end misses the arrow by
                    offArrow: Math.hypot(ex - (x0 + dx * t), ey - (y0 + dy * t)),
                    // 0 when the leader and the arrow meet at a right angle
                    cosine: Math.abs((ex - qx) * dx + (ey - qy) * dy) / (len * seg),
                    along: t * seg,
                    // …and the corner it leaves from is a corner OF THE BOX
                    onBox: Math.abs(num('--lead-x')) < 1 || Math.abs(num('--lead-x') - w) < 1
                };
            });
        }""")
        assert got, got
        drawn = [g for g in got if not g["clamped"]]
        assert drawn, got                      # or this asserts nothing at all
        for g in drawn:
            assert abs(g["len"] - 14) < 0.5, g          # the constant, not whatever fitted
            assert g["cosine"] < 0.02, g                # a right angle
            assert g["offArrow"] < 0.5, g               # …ending ON the arrow
            assert g["along"] >= 27.5, g                # …and never on its head
            assert g["onBox"], g
        for g in got:
            # A CLAMPED BOX HAS NO LEADER, and must not have one: the picture was too short to hold
            # it off its arrow, so it is ON the line and there is no gap to draw across.
            if g["clamped"]:
                assert g["len"] == 0, g
        assert not page.js_errors, page.js_errors


def _stage_state(page: Any) -> dict:
    """What the drawing and its pan/zoom machinery think they are, right now.

    NaN and Infinity do not survive the trip out of the page intact, so every number that could be
    one is reduced to a yes/no in the page itself."""
    return dict(page.evaluate("""() => {
        const stage = document.getElementById('stage');
        const d = document.getElementById('diagram');
        const svg = d.querySelector('svg');
        // svgPanZoom() on an element it already owns hands back that same instance. It BUILDS one on
        // an svg it does not own, so only ever call this where the first svg is the map itself — a
        // card view's first svg is a decoration, and this would quietly pan-zoom that instead.
        const pz = (svg && window.svgPanZoom) ? window.svgPanZoom(svg) : null;
        const sizes = pz ? pz.getSizes() : null;
        const zoom = pz ? pz.getZoom() : null;
        return {
            drawingHeight: Math.round(d.getBoundingClientRect().height),
            // the pan/zoom base scale: 0 is the poisoned state, and nothing recovers from it
            baseScaleIsReal: !!(sizes && sizes.realZoom > 0 && Number.isFinite(sizes.realZoom)),
            fittedHeight: sizes ? Math.round(sizes.height) : 0,
            zoomIsReal: Number.isFinite(zoom),
            header: (document.getElementById('zoomlevel').textContent || '').trim(),
            paneScrolls: stage.scrollHeight > stage.clientHeight + 1
        };
    }"""))


def test_a_pane_too_short_for_its_header_still_draws_the_map() -> None:
    """A window short enough that the tabs, the trail and the feature's own heading fill the whole
    graph pane used to leave the drawing exactly 0 tall — and 0 is worse than small. The pan/zoom
    machinery DIVIDES BY that height with no floor of its own, so the map went blank, the zoom in the
    title bar read "NaN%", and it never came back: widening the window again fed the same NaN into
    every later move instead of re-fitting. Measured on this map at 529x265, the header alone was
    218px inside a 161px pane. The drawing now keeps a floor and the pane scrolls to reach it.

    This one is about the FLOOR: at the size it uses, the old code left the drawing 1px tall rather
    than 0, so it was starved but not yet poisoned. The two tests below cover the poisoning itself."""
    with _served() as url, _page(url + "#v=usecase&uc=UC1") as page:
        page.set_viewport_size({"width": 560, "height": 240})
        _settle(page)
        short = _stage_state(page)
        assert short["drawingHeight"] >= 160, short      # the floor, not the 0 the header left
        assert short["baseScaleIsReal"], short
        assert short["zoomIsReal"], short
        assert re.fullmatch(r"\d+%", short["header"]), short   # never "NaN%"
        assert short["paneScrolls"], short               # …because the header no longer eats the map

        # The move that used to do the poisoning: a resize while the drawing has no room. Every
        # re-fit path in the viewer goes through this one, so a window resize covers them all.
        page.set_viewport_size({"width": 560, "height": 210})
        _settle(page)
        assert _stage_state(page)["zoomIsReal"], _stage_state(page)

        # …and the map comes BACK when the window does. This is the half that stayed broken before:
        # the fit is re-measured against the new pane instead of dividing by a stale NaN.
        page.set_viewport_size({"width": 1200, "height": 820})
        _settle(page)
        wide = _stage_state(page)
        assert wide["baseScaleIsReal"], wide
        assert abs(wide["fittedHeight"] - wide["drawingHeight"]) <= 2, wide
        assert not wide["paneScrolls"], wide
        assert not page.js_errors, page.js_errors


def test_the_graph_pane_scrolls_only_when_its_header_cannot_fit() -> None:
    """The floor under the drawing is paid for by letting the graph pane scroll. That must cost
    nothing at a size anybody actually uses: at a normal window the drawing is far taller than its
    floor, so the pane has nothing below its own bottom edge and never offers a scrollbar. It had 29
    unreachable pixels down there before, from the selection card — invisible only because the pane
    clipped instead of scrolling, and a scrollbar on every normal window the moment it stopped."""
    with _served() as url, _page(url + "#v=usecase&uc=UC1") as page:
        for width, height in ((1400, 900), (1100, 760), (960, 620)):
            page.set_viewport_size({"width": width, "height": height})
            _settle(page)
            seen = _stage_state(page)
            assert not seen["paneScrolls"], (width, height, seen)
            assert seen["baseScaleIsReal"], (width, height, seen)
        assert not page.js_errors, page.js_errors


def test_a_drawing_squeezed_to_nothing_does_not_poison_the_map_for_good() -> None:
    """The floor is one guard, and this is the other — the one that still holds if the floor ever
    moves. Take the floor away by hand so the drawing really does measure nothing, then resize the
    window on top of it. The pan/zoom machinery has to SKIP that move: measuring a box with no height
    is what set its base scale to 0, and from 0 the zoom is 0/0 and every later fit divides by that
    NaN instead of recovering. Give the drawing its room back and the map fits again."""
    with _served() as url, _page(url + "#v=usecase&uc=UC1") as page:
        page.set_viewport_size({"width": 900, "height": 700})
        _settle(page)
        assert _stage_state(page)["baseScaleIsReal"]

        page.evaluate("() => { document.getElementById('diagwrap').style.minHeight = '0px'; }")
        page.set_viewport_size({"width": 560, "height": 210})
        _settle(page)
        squeezed = _stage_state(page)
        assert squeezed["drawingHeight"] == 0, squeezed        # the box really is gone…
        assert squeezed["zoomIsReal"], squeezed                # …and the map is still not poisoned
        assert re.fullmatch(r"\d+%", squeezed["header"]), squeezed

        page.evaluate("() => { document.getElementById('diagwrap').style.minHeight = ''; }")
        page.set_viewport_size({"width": 1200, "height": 820})
        _settle(page)
        back = _stage_state(page)
        assert back["baseScaleIsReal"], back
        assert abs(back["fittedHeight"] - back["drawingHeight"]) <= 2, back
        assert not page.js_errors, page.js_errors


def _stylesheet_with_no_room(url: str) -> str:
    """The viewer's real stylesheet, with the floor under the drawing taken out and a header too tall
    for any window — so the drawing measures nothing from the first layout, before anything else has
    had a chance to render. Removing the floor alone is not enough to test this: the drawing still has
    room at the moment the map is built, and only loses it once the feature's heading fills in."""
    parts = urlsplit(url)
    css = urlopen(f"{parts.scheme}://{parts.netloc}/static/viewer.css").read().decode()
    out = css.replace("min-width: 0; min-height: 160px; display: flex;",
                      "min-width: 0; min-height: 0; display: flex;")
    assert out != css, "the floor rule moved — this test no longer takes it out"
    return out + "\n#stagehead{min-height:2000px;}"


def test_a_map_built_with_no_room_at_all_still_comes_back() -> None:
    """The worst version of the same fault, and the one the floor alone does not cover: the map is
    BUILT while the drawing has no room, not merely squeezed afterwards. The pan/zoom machinery
    measures that box once, at birth, and divides by it — so a 0 there used to be permanent. Verified
    against the old code through this exact test: the map stayed blank at "NaN%" and threw
    "the matrix is not invertible", and making the window large again did not bring it back, because
    every later fit divided by the NaN the first measurement produced."""
    with _served() as url:
        with _page(url + "#v=usecase&uc=UC1", stylesheet=_stylesheet_with_no_room(url)) as page:
            page.wait_for_timeout(1200)
            blind = _stage_state(page)
            assert blind["drawingHeight"] == 0, blind          # built with nothing at all…
            assert blind["zoomIsReal"], blind                  # …and still not poisoned
            assert re.fullmatch(r"\d+%", blind["header"]), blind

            # room back: the header stops being impossible, and the map must FIT, not stay broken
            page.evaluate("""() => {
                for (const sheet of document.styleSheets) {
                    try {
                        for (let i = sheet.cssRules.length - 1; i >= 0; i--) {
                            if (String(sheet.cssRules[i].cssText).includes('min-height: 2000px')) {
                                sheet.deleteRule(i);
                            }
                        }
                    } catch (e) { /* a cross-origin sheet has no readable rules */ }
                }
            }""")
            page.set_viewport_size({"width": 1200, "height": 820})
            page.wait_for_timeout(1200)
            back = _stage_state(page)
            assert back["baseScaleIsReal"], back
            assert abs(back["fittedHeight"] - back["drawingHeight"]) <= 2, back
            assert not page.js_errors, page.js_errors


def test_a_map_poisoned_behind_the_viewer_s_back_still_never_throws() -> None:
    """The last line of defence, and the only test that reaches it. The two guards above stop the map
    from ever being measured against a box with no room — so the code that copes with a map that WAS
    measured that way is never reached by any normal route, and a test that only drives the viewer
    cannot tell whether it still works. So reach past the viewer and poison the map directly, the way
    the drawing library itself used to: re-measure and re-fit it against a box with no height. From
    there the map's scale is 0, and dividing by it is what put an Infinity into a drawing coordinate
    and left a shape whose position cannot be worked back — the two errors originally reported. The
    viewer must survive it silently: nothing thrown, and the zoom still a real number."""
    with _served() as url, _page(url + "#v=usecase&uc=UC1") as page:
        page.set_viewport_size({"width": 1100, "height": 760})
        _settle(page)
        assert _stage_state(page)["baseScaleIsReal"]

        poisoned = page.evaluate("""() => {
            document.getElementById('diagwrap').style.minHeight = '0px';
            const svg = document.getElementById('diagram').querySelector('svg');
            const pz = window.svgPanZoom(svg);
            document.getElementById('stagehead').style.minHeight = '4000px';   // the drawing is now 0 tall
            // exactly what the viewer's own re-fit does — but with its guard bypassed
            pz.resize(); pz.fit(); pz.center();
            return { drawingHeight: Math.round(document.getElementById('diagram')
                                                .getBoundingClientRect().height),
                     baseScale: pz.getSizes().realZoom };
        }""")
        assert poisoned["drawingHeight"] == 0, poisoned
        assert poisoned["baseScale"] == 0, poisoned    # the map really is poisoned now

        # …and now use it. Every one of these went through the coordinate maths that used to throw.
        page.mouse.move(400, 300)
        page.mouse.move(500, 360)
        page.wait_for_timeout(200)
        page.evaluate("() => window.dispatchEvent(new Event('resize'))")
        page.set_viewport_size({"width": 900, "height": 700})
        _settle(page)
        # The map's own scale stays 0 — the drawing library cannot be talked out of that, and this
        # test deliberately never gives the room back (the two tests above cover recovery). What is
        # being asserted is the ONLY thing the viewer still owes here: it does not throw.
        assert not page.js_errors, page.js_errors


def test_a_record_inside_another_one_lists_the_use_cases_that_reach_its_holder() -> None:
    """The panel and the check must not disagree about one record.

    `validate` counts an embedded record as storied when its container is reached — it lives in the
    holder's row, so a story that writes the holder writes the piece. The panel walked no holder
    chain, so it said "No traced use case reaches it" on exactly those records: the screen calling a
    gap what the check calls fine, about the same record, on the same map.

    E2 is embedded in E1, and only E1 is ever named by a step."""
    def mutate(m: dict) -> None:
        m["entities"] = [e for e in m["entities"] if e["id"] in ("E1", "E2")]
        e1, e2 = (next(e for e in m["entities"] if e["id"] == i) for i in ("E1", "E2"))
        e1["store"] = {"dep": "D1", "container": "orders", "mode": "collection", "notes": ""}
        e2["store"] = {"dep": "D1", "container": "orders", "mode": "embedded", "notes": ""}
        e1["relations"] = [{"verb": "contains", "target": "E2", "src_card": "1", "dst_card": "*",
                            "display": e2["name"], "how": None, "keyed_by": []}]
        e2["relations"] = []
        for f in m["flows"]:
            if f["uc"] == "UC1":
                f["steps"] = [{"n": 1, "src": "C1", "dst": "E1", "phrase": "writes the record",
                               "note": "", "where": "backend/src/mcpolis/entrypoints/app.py:1",
                               "no_call_site": False, "subflow": None, "direction": "out"}]
        m["subflows"] = []
        for f in m["flows"]:
            if f["uc"] != "UC1":
                f["steps"] = [s for s in f["steps"] if not (s["src"].startswith("E")
                                                            or s["dst"].startswith("E"))]
    with _served_map(mutate) as url, _page(url + "#v=element&id=E2") as page:
        _settle(page)
        text = page.evaluate("() => document.body.innerText")
        assert "IN USE CASES" in text.upper(), text[:400]
        assert "No traced use case reaches it" not in text, \
            "E2 is inside E1, and E1 is storied — the holder's stories are its stories"
        assert not page.js_errors, page.js_errors


def _with_shared_walk(m: Any) -> None:
    """UC1 runs a shared walk that keeps a record — the shape the committed fixture has none of."""
    m["subflows"] = [{
        "id": "SF1", "name": "Keep the organization",
        "steps": [{"n": 1, "src": "C101", "dst": "E1", "phrase": "writes the organization",
                   "note": "", "where": None, "no_call_site": False, "subflow": None},
                  {"n": 2, "src": "E1", "dst": "C101", "phrase": "hands back what it stored",
                   "note": "", "where": None, "no_call_site": False, "subflow": None}],
    }]
    steps = m["flows"][0]["steps"]
    steps[2:2] = [{"n": 99, "src": "C101", "dst": "C15", "phrase": "", "note": "", "where": None,
                   "no_call_site": False, "subflow": "SF1"}]


def test_a_use_case_walk_counts_its_own_steps_not_the_shared_walk_s() -> None:
    """A use case that runs a shared walk used to count that walk's steps as its own — so the counter,
    the numbers on the map and the numbers in the Sequence view all described a walk longer than the one
    the map stores. The reference is one step now, and BOTH pictures say so: they are read against each
    other by number, so a disagreement would make the toggle between them land somewhere else."""
    with _served_map(_with_shared_walk) as url, _page(url + "#v=usecase&uc=UC1") as page:
        _settle(page)
        seen = page.evaluate("""() => {
            const chips = [...document.querySelectorAll('#diagram .ibox-chip')].map((c) =>
              ({ t: c.textContent,
                 k: ([...c.classList].find((x) => x.startsWith('ibox-k-')) || '').slice(7) }));
            const box = [...document.querySelectorAll('#diagram g.node')]
              .find((n) => /SF1/.test(n.id));
            return { counter: document.querySelector('.flowplay-count, .stepcount, .flow-count')?.textContent
                       || document.body.innerText.match(/Step\\s*[-–]?\\s*\\/\\s*(\\d+)/)?.[1],
                     chips, hasBox: !!box,
                     steps: [...document.querySelectorAll('#diagram .ibox-count')].map((e) => e.textContent),
                     arrows: [...document.querySelectorAll('#diagram .edgeLabel')]
                       .map((e) => e.textContent.trim()).filter(Boolean) };
        }""")
        assert seen["hasBox"], "the shared walk is drawn as its own box"
        assert seen["chips"] == [{"t": "Organization", "k": "entity"}], seen["chips"]
        # HOW MANY STEPS THE SHARED WALK HOLDS IS NOT ON ITS BOX. The box is a door to the walk's own
        # screen, where its steps are numbered from 1 and belong to it; a count here answered a
        # question this picture is not about, and it was the one number on a box that carries chips.
        assert seen["steps"] == [], seen["steps"]
        # 12 = the fixture's own 11 steps plus the one reference. Expanded it would have read 13.
        assert seen["counter"] == "12", seen
        assert "3" in seen["arrows"] and "13" not in seen["arrows"], seen["arrows"]
        assert not page.js_errors, page.js_errors


def test_the_shared_walk_s_box_opens_the_walk_itself() -> None:
    """A shared walk belongs to every use case that runs it, so it has a screen of its own rather than a
    home inside one of them. Drilling the box opens it: its steps numbered from 1, its own two pictures,
    and a trail that still leads back the way the reader came."""
    with _served_map(_with_shared_walk) as url, _page(url + "#v=usecase&uc=UC1") as page:
        _settle(page)
        page.evaluate("""() => {
            const box = [...document.querySelectorAll('#diagram g.node')].find((n) => /SF1/.test(n.id));
            box.dispatchEvent(new MouseEvent('click', { bubbles: true, altKey: true }));
        }""")
        page.wait_for_function("() => location.hash.includes('subflow')")
        _settle(page)
        seen = page.evaluate("""() => ({
            hash: location.hash,
            crumbs: [...document.querySelectorAll('#crumb *')].map((e) => e.textContent.trim())
                      .filter(Boolean),
            counter: document.body.innerText.match(/Step\\s*[-–]?\\s*\\/\\s*(\\d+)/)?.[1],
        })""")
        assert "v=subflow" in seen["hash"] and "sf=SF1" in seen["hash"], seen["hash"]
        assert seen["counter"] == "2", seen           # its own two steps, numbered from 1
        assert seen["crumbs"][-1] == "Keep the organization", seen["crumbs"]
        assert "SF1" not in " ".join(seen["crumbs"]), "an id must never reach the screen"
        assert not page.js_errors, page.js_errors


def test_the_first_walk_opens_the_code_column_and_then_leaves_it_alone() -> None:
    """The rail that opens the source column is a thin strip on the far edge, and nothing on a use case
    map says the two are joined — while every box and every arrow on it points at a place in the code.
    So the first walk opens it. ONCE: a reader who then shuts it is not argued with on the next walk.

    A source test cannot see this. The rule is decided inside `syncCodePane`, and whether it fires at all
    depends on a fetch that is still in flight when the first render runs."""
    with _served() as url, _page(url + "#v=usecase&uc=UC1") as page:
        _settle(page)
        assert page.evaluate("() => !document.body.classList.contains('code-hidden')"), \
            "the first walk shows the reader the column exists"
        page.evaluate("() => document.getElementById('cvclose').click()")
        page.wait_for_timeout(600)
        page.goto(url + "#v=usecase&uc=UC2")
        _settle(page)
        assert page.evaluate("() => document.body.classList.contains('code-hidden')"), \
            "closed once is closed for good — the rule fires on the FIRST walk only"
        assert not page.js_errors, page.js_errors


def test_a_selected_box_gets_a_card_with_a_line_to_it_not_a_drawer() -> None:
    """Every other screen puts what it is describing beside what you clicked. The map put it in a band
    across the bottom, because the drawer held the default from when the card was the newer shape. The
    card is the default now, and it draws a leader line to the box it describes."""
    with _served() as url, _page(url + "#v=usecase&uc=UC1") as page:
        _settle(page)
        assert not page.evaluate("() => document.body.classList.contains('card-drawer')")
        page.evaluate("""() => {
            const n = [...document.querySelectorAll('#diagram g.node')][1];
            n.dispatchEvent(new MouseEvent('click', { bubbles: true }));
        }""")
        page.wait_for_timeout(800)
        assert page.evaluate("() => !document.getElementById('callout').hasAttribute('hidden')"), \
            "the card points at what it describes"
        assert not page.js_errors, page.js_errors


def test_a_box_s_name_opens_it_and_the_box_around_the_name_selects_it() -> None:
    """Features and Interfaces open a thing by clicking its title. On the map that gesture existed only
    one step removed — click the box, then click the card that appears — while the box itself offered a
    corner icon that does something else entirely (locate this element in a structural view).

    The name opens it now, in one click. The box AROUND the name still selects, so the two acts stay
    apart: the name goes somewhere, the box stays here and tells you about itself. Measured on mcpolis
    UC30, a component's name is a quarter to a half of its box, so both targets are real."""
    with _served() as url, _page(url + "#v=usecase&uc=UC1") as page:
        _settle(page)
        spot = page.evaluate("""() => {
            const n = [...document.querySelectorAll('#diagram g.node')].find((x) => /C15/.test(x.id));
            // THE VISIBLE BOX, not the node group. The drawing engine pads a node well past its
            // label, and that padding is transparent and takes no clicks — a point inside the group
            // can be outside the box a reader can see. Every coordinate here is the box's own, and
            // the second one is its top-left corner: inside the box, inside its own padding, and
            // clear of the name however long the name runs.
            const b = n.querySelector('.ibox').getBoundingClientRect();
            const l = n.querySelector('.ibox-name').getBoundingClientRect();
            return { nameX: l.left + l.width / 2, nameY: l.top + l.height / 2,
                     edgeX: b.left + 3, edgeY: b.top + 3 };
        }""")
        page.mouse.click(spot["nameX"], spot["nameY"])
        page.wait_for_function("() => location.hash.includes('v=element')")
        assert "id=C15" in page.evaluate("() => location.hash")
        page.goto(url + "#v=usecase&uc=UC1")
        _settle(page)
        page.mouse.click(spot["edgeX"], spot["edgeY"])
        page.wait_for_timeout(700)
        seen = page.evaluate("""() => ({ hash: location.hash,
                                         card: !!document.querySelector('#panel .ecard[data-id]') })""")
        assert "v=usecase" in seen["hash"] and "node%3AC15" in seen["hash"], seen
        assert seen["card"], "the box around the name still selects and shows its card"
        assert not page.js_errors, page.js_errors


def test_hovering_a_box_shows_its_card_with_a_line_to_it() -> None:
    """A reader scanning a walk wants to know what each box is. Hover answers, with the same card a
    click pins and the same leader line pointing at the box — and leaving takes it away again.

    Only a browser can see this: the card's visibility is decided by one rule after the HTML is written,
    and writing the HTML alone left the card rendered but hidden."""
    with _served() as url, _page(url + "#v=usecase&uc=UC1") as page:
        _settle(page)
        spot = page.evaluate("""() => {
            const n = [...document.querySelectorAll('#diagram g.node')].find((x) => /C15/.test(x.id));
            const c = n.querySelector('.ibox-name').getBoundingClientRect();
            return { x: c.left + c.width / 2, y: c.top + c.height / 2 };
        }""")
        page.mouse.move(spot["x"], spot["y"])
        page.wait_for_timeout(600)
        seen = page.evaluate("""() => ({
            card: !document.getElementById('panel').hidden,
            line: !document.getElementById('callout').hasAttribute('hidden'),
        })""")
        assert seen == {"card": True, "line": True}, seen
        page.mouse.move(4, 4)
        page.wait_for_timeout(600)
        assert page.evaluate("() => document.getElementById('panel').hidden"), \
            "leaving puts back what was there — nothing was selected, so nothing shows"
        assert not page.js_errors, page.js_errors


def test_opening_the_source_narrows_what_you_see_of_the_interfaces_picture_not_the_picture() -> None:
    """Every other diagram keeps its size when the source column opens, and the area around it shrinks.
    The Interfaces picture alone re-laid itself out: measured on mcpolis, 1060px wide became 890px the
    moment the column opened, squeezing the gutters the wires need room to turn in.

    Its wrapper already scrolled, so a floor under the stage was all it took. The floor is the five
    tracks at rest: two 320px cards, two 130px gutters, a 160px hub.

    ONLY while the column is open — the picture is also built to FIT a narrow window on its own, which
    `test_what_we_own_holds_the_product_and_our_surfaces_and_keeps_its_distance` asserts down to 1024.
    An unconditional floor made that window scroll for no reason. The column is what must not resize
    the drawing; a small screen still gets a drawing sized for it."""
    with _served_map(_two_sided_interfaces()) as url, _page(url + "#v=interfaces") as page:
        _settle(page)
        page.evaluate("""() => { if (document.body.classList.contains('code-hidden'))
                                   document.getElementById('srcrail').click(); }""")
        page.wait_for_timeout(1200)
        opened = page.evaluate("""() => {
            const s = document.getElementById('ifdstage'), w = s.closest('.ifd-wrap');
            const wrap = w.parentElement, cs = getComputedStyle(w);
            return { stage: Math.round(s.getBoundingClientRect().width),
                     scrolls: w.scrollWidth > w.clientWidth + 1,
                     board: { radius: cs.borderTopLeftRadius, border: cs.borderTopWidth },
                     shadeRight: wrap.classList.contains('hfade-on-r'),
                     shadeLeft: wrap.classList.contains('hfade-on-l') };
        }""")
        page.evaluate("() => { const c = document.getElementById('cvclose'); if (c) c.click(); }")
        page.wait_for_timeout(1200)
        closed = page.evaluate("""() => Math.round(
            document.getElementById('ifdstage').getBoundingClientRect().width)""")
        assert opened["stage"] == closed, f"the picture must not resize: {opened['stage']} vs {closed}"
        assert opened["scrolls"], "…and what you see of it scrolls instead"
        # …in the SAME board the Happy Path and a feature's timeline scroll in: a rule, a radius, and
        # the edge shade that says there is more that way. Only the right one, having not scrolled yet.
        assert opened["board"] == {"radius": "10px", "border": "1px"}, opened
        assert opened["shadeRight"] and not opened["shadeLeft"], opened
        assert not page.js_errors, page.js_errors
