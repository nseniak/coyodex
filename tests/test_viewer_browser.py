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
