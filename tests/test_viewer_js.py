#!/usr/bin/env python3
"""Syntax gate for the hand-maintained viewer frontend bundle.

viewer.js is a large, hand-edited vanilla-JS file and the repo has no JS test harness, so a stray
syntax error (an unbalanced brace, a dangling edit) would ship silently and break the whole viewer.
`node --check` parses the file without executing it — a cheap, deterministic regression guard. Skips
when node isn't installed (e.g. a Python-only CI image), so it never turns into a spurious failure.

Conventions: top-level test functions, no classes/fixtures.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

VIEWER_DIR = Path(__file__).resolve().parent.parent / "tools" / "coyodex" / "viewer"


def _node_check(js_path: Path) -> None:
    """`node --check` on a COPY named `.mjs`, never on the file in place.

    viewer.js is an ES module (top-level await, no bundler), but node decides CJS-vs-ESM from the
    nearest package.json, and the repo has none. Checked in place, node parses it as CommonJS, hits
    the top-level `await` first, and reports THAT — so any real syntax error further down is masked by
    a line that has been fine for a year. Measured: a duplicate `const` on line 5018 was reported as
    an await error on line 156. The `.mjs` suffix removes the guessing."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not installed — skipping viewer JS syntax gate")
    assert js_path.exists(), f"expected {js_path} to exist"
    with tempfile.TemporaryDirectory() as td:
        probe = Path(td) / (js_path.stem + ".mjs")
        probe.write_text(js_path.read_text(encoding="utf-8"), encoding="utf-8")
        result = subprocess.run([node, "--check", str(probe)], capture_output=True, text=True)
    assert result.returncode == 0, f"{js_path.name} failed `node --check`:\n{result.stderr}"


def test_viewer_js_parses() -> None:
    _node_check(VIEWER_DIR / "viewer.js")


def _run_js(snippet: str) -> str:
    """Run a snippet against the REAL `esc` / `mdInline` / `mdRefs` lifted out of viewer.js.

    The frontend has no module system (one hand-edited script, loaded whole), so the only way to
    exercise a function of it is to slice its source and evaluate that. Sliced by the marker lines
    around each definition, so a rename fails loudly here instead of silently testing nothing."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not installed — skipping viewer JS behaviour gate")
    js = (VIEWER_DIR / "viewer.js").read_text(encoding="utf-8")
    start = js.index("const esc = (s) =>")
    end = js.index("let mode = HAS_DIFF")
    lifted = js[start:end]
    assert "const mdRefs" in lifted, "mdRefs moved out of the lifted region — fix the slice"
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "probe.mjs"
        f.write_text(lifted + "\n" + snippet, encoding="utf-8")
        r = subprocess.run([node, str(f)], capture_output=True, text=True)
    assert r.returncode == 0, f"probe failed:\n{r.stderr}"
    return r.stdout.strip()


def test_authored_prose_never_shows_a_raw_element_id() -> None:
    """The rule the whole viewer follows — ids stay internal, names go on screen — enforced where it
    was actually broken: the recorded lines, which are KEYED by id, are the only prose that carries
    them. This is a behavioural gate, not a source read: it runs the real function.

    It also pins the three things that must NOT be rewritten — an id inside a code span (the author
    is quoting), an id inside a longer token (a `path:line` anchor must stay copyable), and an id the
    map does not define (leave it exactly as written rather than half-translate it)."""
    refs = {"C54": {"id": "C54", "name": "Request Context Middleware", "node": "C54"},
            "R3": {"id": "R3", "name": "Site visitor", "node": None}}
    body = ("C54, R3: an operator surface. See `C54` and src/C54_handler.py:42 for the detail; "
            "C99 is long gone.")
    out = _run_js(f"""
const refs = {json.dumps(refs)};
const html = mdRefs({json.dumps(body)}, refs);
const text = html.replace(/<[^>]+>/g, '');
console.log(JSON.stringify({{ html, text }}));
""")
    got = json.loads(out)
    # every id the server resolved is GONE from what the reader sees, replaced by its name
    for eid, ref in refs.items():
        assert ref["name"] in got["text"], f"{eid} did not render as its name"
    assert "C54, R3:" not in got["text"], "the recorded line still opens with raw ids"
    # …and the three exceptions survive verbatim
    assert "<code>C54</code>" in got["html"], "an id inside a code span was rewritten"
    assert "src/C54_handler.py:42" in got["text"], "an id inside a longer token was rewritten"
    assert "C99 is long gone" in got["text"], "an undefined id was not left as written"


def test_flow_step_keeps_relationship_navigation_on_the_arrow() -> None:
    """The pane stays step-specific; its arrow owns structural relationship navigation."""
    js = (VIEWER_DIR / "viewer.js").read_text()
    start = js.index("function flowStepInfoHtml(uc, i, numbered)")
    end = js.index("\n// One actor's card", start)
    flow_step = js[start:end]

    assert 'class="flowpairref"' not in flow_step
    assert 'class="endpoints"' not in flow_step
    assert "showPairEdges(pairEdges)" not in flow_step
    assert "Rides arrow" not in flow_step
    assert "ridesref" not in flow_step
    assert 'class="flowref"' not in flow_step


def test_flow_arrows_locate_all_backbone_relationships_in_structural_views() -> None:
    js = (VIEWER_DIR / "viewer.js").read_text()
    locate = js[js.index("function relationshipLocateTarget"):js.index("function decorateActionIcons")]
    sequence = js[js.index("function bindFlow(uc)"):js.index("// --- use-case flow step player")]
    flow_map = js[js.index("function bindFlowMap(uc)"):js.index("function syncEnvPicker")]
    edge_action = js[js.index("function bindEdgeActionIcon"):js.index("// Give an edge's visible path")]

    assert "selCover: bundleAtoms(pairEdges)" in locate
    assert "kind: 'subsystem'" in locate and "kind: 'edge'" in locate
    assert "kind: 'domain'" in locate and "kind: 'domedge'" in locate
    assert "kind: 'bridge'" in locate
    assert "const direct = COMP_LOOKUP[srcId + '>' + dstId] || []" in locate
    assert "direct.length" in locate
    assert "relationshipLocateTarget(dstId, srcId)" in locate
    assert "kind: 'locate'" in locate
    assert "title: 'Locate in ' + tab" in locate
    assert "relationshipLocateAction(st.srcId, st.dstId)" in sequence
    assert "relationshipLocateAction(m[1], m[2])" in flow_map
    assert "const action = { kind: 'drill'" not in edge_action
    assert "action || (onDrill ? { kind: 'drill'" in js
    assert "'edge:' + e.src + '>' + e.dst + ':' + m[3]" in js


def test_only_direct_diagram_clicks_pin_selection_action_icons() -> None:
    js = (VIEWER_DIR / "viewer.js").read_text()
    selection = js[js.index("function selApply"):js.index("// The full click-gesture handler")]
    sequence = js[js.index("function bindFlow(uc)"):js.index("// --- use-case flow step player")]
    edge_action = js[js.index("function bindEdgeActionIcon"):js.index("// Give an edge's visible path")]
    glow_edge = js[js.index("function glowEdge"):js.index("// Synthetic (aggregated")]
    hp_glow = js[js.index("function hpGlow"):js.index("// Glow a set of elements")]
    flow_map = js[js.index("function bindFlowMap(uc)"):js.index("function syncEnvPicker")]

    assert "d.glow(!!d.revealAction)" in selection
    assert "function selAdd(scene, desc, revealAction = false)" in selection
    assert "revealAction: !!revealAction" in selection
    assert "selToggle(scene, desc, true)" in selection
    assert "selReplace(scene, desc, true)" in selection
    assert "function selRevealsAction" in selection
    assert "selRevealsAction(scene, selKey)" in sequence
    assert "glowEdge(p, label, revealAction = true)" in glow_edge
    assert "p._actionIcon._selected = !!revealAction" in glow_edge
    assert "hpGlow(el, revealAction = true)" in hp_glow
    assert "el._actionIcon._selected = !!revealAction" in hp_glow
    assert "glow: (reveal) => glowEdge" in flow_map
    assert "flowPlay.showLocate" not in js
    assert "showLocate:" not in js
    assert "const pinOnSelect" not in edge_action


def test_node_use_cases_are_grouped_by_capability_without_a_serves_row() -> None:
    js = (VIEWER_DIR / "viewer.js").read_text()
    css = (VIEWER_DIR / "viewer.css").read_text()
    trace = js[js.index("function tracedUseCasesFor"):js.index("// The \"Triggered by\"")]
    detail = js[js.index("function nodeDetailBodyHtml"):js.index("function bindNodeDetailHandlers")]

    assert "isAncestorOf(id, eid)" in trace
    assert "UC_NODES.filter((uc) => set.has(uc.id))" in trace
    assert "CAP_OF_UC[uc.id]" in trace
    assert 'class="used-cap-group"' in trace
    assert 'class="used-uc-list"' in trace
    assert "No traced use case reaches it." in trace
    assert "servesHtml" not in js
    assert "${usedInHtml(id)}" in detail
    assert ".used-cap-name" in css
    assert ".serves-chip" not in css


def test_flow_map_dims_other_numbers_on_a_selected_multi_step_arrow() -> None:
    js = (VIEWER_DIR / "viewer.js").read_text()
    start = js.index("function flowMapPaintStepLabel(label, stepIdx, current)")
    end = js.index("\n// The steps riding one arrow", start)
    label_code = js[start:end]

    assert "stepIdx.length > 1 && stepIdx.includes(current)" in label_code
    assert "active && i !== current" in label_code
    assert "flow-other-step" in label_code
    assert "createElement('strong')" not in label_code
    assert "flowPlay.active && i >= 0" in label_code
    assert "pairSelected" not in label_code
    assert "const current = stepSelected" in label_code
    assert "flowMapRefreshStepLabels();" in js[js.index("function selApply"):js.index("function selAdd")]
    assert "mapArrows: arrows" in js


def test_flow_map_arrows_reuse_complete_sequence_step_info() -> None:
    js = (VIEWER_DIR / "viewer.js").read_text()
    step = js[js.index("function flowStepInfoHtml"):js.index("// One actor's card")]
    pair = js[js.index("function showFlowPair"):js.index("function bindFlowMap")]
    binding = js[js.index("function bindFlowMap"):js.index("function syncEnvPicker")]

    assert "flowStepInfoHtml(uc, i, false)" in step
    assert "bindFlowStepInfo(panel, uc, i)" in step
    assert "if (steps.length === 1) { showFlowStep(uc, steps[0].i); return; }" in pair
    assert "flowStepInfoHtml(uc, i, true)" in pair
    assert 'class="flow-step-separator"' in pair
    assert "Steps on this arrow" not in pair
    assert "flowstepref" not in pair
    assert "if (on.length === 1)" in binding
    assert "else showFlowPair" in binding
    assert "flowSyncCur(on[0].i); showFlowPair" not in binding


def test_flow_map_boxes_locate_the_element_in_its_structural_diagram() -> None:
    js = (VIEWER_DIR / "viewer.js").read_text()
    start = js.index("function locateActionFor(id)")
    end = js.index("\nfunction clearFocus", start)
    locate_code = js[start:end]

    assert "const t = selectTargetFor(id)" in locate_code
    assert "!t || !t.selectId" in locate_code  # actor aliases have no structural home
    assert "kind: 'locate'" in locate_code
    assert "const tab = stateTitle({ kind: topView(t.state.kind, t.state.id) })" in locate_code
    assert "title: 'Locate in ' + tab" in locate_code
    assert "sel: 'node:' + t.selectId" in locate_code
    assert "pendingCenter = t.selectId" in locate_code
    assert "s.kind === 'usecase' && FLOW_VIEW === 'map'" in locate_code
    assert "locating ? locateActionFor(id) : primaryActionFor(id)" in locate_code
    assert "if (locate && isDrillClick(ev)) { locate.run(); return; }" in js
    assert "action-icon is-' + action.kind" in js
    assert "Lucide LocateFixed" in js
    assert "ACTION_ICON_TIP_DELAY_MS = 250" in js
    assert "scheduleActionIconTip(actionLabel, ev)" in js
    assert "icon.setAttribute('aria-label', actionLabel)" in js
    assert "createElementNS(SVGNS, 'title')" not in js[js.index("function addActionIcon"):js.index("function addLabelActionIcon")]


def test_all_action_icons_render_in_the_foreground_overlay() -> None:
    js = (VIEWER_DIR / "viewer.js").read_text()
    action = js[js.index("function addActionIcon"):js.index("function addLabelActionIcon")]
    label = js[js.index("function addLabelActionIcon"):js.index("function showIcon")]
    edge = js[js.index("function bindEdgeActionIcon"):js.index("// Give an edge's visible path")]

    assert "svg.appendChild(g)" in js[js.index("function ensureIconOverlay"):js.index("const ACTION_ICON_TIP_DELAY_MS")]
    assert "svg.querySelector(':scope > g')" not in js[js.index("function ensureIconOverlay"):js.index("const ACTION_ICON_TIP_DELAY_MS")]
    assert "iconOverlay.parentNode.appendChild(iconOverlay)" in js
    assert "const parent = iconOverlay || host || el" in action
    assert "const parent = host || iconOverlay || el" not in action
    assert "const parent = iconOverlay || host" in label
    assert "const bridgeParent = iconBridgeOverlay || parent" in label
    assert "bridgeParent.appendChild(bridge)" in label
    assert "host.insertBefore(bridge, label)" not in label
    assert "pointToHostSpace(icon.parentNode, icon._anchor.x" in label
    assert "b.setAttribute('height', String(10 * inv))" in label
    assert "const parent = iconOverlay || host" in edge
    assert "clientToLocal(parent, ev.clientX, ev.clientY)" in edge


def test_use_case_flow_opens_as_map_and_lists_map_first() -> None:
    js = (VIEWER_DIR / "viewer.js").read_text()
    start = js.index("function syncFlowPicker(s)")
    end = js.index("\n// `flowMapToken`", start)
    picker = js[start:end]

    assert "let FLOW_VIEW = 'map'" in js
    assert "${btn('map', 'Map')}${btn('sequence', 'Sequence')}" in picker
    assert picker.index("btn('map', 'Map')") < picker.index("btn('sequence', 'Sequence')")


def test_flow_player_suspends_and_resumes_within_one_visit() -> None:
    js = (VIEWER_DIR / "viewer.js").read_text()
    start = js.index("function flowCounter()")
    end = js.index("\n// A flow step's side panel", start)
    player = js[start:end]

    assert "active ? i + 1 : '\\u2013'" in player
    assert "flowprev.disabled = !active" in player
    assert "flownext.disabled = false" in player
    assert "flownext.title" not in player
    assert "flowPlay.active = false" in player
    assert "flowGoto(flowPlay.cur >= 0 ? flowPlay.cur : 0)" in player
    assert "flowResume = null" in player
    assert "if (switched && flowPlay.active) { flowGoto(flowPlay.cur); return; }" in player
    assert "flowResume = { cur: flowPlay.cur, active: flowPlay.active }" in js
    assert "flowSuspend();" in js[js.index("function selClear"):js.index("function selReplace")]


def test_flow_player_state_is_captured_and_restored_with_history() -> None:
    js = (VIEWER_DIR / "viewer.js").read_text()
    capture = js[js.index("function captureViewState"):js.index("function pushContentPoint")]
    transition = js[js.index("function driveTransition"):js.index("async function runDrill")]
    html = (VIEWER_DIR / "viewer.html").read_text()

    assert "history[hi].flow = flowSnapshot()" in capture
    assert "flow: c.flow" in js[js.index("function pushContentPoint"):js.index("function go(state")]
    assert "restoreFlowSnapshot(to.flow)" in transition
    assert "const saved = switched || (s && s.flow)" in js
    assert "flowInit(s)" in js
    assert 'id="flowprev" aria-label="Previous step"' in html
    assert 'id="flownext" aria-label="Next step"' in html
    assert 'title="Previous step' not in html
    assert 'title="Next step' not in html


def test_the_ui_does_not_name_internal_model_fields():
    """The viewer speaks the reader's language, not the model's.

    A panel that says "no `runs_in`" names a JSON field the reader never sees and cannot act on from
    the UI. Naming the field is right in `validate` — that output is FOR editing the map, and the
    codebase already draws this line ("Completeness is validate's job, where it comes with the
    specific ids to fix"). It is wrong on screen.

    Checks the rendered STRINGS only: reading `ep.runs_in` in code is how the data is used, and
    backtick-to-<code> markdown of AUTHORED map text is the map's own words, not ours."""
    js = (Path(__file__).resolve().parents[1] / "tools/coyodex/viewer/viewer.js").read_text()
    fields = ("runs_in", "no_call_site", "non_entity_types", "tests_note", "where_configured",
              "cadence_source", "tech_source", "subflow", "why_refs")
    offenders = []
    for i, line in enumerate(js.splitlines(), 1):
        code = line.split("//", 1)[0] if not line.lstrip().startswith("//") else ""
        if "<code>" not in code:
            continue
        for f in fields:
            if f"<code>{f}</code>" in code:
                offenders.append(f"{i}: {line.strip()[:90]}")
    assert offenders == [], "internal field name rendered in the UI:\n" + "\n".join(offenders)


def test_source_links_are_bound_by_delegation_not_per_render():
    """One listener per container, so a new panel writer cannot ship dead source buttons.

    Source buttons used to be wired by calling `wireSrcLinks(root)` after each render, which works
    only if every panel writer remembers. `showNode` — the pane shown for any selected element — did
    not, so a deployment unit's Environments row rendered its manifest anchors as buttons that did
    nothing when clicked. Delegation makes forgetting impossible rather than merely catchable."""
    js = (VIEWER_DIR / "viewer.js").read_text()
    code = [ln for ln in js.splitlines() if not ln.lstrip().startswith("//")]
    stale = [ln.strip() for ln in code if "wireSrcLinks" in ln]
    assert stale == [], ("per-render source-link wiring is back — it double-binds against the "
                         "delegated listener:\n" + "\n".join(stale))
    assert "closest('.srclink')" in js, "the delegated source-link listener is missing"
    # it must be attached to the STABLE panel host, not the `panel` binding, which is temporarily
    # re-pointed at individual cards while a multi-selection renders.
    assert "[PANEL_HOST, diagram].forEach" in js


def test_the_section_index_is_ONE_component_used_by_every_card_list_tab() -> None:
    """The System tab had a pinned index — all sections at a glance, click to jump, the one you are
    in lit up — and the two other card-list tabs did not, though they have the same problem the
    moment a map has more categories than fit on a screen. A second copy per tab is three places for
    the sticky-offset maths to drift, so the bar is one component all three call."""
    js = (VIEWER_DIR / "viewer.js").read_text()
    assert "function tabIndexHtml(secs)" in js and "function bindTabIndex(wrap)" in js
    assert "function bindSysIndex" not in js and "sys-index" not in js   # the private copy is gone
    # ONE page still stacks several groups on one scroll and therefore still needs an index: the
    # use-case list. System and Rules stopped stacking when they became cards, so they index nothing —
    # a card grid IS the index of what is behind it. The component stays shared, not re-privatised.
    body = js[js.index("function renderUseCases("):js.index("\nfunction ", js.index("function renderUseCases(") + 10)]
    assert "tabIndexHtml(" in body and "bindTabIndex(" in body
    for fn in ("renderRules", "renderSystem"):
        gone = js[js.index(f"function {fn}("):js.index("\nfunction ", js.index(f"function {fn}(") + 10)]
        assert "tabIndexHtml(" not in gone, fn
    # One section indexes nothing — no bar rather than a bar with one chip.
    assert "if (!secs || secs.length < 2) return '';" in js


def test_the_pinned_index_sticks_to_the_wrappers_top_border() -> None:
    """`position: sticky; top: 0` inside a scrolling box resolves to the CONTENT edge, so the
    wrapper's 16px top padding stayed ABOVE the bar as a transparent strip — scrolling rows slid
    through it and the bar read as floating in the middle of the list. The padding moves onto the
    bar (only where there IS one) and negative side margins take it full-bleed, so nothing scrolls
    past above or beside it. Measured in the browser: gap 0, bar width == wrapper width."""
    css = (VIEWER_DIR / "viewer.css").read_text()
    # The padding-drop is now shared with every other wrap that holds a sticky line — see
    # test_no_scroll_wrapper_holds_a_sticky_line_below_its_own_top_padding for why they all need it.
    assert ".usecases-wrap:has(> .tab-index), .usecases-wrap.system-wrap, .glossary-wrap { padding-top: 0; }" in css
    bar = css[css.index(".usecases-wrap .tab-index {"):]
    bar = bar[:bar.index("}")]
    assert "position: sticky" in bar and "top: 0" in bar
    assert "margin: 0 -20px 12px" in bar and "padding: 12px 20px 10px" in bar


def test_the_scroll_spy_clears_the_sections_scroll_margin() -> None:
    """The spy lights the LAST section whose top is above a line just under the bar. That line has
    to clear the sections' own `scroll-margin-top`, or a section you just JUMPED to lands below the
    line and the chip that lights is the one ABOVE the one you clicked."""
    js = (VIEWER_DIR / "viewer.js").read_text()
    spy = js[js.index("const spy = () => {"):js.index("wrap.addEventListener('scroll', spy")]
    assert "getBoundingClientRect().bottom + 12" in spy
    css = (VIEWER_DIR / "viewer.css").read_text()
    assert "scroll-margin-top: calc(var(--tab-index-h) + 8px)" in css      # 8 < 12


def test_a_text_tab_remembers_where_it_was_scrolled_to() -> None:
    """The diagram tabs remember their camera twice over — per history point (back/forward lands
    exactly) and per view (a tab switch lands there too). The text tabs were left out only because
    they have no camera; the position matters just as much on a 96-rule list. Same two places,
    saving scrollTop instead of zoom."""
    js = (VIEWER_DIR / "viewer.js").read_text()
    assert "const scrollByView = {};" in js
    assert "function textScroller()" in js
    # ONE selector names every text tab's scroll container — Use Cases / Business logic / the rule
    # page / System / Tests share `.usecases-wrap`; Glossary and Data have their own.
    assert "'.usecases-wrap, .glossary-wrap, .dv-content'" in js
    capture = js[js.index("function captureViewState"):js.index("function pushContentPoint")]
    assert "history[hi].scroll = sc.scrollTop" in capture
    assert "scrollByView[stateKey(history[hi])] = sc.scrollTop" in capture
    # …and it survives a right-pane navigation, like every other field the restore reads.
    assert "scroll: c.scroll" in js[js.index("function pushContentPoint"):js.index("function go(state")]
    # Every text view restores it on the way out of render().
    assert js.count("restoreTextScroll(s") >= 7
    # Clicking the tab you are already ON is a reset — it drops the remembered spot, as it drops the
    # remembered camera.
    reset = js[js.index("function resetTab(view)"):js.index("function resetTab(view)") + 400]
    assert "delete scrollByView[stateKey(root)]" in reset


def test_an_explicit_jump_beats_a_remembered_scroll_position() -> None:
    """A cross-link naming a decision area, or the crumb walking back out of a rule, asks for a SPECIFIC
    place, and a remembered scroll offset must not undo it. That used to need an escape hatch, because
    the list stacked every area on one page and the link had to scroll to a section of it. An area is
    its own page now: there is nothing to scroll to, nothing to override, and the state's own offset is
    simply correct. The hatch goes with its only producer rather than sitting there unreachable."""
    js = (VIEWER_DIR / "viewer.js").read_text()
    assert "function restoreTextScroll(s) {" in js
    assert "restoreTextScroll(s, " not in js, "the escape hatch outlived its only producer"
    assert "const jumped = " not in js
    rules = js[js.index("function renderRules(s)"):js.index("\nfunction ", js.index("function renderRules(s)") + 10)]
    assert "scrollIntoView" not in rules


def test_no_tab_row_can_ever_clip_a_tab_out_of_reach() -> None:
    """Both tab rows were one nowrap flex row with `overflow:hidden`, so a pane too narrow for every
    tab silently amputated the last ones. Measured in the browser at a 1280px window: the Tests tab
    had ZERO visible width and could not be clicked, and Glossary was cut mid-word. A hidden tab is a
    view the reader cannot reach and has no way to discover, so buttons keep their natural width and
    the row wraps instead. Grouping does not retire this rule — a very narrow pane can still overflow
    a four-view sub row. The mode switch now sits INLINE after the view tabs rather than pushed to the
    far edge, so the sub row itself has to wrap too: otherwise the switch is the thing a narrow pane
    cuts off, and #stage hides its overflow. Measured at a 400px pane: the row grows to two lines and
    the switch drops onto the second, whole."""
    css = (VIEWER_DIR / "viewer.css").read_text()
    subrow = css[css.index("#stagesubrow {"): css.index("}", css.index("#stagesubrow {"))]
    assert "flex-wrap: wrap" in subrow
    assert "viewextra" not in css, "the header's mode slot is gone; the switch lives with its list"
    for row in ("#groupsw", "#viewsw"):
        rule = css[css.index(f"\n{row} {{") : css.index("}", css.index(f"\n{row} {{"))]
        assert "flex-wrap: wrap" in rule, row
        btn = css[css.index(f"\n{row} button {{") : css.index("}", css.index(f"\n{row} button {{"))]
        assert "flex: 0 0 auto" in btn and "white-space: nowrap" in btn, row


def test_every_view_declares_its_group_and_every_group_is_declared_once() -> None:
    """The grouping lives on the button it groups (`data-group`), so there is no second membership
    list to keep in step with the buttons. A view with no group would vanish from every row: its
    group tab would never light and its sub tab would never be shown."""
    html = (VIEWER_DIR / "viewer.html").read_text()
    js = (VIEWER_DIR / "viewer.js").read_text()
    buttons = re.findall(r'<button data-view="([a-z]+)" data-group="([a-z]+)">', html)
    views = re.findall(r'<button data-view="([a-z]+)"', html)
    assert len(buttons) == len(views), "a view button is missing its data-group"
    start = js.index("const VIEW_GROUPS = [")
    table = js[start : js.index("\n];", start)]
    declared = set(re.findall(r"\['([a-z]+)', '", table))
    assert {g for _, g in buttons} <= declared, "a button names a group VIEW_GROUPS does not declare"
    assert declared == {g for _, g in buttons}, "VIEW_GROUPS declares a group no view belongs to"


def test_an_empty_group_never_reaches_the_row_and_a_lone_view_draws_no_sub_tab() -> None:
    """Two ways the two-row switcher could lie. A group whose every view is gated off by THIS map's
    content would open onto nothing, so it is not built at all. And a group holding one view draws no
    sub tabs, because a lone chip repeating the group name above it says nothing — the strip still
    renders at full height, so opening that group does not shunt the diagram up and back down."""
    js = (VIEWER_DIR / "viewer.js").read_text()
    boot = js[js.index("for (const [gid, label, question] of VIEW_GROUPS) {"):]
    assert "if (!views.length) continue;" in boot[: boot.index("\n}")]
    assert "const lone = groupViews(tg).length < 2;" in js
    assert "b.hidden = lone || b.dataset.group !== tg;" in js
    css = (VIEWER_DIR / "viewer.css").read_text()
    sub = css[css.index("#stagesubrow {"): css.index("}", css.index("#stagesubrow {"))]
    assert "min-height" in sub, "an empty sub row must still reserve its height"


def test_a_map_with_no_features_keeps_the_flat_use_case_list() -> None:
    """The overview cards are built from the map's capabilities. A map that records none would land on
    an empty screen, so that tab falls back to the flat use-case list it has always shown. The list is
    ONE function for every case — a feature's use cases, an actor's, or all of them — so the row
    markup, the Happy-Path pill, the diff badge and the flow click cannot drift between them."""
    js = (VIEWER_DIR / "viewer.js").read_text()
    assert "if (HAS_CAPABILITIES) renderOverview(); else renderUseCases();" in js
    assert "function renderUseCases(sel) {" in js
    assert ("renderUseCases(s.kind === 'actor' ? { actor: s.act } : { cap: s.cap, actor: s.act });"
            in js), "one feature's list, and a grid cell's, are the same renderer scoped differently"
    # In diff mode a card carries its members' change, or dropping the use cases one level down would
    # hide every "changed" badge behind a click.
    feat = js[js.index("function renderOverview() {"): js.index("\nfunction ", js.index("function renderOverview() {") + 10)]
    assert "g.ucs.some((x) => usecaseDiffState(x.id))" in feat


def test_features_shows_features_and_actors_own_their_own_drill() -> None:
    """"What does this product do?" and "what can this role do?" are different questions, and they had
    a view each AND a switch on one of them. So a tab named Features could show no feature, and the
    Actors view could not answer its own question without handing the reader to another tab: its cards
    drilled ACROSS into the Features view's actor axis.

    One question per view now. The switch is gone, the Features view has one axis, and an actor's use
    cases sit under Actors, where the cards that open them are."""
    js = (VIEWER_DIR / "viewer.js").read_text()
    assert "UC_GROUP_BY" not in js and "ucGroupBy" not in js, "the axis is gone, not defaulted"
    assert "bindOverviewAxis" not in js and "uc-groupby" not in js
    assert "if (kind === 'actor') return 'actors';" in js, "an actor's page lives under its own view"
    over = js[js.index("function renderOverview() {"): js.index("\nfunction ", js.index("function renderOverview() {") + 10)]
    # Two words for a capability, then three: `Category`, then `Capability` beside a tab already
    # saying Features. Both were the label of a switch that should not have existed.
    assert "'Category'" not in js and "Features grouped by" not in js
    assert "'grid'" not in over, "the matrix setting is gone, not hidden"
    assert "renderRoleGrid" not in js
    # One builder, one shape: the grid variant existed only for the Features view's actor axis.
    actors = js[js.index("function renderActors() {"): js.index("\nfunction ", js.index("function renderActors() {") + 10)]
    assert "actorCardsHtml()" in actors
    # The drill stays inside the Actors view now.
    opener = js[js.index("function openActor(id) {"): js.index("\nfunction ", js.index("function openActor(id) {") + 10)]
    assert "go({ kind: 'actor', act: n.name });" in opener and "UC_GROUP_BY" not in opener
    # Each page sits under ITS OWN view, so the two trails differ from their first word.
    assert "if (s.kind === 'actor') return [{ kind: 'actors' }, { kind: 'actor', act: s.act }];" in js
    assert ("if (s.kind === 'capability') return [{ kind: 'usecases' }, "
            "{ kind: 'capability', cap: s.cap, act: s.act }];") in js
    assert "kind === 'actor'" in js[js.index("function topView(kind, id) {"):]

def test_every_state_field_survives_a_right_pane_navigation() -> None:
    """`pushContentPoint` rebuilds the current state field by field so opening a file keeps the screen
    you are on. Maintained by hand it dropped a field three times running (`store`/`entity`, then
    `blk`/`br`, then `cap`/`act`), and the failure is silent and sticky: the crumb keeps naming the
    level you were on while the pane renders the level ABOVE it, back/forward preserves the corrupted
    point, and the tab remembers it. So the list is derived from what `stateKey` actually reads."""
    js = (VIEWER_DIR / "viewer.js").read_text()
    key = js[js.index("function stateKey(s) {"): js.index("\n}", js.index("function stateKey(s) {"))]
    read = set(re.findall(r"s\.([a-zA-Z]+)", key)) - {"kind"}
    decl = js[js.index("const STATE_FIELDS = ["):]
    declared = set(re.findall(r"'([a-zA-Z]+)'", decl[: decl.index("]")]))
    assert read == declared, f"stateKey reads {read - declared}, STATE_FIELDS declares {declared - read}"
    push = js[js.index("function pushContentPoint(content) {"): js.index("\n}", js.index("function pushContentPoint(content) {"))]
    assert "for (const f of STATE_FIELDS)" in push


def test_a_use_cases_crumb_names_the_card_it_was_listed_on() -> None:
    """A use case has TWO homes — its feature, and every actor who drives it — and the reader's own
    path picks one. The row carries the actor whose list it was opened from, so the trail runs through
    Actors; otherwise it runs through the feature. A use case in no feature still gets a card crumb, or
    that drill is the only one in the viewer no breadcrumb can undo.

    A THIRD case went with the axis: the trail used to GUESS an actor from a global switch for a use
    case reached some other way (a search, a Happy Path step), which put a card the reader never opened
    into their trail."""
    js = (VIEWER_DIR / "viewer.js").read_text()
    anc = js[js.index("if (s.kind === 'usecase') {"):]
    anc = anc[: anc.index("\n  }")]
    assert "if (s.act) return [{ kind: 'actors' }, { kind: 'actor', act: s.act }," in anc
    assert "CAP_OF_UC[s.uc] ? CAP_OF_UC[s.uc].id : '-'" in anc
    assert "actorGroupOf" not in js, "no guessing an actor the reader never chose"


def test_a_feature_found_by_search_lands_on_its_card() -> None:
    """A feature is DRAWN as no box anywhere — it groups behaviour — so nothing can be selected for it.
    Without a case of its own it fell to the default and opened Dependencies, which is a confident wrong
    answer to a search hit the index itself labels a feature. Its home view is the card list that shows
    it, so a hit lands there and the card is scrolled to and ringed: the card-list half of "show in
    context", where a diagram would select and centre a box. An actor resolves the same way."""
    js = (VIEWER_DIR / "viewer.js").read_text()
    target = js[js.index("function selectTargetFor(id) {"):
                js.index("\nfunction ", js.index("function selectTargetFor(id) {") + 10)]
    assert "return { state: { kind: 'usecases' }, selectId: null, flashId: id };" in target
    assert "return { state: { kind: 'actors' }, selectId: null, flashId: id };" in target
    # The flash survives the navigation: it is stashed, and consumed by the render that draws the card.
    assert "pendingFlash = t.flashId;" in js
    assert "function applyPendingFlash() {" in js and "flashCard(id);" in js
    assert "if (cur0 && stateKey(cur0) === stateKey(t.state)) { flashCard(t.flashId); return; }" in js

def test_a_use_case_named_by_two_roles_is_listed_under_both() -> None:
    """Either named role can start it, so both cards must show it. Filing it under the first hid it
    from the other; giving the pair its own group drew a third card that read as a bug ("Organization
    admin (30)" beside "Organization admin and Team member (1)"). The group sizes therefore overlap
    and no longer sum to the use-case count, which is honest for the question a group answers.
    The crumb has to survive that: the row carries the actor whose list it was opened from, or a
    recomputed group could send the reader back to a list they never opened."""
    js = (VIEWER_DIR / "viewer.js").read_text()
    body = js[js.index("function actorGroups() {"): js.index("\nfunction ", js.index("function actorGroups() {") + 10)]
    assert "for (const [key, title, role] of entries)" in body, "a use case must file under EVERY actor"
    assert "byActor[key].ucs.push(n)" in body
    # One undeclared name still sends the whole use case to Other: a half-known pair has no per-role home.
    assert "known ? names.map((nm, i) =>" in body and "[[OTHER, 'Other', null]]" in body
    assert "(id) => go({ kind: 'usecase', uc: id, act: oneActor })" in js


def test_the_group_by_switch_and_the_slot_it_lived_in_are_both_gone() -> None:
    """It moved twice — a header strip of its own, then beside the view tabs, then down with the cards —
    and each move made it a smaller problem without making it the right thing. It switched between
    features and actors on a view named Features, and both already had a view of their own.

    The header slot it once lived in went first, and stays gone: a slot that exists to host one control
    is chrome pretending to be a feature."""
    js = (VIEWER_DIR / "viewer.js").read_text()
    html = (VIEWER_DIR / "viewer.html").read_text()
    assert "viewextra" not in js and "viewextra" not in html
    assert "switchHtml" not in js and "data-gb" not in js
    css = (VIEWER_DIR / "viewer.css").read_text()
    assert ".uc-groupby" not in css, "the switch's styling goes with the switch"
    assert ".uc-seg" in css, "…but the segmented control it shaped is still worn by the Happy Path"

def test_the_breadcrumb_starts_under_the_active_tabs_label() -> None:
    """The alignment IS the design. The view row pads 10px and each tab pads 7px inside that, so the
    breadcrumb's 17px left padding lands its first segment exactly under the active tab's label — the
    path reads as starting from the tab it belongs to, rather than floating at the page edge."""
    css = (VIEWER_DIR / "viewer.css").read_text()
    sub = css[css.index("#stagesubrow {"): css.index("}", css.index("#stagesubrow {"))]
    assert "padding: 0 10px" in sub
    tab = css[css.index("#viewsw button {"): css.index("}", css.index("#viewsw button {"))]
    assert "padding: 8px 7px 6px" in tab
    hint = css[css.index("\n.hint {"): css.index("}", css.index("\n.hint {"))]
    assert "padding: 6px 12px 7px 17px" in hint, "10px row + 7px tab = 17px"

def test_the_active_view_is_underlined_and_the_active_group_is_a_pill() -> None:
    """Two tab rows one above the other, and if both mark their active item the same way the reader
    cannot tell which level they are reading. The group is a pale pill on a tinted ground; the view is
    an underline on white. The underline also does a second job: it is the mark the breadcrumb below
    lines up with."""
    css = (VIEWER_DIR / "viewer.css").read_text()
    grp = css[css.index("#groupsw button.active {"): css.index("}", css.index("#groupsw button.active {"))]
    assert "#e0e7ff" in grp and "#3730a3" in grp
    view = css[css.index("#viewsw button.active {"): css.index("}", css.index("#viewsw button.active {"))]
    assert "border-bottom-color: #6366f1" in view and "background" not in view

def test_no_control_outlives_the_view_that_drew_it() -> None:
    """A view's own controls are drawn by that view's renderer into the view's own content, so moving
    to another view cannot leave one behind: the content is replaced whole. This used to need a header
    slot cleared on every render, which is the mechanism the floating flow picker also needs — and that
    one still does, because it floats over the diagram rather than living in it."""
    js = (VIEWER_DIR / "viewer.js").read_text()
    render = js[js.index("  const fp = document.getElementById('flowpicker');"):]
    assert "if (fp) fp.hidden = true;" in render[:400], "the floating picker is still hidden up front"
    assert "uc-groupby-why" not in js
    assert "function viewQuestion(view) {" in js

def test_one_question_in_one_place_on_every_view() -> None:
    """A view's question is the same sentence at every depth inside that view, read from ONE table by
    the top view, so it is a property of the VIEW and can never change as the reader drills. Where it is
    DRAWN has moved five times: the info pane (only diagrams had one, and it vanished on the first
    click), the first block of the page (read as a caption, and each page began inventing its own),
    beside the view tabs (upright at tab size, it read as a fifth disabled tab), the trail row beside the
    page title, and then two places at once — beside the title on a diagram, leading the page on prose.

    Two places was the mistake this fixes. One sentence looked like two different things depending on
    which tab you were on: 12.5px hung off an em dash next to a diagram's title, 14px on its own line
    over a page of cards. Nothing about a diagram or a page explained the difference, and beside the
    title it read as chrome ABOUT the page rather than as the page's own opening words.

    It is one line under the header block now, on every view: the content's own text size, the content's
    own left edge and reading cap, italic because nothing else in this app is. Below the header's shadow,
    so it belongs to the content; outside the content's scroll, so it can never become a caption for
    whichever block ends up under it — which is what the spec undid.

    Shown ONLY on the view's own landing screen, which is exactly a one-item trail: every trail starts at
    its view. One level in, the reader has chosen something and is past asking what the view is for."""
    js = (VIEWER_DIR / "viewer.js").read_text()
    html = (VIEWER_DIR / "viewer.html").read_text()
    css = (VIEWER_DIR / "viewer.css").read_text()
    # ONE element, and the trail row is back to carrying nothing but the trail.
    assert "viewq" not in js and "viewq" not in html, "the second copy is deleted, not hidden"
    assert "#viewq" not in css
    crumbrow = html[html.index('<nav class="hint" id="crumbrow"'):
                    html.index("</nav>", html.index('<nav class="hint" id="crumbrow"'))]
    assert 'id="crumb"' in crumbrow and 'id="pageq"' not in crumbrow, "the trail row is the trail alone"
    assert html.index('<p id="pageq" hidden></p>') > html.index('id="crumbrow"'), "the question is below the header"
    assert html.index('<p id="pageq" hidden></p>') < html.index('<div id="diagwrap">'), "…and above the content"
    chrome = js[js.index("function renderChrome(s) {"):
                js.index("\nfunction ", js.index("function renderChrome(s) {") + 10)]
    assert "const q = chain.length === 1 ? viewQuestion(tv) : '';" in chrome, \
        "a one-item trail IS the view's own landing screen"
    assert "pageq.textContent = q;" in chrome and "pageq.hidden = !q;" in chrome
    pq = css[css.index("#pageq {"): css.index("}", css.index("#pageq {"))]
    assert "font-size: 14px" in pq, "the content's own text size, not the trail row's 12.5px"
    assert "font-style: italic" in pq
    assert "padding: 14px 20px 0" in pq, "the content's own left edge"
    assert "#pageq::before" not in css, "no dash on a sentence with no title to join"
    intro = js[js.index("function viewIntroHtml(view) {"):
               js.index("\nfunction ", js.index("function viewIntroHtml(view) {") + 10)]
    assert "viewQuestion" not in intro

def test_the_header_block_casts_a_shadow_so_it_reads_as_fixed() -> None:
    """The tab rows and the trail stay put while everything under them scrolls, pans and zooms. A
    hairline alone did not say so: it read as one more divider in a page full of them, and on a diagram
    the shapes simply slid under it with nothing to mark the boundary they passed.

    So the block casts a shadow onto whatever passes beneath it. Everything below that shadow is content
    — the view's question included, which is exactly why the question left the trail row."""
    css = (VIEWER_DIR / "viewer.css").read_text()
    head = css[css.index("#stagehead {"): css.index("}", css.index("#stagehead {"))]
    assert "box-shadow" in head, "the fixed block has to say it is fixed"
    assert "z-index" in head, "…and sit above what passes under it"

def test_a_page_about_one_element_says_what_it_is_beside_its_name() -> None:
    """A card puts an element's name and its pills on ONE line. Its own page split them across two rows
    with a rule between, so the page drew the element in a shape no card uses. Measured over the three
    maps: of the 1189 pages whose last breadcrumb item is one element, 796 drew a pill block, and on 629
    of them (every entity, component and process) that block held ONE word and nothing else — a 48px
    strip saying `entity` between the page's title and its first sentence.

    The pills now ride the breadcrumb after the name, and the block is not drawn when nothing is left in
    it. The breadcrumb's last item IS the page's title, so this is the name and its pills on one line,
    exactly as a card reads.

    THE SAME PILLS THE CARD SHOWS, from `cardFacts` — its type, and the few extras its type earns. Not
    the page's full detail: a dependency's card says `dependency` and `service`, while its page also
    records a purpose bucket and the roles derived from its incoming edges. Five words hung off a trail
    is a wall rather than a trail, so those two stay on the page, below.

    EVERY page about one element, diagram or prose. A drilled diagram was excluded for one round, on the
    grounds that its card already floats over the drawing — but that card can be closed and moved, and
    once it is, the page said nothing about what it was showing. `Features › Organizations and team ›
    Create an organization` never said the last item was a use case, while every other page of the trail
    did. One rule with no exception beats a rule the reader has to learn the edge of.

    A page about a PAIR (an arrow, a bridge) or a FOLD (Libraries, a dependency bucket) is not about one
    element and gets nothing: there is no card to read, and a fold's stored kind is a way of drawing
    rather than a word the map records.

    Plain text, never a control. Clicking a type pill means "show this in context", and the context of
    the page you are already on is the page you are already on."""
    js = (VIEWER_DIR / "viewer.js").read_text()
    css = (VIEWER_DIR / "viewer.css").read_text()
    which = js[js.index("function pageElementId(s) {"):
               js.index("\n}", js.index("function pageElementId(s) {"))]
    assert "TEXT_PAGES" not in which, "a drilled diagram is a page about one element too"
    for kind in ("element", "capability", "rule", "rules", "actor",
                 "usecase", "subsystem", "domsub", "deploymentUnit"):
        assert f"'{kind}'" in which, kind
    for pair in ("edge", "domedge", "bridge", "depedge", "libs", "bucketfold"):
        assert f"'{pair}'" not in which, f"{pair} is a pair or a fold, not one element"
    pills = js[js.index("function crumbPillsHtml(id) {"):
               js.index("\n}", js.index("function crumbPillsHtml(id) {"))]
    assert "cardFacts(id)" in pills, "the same pills the card shows, from the same function"
    assert "<button" not in pills, "plain text: the pill's destination is the page you are on"
    assert "crumbPillsHtml(pageElementId(s))" in js, "drawn on the LAST crumb, which is the page's title"
    # …and the body no longer draws what the trail carries.
    extra = js[js.index("function kindPillsExtra(n) {"):
               js.index("\n}", js.index("function kindPillsExtra(n) {"))]
    assert "n.kind !== 'dep'" in extra, "only a dependency has axes its card does not carry"
    assert ".filter((w) => w !== kind)" in extra, \
        "a role whose word IS the kind says nothing twice — 32 of the 153 dependencies"
    assert "extra ? `<div class=\"page-hero\">" in js, "no hero at all when nothing is left in it"

def test_a_text_view_has_no_selection_card_and_a_diagram_only_has_one_when_it_says_something() -> None:
    """Per the spec a card list, a card grid and a details page carry no info pane: a pane beside a page
    of prose only repeated it, and it stole a third of the height from the content it described.

    A DIAGRAM no longer keeps a standing pane either. It was a fixed 300px band under every diagram,
    there whether or not anything was selected. Measured over 60 states on the three maps: with nothing
    selected it held 76px of content on four of the five views, and one selected shape held 67-184px, so
    about three quarters of it stood empty nearly all the time. The diagram was left with 447px of an
    860px window, which is 32% of the screen for the thing the page is about. It is now 752px.

    What you selected floats over the drawing instead, and `paneSync` is the ONE place that decides
    whether it is on screen: it is there when it has something to say and gone when it has not. Every
    caller just writes; nothing has to remember to show or hide.

    And a card belongs to the page on screen, so EVERY navigation starts with no card: `syncInfoPane`
    clears it before the page renders, and the page puts one back only if it has one to show — its own
    subject, or the selection history is restoring. Enforced by construction rather than by a check per
    navigation path, because a card that outlives its page describes something no longer on screen.
    A transient render is exempt: those are the intermediate frames of a drill animation, and clearing on
    each one blinks the card off and back for one navigation the reader has not finished making."""
    js = (VIEWER_DIR / "viewer.js").read_text()
    css = (VIEWER_DIR / "viewer.css").read_text()
    assert "function syncInfoPane(_s, transient) {" in js
    assert "  if (transient) return;" in js, "a drill animation's own frames must not blink the card"
    assert "syncInfoPane(s, transient);" in js[js.index("async function render(sArg, transient) {"):][:1200]
    assert "showViewIntro" not in js, "one mechanism clears the card, not two"
    pages = js[js.index("const TEXT_PAGES = new Set(["):]
    pages = pages[: pages.index("]);")]
    for kind in ("actors", "usecases", "capability", "actor", "rules", "system", "glossary"):
        assert f"'{kind}'" in pages, kind
    assert "'hp'" not in pages and "'usecase'," not in pages, "a diagram is not a page of prose"
    # ONE rule, called from both paths that fill the card: a selection, and a page's own default.
    sync = js[js.index("function paneSync() {"): js.index("\n}", js.index("function paneSync() {"))]
    assert "PANEL_HOST.hidden = !has;" in sync
    assert 'id="panelclose"' in sync, "the close button is stamped from the one place, so no card is stuck open"
    assert 'id="panelbar"' in sync, "…and so is the bar it rides on"
    assert "paneSync();" in js[js.index("function renderSelPanel(scene) {"):
                                js.index("\n}", js.index("function renderSelPanel(scene) {"))]
    assert "paneSync();" in js[js.index("function applyDefaultPanel(s) {"):
                                js.index("\n}", js.index("function applyDefaultPanel(s) {"))]
    # It floats over the drawing, and #diagwrap is what it floats in.
    pane = css[css.index("#panel {"): css.index("}", css.index("#panel {"))]
    assert "position: absolute" in pane and "top: 12px" in pane and "right: 12px" in pane, \
        "top-right: #envpicker owns bottom-left and #legend bottom-right"
    assert "max-height" in pane, "a few states run long and must scroll rather than fill the screen"
    assert '<div id="diagwrap">' in (VIEWER_DIR / "viewer.html").read_text()
    # The 300px band, its drag handle and its stored height are gone, not merely hidden.
    assert "vsplit" not in js and "vsplit" not in css
    assert "panelH" not in js, "there is no pane height left to remember"

def test_an_arrow_card_holds_three_calls_and_drills_for_the_rest() -> None:
    """An arrow stands for anything from one call to 33. In the old 300px pane its list ran from 73px to
    1983px, and 16 of the 32 arrows sampled were taller than the pane they were drawn in.

    Measured across the three maps: 873 drawn arrows, of which 481 (55%) stand for exactly ONE call and
    718 (82%) for three or fewer. So the card holds three, which finishes four arrows in five where the
    reader clicked, and the 155 that hold more offer a drill to the arrow's own page.

    ONE builder, because four panels drew this shape by hand and each capped it differently, which is to
    say none of them capped it.

    Two cases are never cut. The arrow's OWN page passes `full`, since there the list IS the subject and
    a drill would lead to the page already open. And an arrow with no page to drill to (a Deployment
    arrow has none yet) shows everything, because a card that hides rows and offers no way to them would
    be worse than a long card."""
    js = (VIEWER_DIR / "viewer.js").read_text()
    assert "const ARROW_CARD_ROWS = 3;" in js
    fn = js[js.index("function arrowCardHtml(o) {"): js.index("\n}", js.index("function arrowCardHtml(o) {"))]
    assert "const full = o.full || !o.drill;" in fn, "no page to go to means nothing is hidden"
    assert "rows.slice(0, ARROW_CARD_ROWS)" in fn
    assert "class=\"xmore\" data-drill=" in fn
    for caller in ("function showContainerEdge(a, b, drawn, full) {",
                   "function showDomainContainerEdge(a, b, drawn, full) {",
                   "function showBridgeEdge(drawn, full) {"):
        assert caller in js, caller
        body = js[js.index(caller): js.index("\n}", js.index(caller))]
        assert "arrowCardHtml({" in body, caller
    assert "showContainerEdge(s.a, s.b, s.efocus || { src: s.a, dst: s.b }, true);" in js, \
        "the arrow's own page is never cut"
    assert "closest('.xmore[data-drill]')" in js, "the way to the rest is delegated, not wired per render"

def test_a_deployment_arrow_has_a_page_like_every_other_arrow() -> None:
    """A Deployment arrow was the last kind with nowhere to drill. Subsystem pairs, entity pairs and
    subsystem-to-subdomain bridges each already had a page; a Deployment arrow's list of calls existed
    only in the pane. So its card was the one that could not be cut, and about 25 of the 78 deployment
    arrows in the three maps stand for more than three calls — the worst for 25.

    It gets a page now, and the page is PROSE, not a diagram: the thing it shows is a list. That is why
    `depedge` joins TEXT_PAGES, which is also what takes the floating card, the legend and the zoom
    controls off it.

    ONE function builds the rows for both the card and the page. They were written twice before, for the
    two arrow shapes a Deployment view draws (process to process, process to infrastructure), and the two
    copies had already drifted on their count line."""
    js = (VIEWER_DIR / "viewer.js").read_text()
    assert "function deploymentEdgeRows(a, b) {" in js
    for fn in ("function showDeploymentEdge(a, b, full) {",
               "function showDeploymentInfraEdge(a, b, full) {",
               "function renderDeploymentEdgePage(s) {"):
        assert fn in js, fn
        body = js[js.index(fn): js.index("\n}", js.index(fn))]
        assert "deploymentEdgeRows(" in body, fn
    for card in ("function showDeploymentEdge(a, b, full) {", "function showDeploymentInfraEdge(a, b, full) {"):
        body = js[js.index(card): js.index("\n}", js.index(card))]
        assert "drill: { kind: 'depedge', a, b }" in body, card
    pages = js[js.index("const TEXT_PAGES = new Set(["):]
    assert "'depedge'" in pages[: pages.index("]);")], "an arrow's list is a page of prose"
    assert "if (s.kind === 'depedge') return [{ kind: 'deployment' }, { kind: 'depedge', a: s.a, b: s.b }];" in js, \
        "the trail reads Deployment > A to B; an arrow joins two processes and belongs under neither"
    assert "kind === 'depedge') return 'deployment'" in js, "and it lives under the Deployment tab"

def test_the_selection_card_can_be_moved_and_resized_and_remembers_it() -> None:
    """The card floats, so one landing spot cannot suit every reader on every map: a wide Subsystems
    overview wants it out of the middle, a tall sequence wants it short. It is dragged by its bar and
    resized from its corner, and both survive a reload.

    The BAR is the only grab handle. Dragging on the card's own text would fight selecting that text, and
    a reader copying a call site out of a row should be able to.

    The box is stored in the diagram area's own pixels and CLAMPED on restore, not on save: the window it
    was dragged in is not the window it comes back to, and a card whose bar sits off the edge cannot be
    dragged back. A double-click on the bar puts it home, because a floating thing needs a way back or one
    bad drag on a small window loses it.

    The resize watcher must ignore CONTENT changes — every new card is a height change — or a card nobody
    ever touched would pin itself wherever the stylesheet first put it and stop following the stylesheet.
    An inline width or height is the only proof a reader dragged the corner."""
    js = (VIEWER_DIR / "viewer.js").read_text()
    css = (VIEWER_DIR / "viewer.css").read_text()
    assert "panelBox: 'coyodex.panelBox'" in js
    assert "function applyPanelBox() {" in js and "applyPanelBox();" in js[js.index("function paneSync() {"):
                                                                          js.index("\n}", js.index("function paneSync() {"))]
    assert "closest('#panelbar')" in js, "the bar is the handle"
    assert "if (!PANEL_HOST.style.width && !PANEL_HOST.style.height) return;" in js, \
        "a content-driven height change is not a resize"
    assert "savePanelBox(null);" in js, "double-click puts the card home"
    pane = css[css.index("#panel {"): css.index("}", css.index("#panel {"))]
    assert "resize: both" in pane and "overflow: auto" in pane, "the corner grip needs a clipped overflow"
    assert "min-width" in pane and "min-height" in pane, "it must not shrink to an unreadable stub"
    bar = css[css.index("#panelbar {"): css.index("}", css.index("#panelbar {"))]
    assert "position: sticky" in bar, "the handle and the close button stay reachable in a scrolled card"

def test_a_text_view_drops_the_source_pane_until_a_code_link_asks_for_it() -> None:
    """The same rule, one step further out, for the whole right-hand column (file browser + code viewer).

    Measured on three real maps at a 1440px window: the column held 542px — 38% — on EVERY view, and on
    the seven text views nothing on the page could ever fill it, so the screen the map lands on spent
    more than a third of itself on "Select a node or file to view its source." On the Storage table the
    same 542px pushed two of its six columns off the right edge. Code is the reader's LAST priority
    (narrative, then the implementation facts, then the code), so it does not get the widest fixed
    column on the landing screen.

    A text page therefore starts with no column; the first code link the reader clicks (loadCode, which
    every path funnels through) brings it back, and the code viewer's × sends it away again. A DIAGRAM
    page is untouched — there a click on a shape loads that shape's file — and a PINNED file browser
    keeps the column anywhere, because pinning is a choice the reader saved.

    The two rules read ONE list of text pages: a second list of "which views are prose" is the drift
    that left the legend keyed to a stale one."""
    js = (VIEWER_DIR / "viewer.js").read_text()
    css = (VIEWER_DIR / "viewer.css").read_text()
    html = (VIEWER_DIR / "viewer.html").read_text()
    assert "function syncCodePane(s) {" in js
    fn = js[js.index("function syncCodePane(s) {"): js.index("\nfunction ", js.index("function syncCodePane(s) {") + 10)]
    assert "TEXT_PAGES.has(s.kind)" in fn, "the source pane must read the SAME list as the info pane"
    assert "!treePinned" in fn, "a pinned file browser keeps the column"
    assert "document.body.classList.toggle('code-hidden'" in fn
    # …and it runs for every state, before render's early returns, exactly like syncInfoPane.
    assert "syncCodePane(s);" in js[js.index("async function render(sArg, transient) {"):][:1400]
    # The one door back in: every way of showing a file goes through loadCode / openInCodeViewer.
    assert "noteCodeAsked();" in js[js.index("async function loadCode(path, line) {"):][:900]
    assert "noteCodeAsked();" in js[js.index("function openInCodeViewer(file, line) {"):][:900]
    # The way back out, offered only where the column is optional.
    assert 'id="cvclose"' in html and "#cvclose[hidden] { display: none; }" in css
    assert "getElementById('cvclose')" in js
    # Hiding is the same set of panes degraded mode hides, plus the column's width going back to the page.
    for pane in ("#tree", "#treeresizer", "#codeview", "#resizer"):
        assert f"body.code-hidden {pane}" in css, pane
    assert "body.code-hidden #leftcol { flex: 1 1 auto; width: auto !important; }" in css

def test_a_page_and_its_title_share_one_left_edge() -> None:
    """The reading-width cap on a card page only bites once the source column is closed and the page has
    the whole window. Centring the remainder put the content 153px right of the breadcrumb — and the
    breadcrumb IS the page's title, since no page draws a heading of its own. A title floating 153px
    from the thing it titles reads as belonging to nothing, so the capped wrappers are pinned left."""
    css = (VIEWER_DIR / "viewer.css").read_text()
    for block in ("max-width: 1100px; margin: 0;", "max-width: 1100px; margin: 0 0 14px;"):
        assert block in css, block
    assert "margin: 0 auto" not in css, "a capped wrapper centred away from the breadcrumb is back"

def test_a_diagram_control_is_dead_on_a_page_with_no_diagram() -> None:
    """The legend and the three zoom controls act on the diagram's pan-zoom, which a page of HTML has
    none of. Measured on Mio Coworker: on 7 of the 12 tabs clicking + moved nothing and the reading
    stayed at 100%, while the legend button lit and unlit with nothing happening. A control that looks
    live and does nothing teaches the reader to distrust the ones that work, and costs a keyboard stop.

    They were kept apart by a SECOND list of "which views are prose", keyed by top-level view, and it had
    drifted both ways. It named `usecases`, so a use-case FLOW — boxes, cylinders and an actor figure,
    under the Features tab — drew no legend. It never learned about `actors`, so the legend opened over
    the actor cards and hid two of them. One question deserves one answer: everything now reads
    TEXT_PAGES, the same list the info pane and the source column read."""
    js = (VIEWER_DIR / "viewer.js").read_text()
    css = (VIEWER_DIR / "viewer.css").read_text()
    assert "TEXT_VIEWS" not in js, "the second list of text views is back"
    fn = js[js.index("function syncLegend(s) {"): js.index("\n\n", js.index("function syncLegend(s) {"))]
    assert "TEXT_PAGES.has(s.kind)" in fn, "the legend must read the one list, keyed by state kind"
    assert "legendbtn.disabled = text;" in fn
    assert "for (const b of [zoomout, zoomlevel, zoomin]) if (b) b.disabled = text;" in fn
    assert "header button:disabled { opacity: .35; cursor: default; }" in css

def test_a_sentence_is_never_set_as_a_pill() -> None:
    """A collection's NOTE was rendered with `.dv-tag`, the pill class, which is `white-space: nowrap`
    because a tag is one word. A note is not: over the three real maps its 135 rows run to a median 78
    characters and a longest of 221. So on the Storage table one un-wrappable note demanded 513px and
    the browser paid for it out of the MEANING column beside it, which fell to 99px — the plain-English
    sentence the reader came for, set one word per line, while two further columns were pushed off the
    right edge. The same pill wrapped the same note in the entity info pane.

    Notes are prose (`.dv-note`); only `mode`, which really is one word, keeps a pill. And both sentence
    columns carry a min-width, because with `table-layout: auto` the widest cell in ANOTHER column is
    otherwise free to decide how little they get."""
    js = (VIEWER_DIR / "viewer.js").read_text()
    css = (VIEWER_DIR / "viewer.css").read_text()
    assert 'class="dv-tag">${esc(st.notes)}' not in js and 'class="dv-tag">${esc(r.notes)}' not in js, \
        "a note is back in a pill that cannot wrap"
    assert 'class="dv-note">${esc(st.notes)}' in js and 'class="dv-note">${esc(r.notes)}' in js
    assert 'class="dv-tag">${esc(st.mode)}' in js and 'class="dv-tag">${esc(r.mode)}' in js, \
        "a one-word mode is a real tag and keeps its pill"
    assert "white-space: nowrap" not in css[css.index(".dv-note {"): css.index(".dv-note {") + 200]
    assert "min-width: 24ch" in css[css.index(".dv-meaning {"): css.index(".dv-meaning {") + 140]
    assert "min-width: 22ch" in css[css.index(".dv-notes {"): css.index(".dv-notes {") + 140]
    assert 'class="dv-notes"' in js, "the notes column needs its own class to carry that floor"

def test_the_system_tab_is_cards_over_one_builder() -> None:
    """It used to stack every collection on one scrolling page under a chip bar: on a real map that is
    664 entry points, 43 commands, 48 config keys, 32 types and 8 notes in a single scroll, and the
    chip bar was the only thing that said what was down there. Now it is the same card level the
    Features tab uses, with one collection per card. Cards and drill read ONE builder, so a card can
    never name a section the drill does not render, and the counts on the cards cannot drift from what
    opens. The bands exist because this tab holds three different kinds of thing, and are drawn only
    when there is more than one to tell apart."""
    js = (VIEWER_DIR / "viewer.js").read_text()
    assert "function systemSections() {" in js
    for fn in ("renderSystem", "renderSystemSection"):
        body = js[js.index(f"function {fn}("): js.index("\nfunction ", js.index(f"function {fn}(") + 10)] \
            if f"\nfunction " in js[js.index(f"function {fn}("):] else js[js.index(f"function {fn}("):]
        assert "systemSections()" in body, fn
    assert "plainCardHtml({ key: s.id, name: s.title" in js   # the ONE card component, as everywhere
    assert "go({ kind: 'sysSection', sys:" in js
    assert "const head = live.length > 1 ?" in js       # one band draws no label
    # The drill is a real level: keyed, titled, and reachable back up by breadcrumb.
    assert "const base = [{ kind: 'system' }, { kind: 'sysSection', sys: s.sys }];" in js
    assert "return s.epk ? base.concat([{ kind: 'sysSection', sys: s.sys, epk: s.epk }]) : base;" in js
    assert "'gid', 'sys', 'epk', 'id'];" in js                 # …and its keys survive a right-pane navigation


def test_the_only_pinned_lines_are_the_ones_that_still_say_something() -> None:
    """The System section header was sticky back when nine collections shared one scrolling page and it
    told you which one you had scrolled into. Each collection has its own page now, its title sits at
    the top of it, and the breadcrumb names it permanently — so a sticky copy repeated a label already
    on screen and pushed the column headers further down. What still earns a pin is the index bar
    (which kind am I in) and the table's own COLUMN headers (what is this cell)."""
    css = (VIEWER_DIR / "viewer.css").read_text()
    js = (VIEWER_DIR / "viewer.js").read_text()
    # The header is gone entirely now, not just unpinned: the breadcrumb's last item IS this page's
    # name, so a heading here printed it twice, inside a box that was a card wrapped round a table.
    assert ".system-wrap .uc-actor" not in css and ".system-wrap .uc-group" not in css
    sec = js[js.index("function renderSystemSection(sysId, epk) {"):
             js.index("\nfunction ", js.index("function renderSystemSection(sysId, epk) {") + 10)]
    assert "uc-group" not in sec and "uc-actor" not in sec
    assert "pageHeroHtml({" in sec, "the same hero a role's page and a feature's page use"
    assert "noDesc: false," in sec, "an entry-point kind is a bare word, not a missing sentence"
    th = css[css.index(".system-wrap .glossary thead th {"): css.index("}", css.index(".system-wrap .glossary thead th {"))]
    assert "top: var(--tab-index-h)" in th, "column headers pin directly under the bar, or to the top"
    assert "--sys-header-h" not in css, "the second offset died with the sticky header it measured"


def test_a_page_with_no_index_bar_reserves_no_room_for_one() -> None:
    """`--tab-index-h` defaulted to 40px in the stylesheet and was only ever overwritten when a bar was
    found. Seven of the System tab's ten collections have no bar, so their sticky column headers pinned
    40px down from the top and floated over the rows with an empty strip above them."""
    css = (VIEWER_DIR / "viewer.css").read_text()
    assert "--tab-index-h: 0px; }" in css
    js = (VIEWER_DIR / "viewer.js").read_text()
    bind = js[js.index("function bindTabIndex(wrap) {"): js.index("\n}", js.index("function bindTabIndex(wrap) {"))]
    assert "if (!nav) { wrap.style.setProperty('--tab-index-h', '0px'); return; }" in bind


def test_the_index_bar_is_a_direct_child_of_the_scroll_wrapper() -> None:
    """Its sticky geometry is written against the wrapper: negative side margins take it full-bleed, and
    the wrapper drops its own top padding only when it HAS a bar (`:has(> .tab-index)`). Nested one level
    down inside the section card, that selector missed and the wrapper kept a 16px transparent strip
    above the bar that rows scrolled visibly through. So the System drill emits the bar beside the
    section, not inside it, and the kinds it jumps to carry the scroll-margin that clears it."""
    js = (VIEWER_DIR / "viewer.js").read_text()
    # The Entry points collection went one level deeper for the same reason the tab did: 311 rows under
    # a chip bar wrapping onto three lines is a flat list with pills. It carries its KINDS as data and
    # the page draws cards from them, so the cards and the table cannot disagree about a count.
    assert "kinds.push({ key: k, count: byKind[k].length" in js
    assert "if (found.kinds && !epk) {" in js
    assert "bindPlainCards(diagram, (key) => go({ kind: 'sysSection', sys: sysId, epk: key }));" in js
    assert "'gid', 'sys', 'epk', 'id'];" in js


def test_no_scroll_wrapper_holds_a_sticky_line_below_its_own_top_padding() -> None:
    """A scroll container's top padding is not part of the scrollport: a sticky `top: 0` child pins to
    the PADDING box, so the padding stays open as a transparent strip that rows scroll visibly through
    ABOVE the pinned line. Measured on the Run commands page — column headers pinned 16px down with a
    table cell painted above them — and the same on Tests and on the Glossary tab. Every wrap holding a
    sticky line drops the padding; the breathing room becomes a MARGIN on the first child, which scrolls
    away like content instead of holding the gap open forever. Verified after: every page still rests
    16px down, every sticky line pins at 0, and the topmost thing while scrolled is the sticky line."""
    css = (VIEWER_DIR / "viewer.css").read_text()
    # `.usecases-wrap.system-wrap`, not `.system-wrap`: the base class sets `padding` as a SHORTHAND
    # later in the file, and at equal specificity that shorthand puts the 16px back.
    assert ".usecases-wrap:has(> .tab-index), .usecases-wrap.system-wrap, .glossary-wrap { padding-top: 0; }" in css
    assert ".system-wrap > :first-child, .glossary-wrap > :first-child { margin-top: 16px; }" in css
    assert ".system-wrap > .tab-index:first-child { margin-top: 0; }" in css   # the bar carries its own
    js = (VIEWER_DIR / "viewer.js").read_text()
    assert "glossary-wrap\" style=\"padding-top" not in js, "an inline top padding reopens the strip"


# --- feature-led views (plan/80) ----------------------------------------------------------------

def _run_js_region(start_marker: str, end_marker: str, snippet: str) -> str:
    """Run `snippet` against a REGION of viewer.js lifted verbatim between two markers.

    Same trick as `_run_js`, which lifts the escaping helpers: the frontend has no module system, so
    a pure function of it is exercised by slicing its source and evaluating it. Sliced by marker
    lines, so a rename fails loudly here rather than silently testing an empty string."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not installed — skipping viewer JS behaviour gate")
    js = (VIEWER_DIR / "viewer.js").read_text(encoding="utf-8")
    lifted = js[js.index(start_marker): js.index(end_marker)]
    assert lifted.strip(), "the lifted region is empty — fix the markers"
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "probe.mjs"
        f.write_text(lifted + "\n" + snippet, encoding="utf-8")
        r = subprocess.run([node, str(f)], capture_output=True, text=True)
    assert r.returncode == 0, f"probe failed:\n{r.stderr}"
    return r.stdout.strip()


def _run_js_regions(regions: list[tuple[str, str]], snippet: str) -> str:
    """`_run_js_region` for a function whose helpers live elsewhere in the file: lift SEVERAL slices,
    in the order given, and run the snippet against all of them. Same marker discipline."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not installed — skipping viewer JS behaviour gate")
    js = (VIEWER_DIR / "viewer.js").read_text(encoding="utf-8")
    lifted = []
    for start, end in regions:
        part = js[js.index(start): js.index(end)]
        assert part.strip(), f"the region {start!r} lifted nothing — fix the markers"
        lifted.append(part)
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "probe.mjs"
        f.write_text("\n".join(lifted) + "\n" + snippet, encoding="utf-8")
        r = subprocess.run([node, str(f)], capture_output=True, text=True)
    assert r.returncode == 0, f"probe failed:\n{r.stderr}"
    return r.stdout.strip()


def test_one_feature_reads_as_three_levels_and_not_seven_equal_rows() -> None:
    """A feature was a label on a use case: to answer "what does Billing & credits do, decide, know and
    run on?" you read four other views and joined them by hand. The first page that answered it put all
    seven answers in ONE definition list, so the purpose weighed the same as the component list, the use
    cases (which ARE the feature) were one row reading "10 use cases", and three rows were folded
    disclosures opening onto thirty unordered chips.

    Three levels now. A header answers "what is this" — name, label, purpose, who drives it. The use
    cases are the page's body. The rest of the map, filtered to this feature, follows as sections in
    reading order: the doors, the decisions, the data, the code. Order on the page IS order of
    importance, and every section carries its count in its heading, so nothing must be opened to be
    counted."""
    js = (VIEWER_DIR / "viewer.js").read_text()
    head = js[js.index("function featureHeadHtml(capId) {"):
              js.index("\nfunction ", js.index("function featureHeadHtml(capId) {") + 10)]
    assert "pageHeroHtml({" in head and "Used by" in head
    assert "f.rules" not in head and "f.components" not in head, "the header holds no counts"
    # A feature's page and a decision area's page are the same shape, so they are the same function.
    assert "function pageHeroHtml(o) {" in js
    assert "pageHeroHtml({" in js[js.index("function renderRules(s) {"):]
    secs = js[js.index("function featureSectionsHtml(capId) {"):
              js.index("\nfunction ", js.index("function featureSectionsHtml(capId) {") + 10)]
    order = re.findall(r"featSection\(secs, '(\w+)', '([^']+)'", secs)
    assert [t for _, t in order] == ["How you reach it", "What it decides", "What it knows",
                                     "What it runs on"], order
    # The use cases are the FIRST section, emitted by the one list renderer, not by a second copy.
    assert "const title = page ? 'What you can do'" in js
    assert "secs.concat(extra.secs)" in js, "the pinned index is built from the sections themselves"
    # Only the CODE folds. It is the lowest-priority thing on the page and its count is in the
    # heading; every other section is open, because a count you must click to see cannot be scanned.
    region = js[js.index("// \u2500\u2500 the feature page"): js.index("function bindFeaturePage(root) {")]
    assert region.count("<details") == 1 and "feat-fold" in region


def test_a_long_list_on_the_feature_page_is_grouped_not_dumped() -> None:
    """One live feature is built from 55 components and another from 31. As one flat run of chips that
    is a wall that says nothing about shape. Grouped under the subsystem each component lives in, the
    same list answers which parts of the machine the feature occupies. Entities group the same way, by
    subdomain, because both ride the same `parent` pointer. One group is not a grouping — a single
    heading repeating the section heading above it is drawn plain instead."""
    js = (VIEWER_DIR / "viewer.js").read_text()
    grp = js[js.index("function featChipGroupsHtml(ids) {"):
             js.index("\nfunction ", js.index("function featChipGroupsHtml(ids) {") + 10)]
    assert "(GRAPH.nodes[id] || {}).parent" in grp
    assert "if (groups.length < 2) return chips(ids);" in grp
    # A feature's rules are cut by DECISION AREA, the same cut the Rules tab makes — one grouping,
    # shared with the component pane, because two of them would disagree about where a rule sits.
    assert "function rulesByBlock(ids) {" in js
    decides = js[js.index("function decidesHtml(id) {"):
                 js.index("\nfunction ", js.index("function decidesHtml(id) {") + 10)]
    assert "rulesByBlock(ids)" in decides


def test_a_feature_page_never_claims_more_certainty_than_the_join_has() -> None:
    """Two silences the page must break. Rules enforced where NO use-case walk passes cannot be placed
    on any feature (27 of 66 on one live map, 47 of 96 on another), so a page listing only the joined
    ones claims the feature decides less than it does. And with no code index a rule is linked only on
    an exact line match, which makes every rule list a floor. Both notes sit directly under the count
    they qualify, not somewhere in the middle of the page."""
    js = (VIEWER_DIR / "viewer.js").read_text()
    notes = js[js.index("function featRuleNotes() {"):
               js.index("\nfunction ", js.index("function featRuleNotes() {") + 10)]
    assert "FEAT_COVERAGE.rulesUnjoined" in notes and "no use-case walk passes" in notes
    assert "FEATURES.ruleJoinUsesExtents === false" in notes and "floor" in notes
    rules = js[js.index("function featRulesHtml(ids) {"):
               js.index("\nfunction ", js.index("function featRulesHtml(ids) {") + 10)]
    assert "featRuleNotes()" not in rules, "a product page carries no coyodex statistic"
    assert "if (!ids.length) return notes + featEmpty(" in rules, "a feature deciding nothing still says so"
    # The notes still exist — on the System tab, with every other fact about coyodex's own analysis.
    cov = js[js.index("function unreachedHtml() {"):
             js.index("\nfunction ", js.index("function unreachedHtml() {") + 10)]
    assert "featRuleNotes()" in cov and "coverageLineHtml()" in cov
    # A map whose use cases name no way in (measured: 0 of 664 on one live map) must SAY so.
    eps = js[js.index("function featEntryPointsHtml(ids) {"):
             js.index("\nfunction ", js.index("function featEntryPointsHtml(ids) {") + 10)]
    assert "Not recorded:" in eps, "an empty ways-in section must name the silence, not go blank"


def test_the_feature_page_reads_the_python_join_and_never_redoes_it() -> None:
    """`coyodex.features` joins a feature to its rules through `validate_model.rule_steps` — the SAME
    reader the Rules view uses, so the two screens cannot disagree about what one rule governs. A
    second join written in JS would drift from both. The page therefore reads the shipped lists and
    counts nothing itself."""
    js = (VIEWER_DIR / "viewer.js").read_text()
    secs = js[js.index("function featureSectionsHtml(capId) {"):
              js.index("\nfunction ", js.index("function featureSectionsHtml(capId) {") + 10)]
    assert "FEAT_BY_ID[capId]" in secs
    for field in ("f.entryPoints", "f.rules", "f.entities", "f.components"):
        assert field in secs, field
    assert "USES_BY_NODE" not in secs, "the component join lives in Python only"
    assert "FEATURES = b.features || {};" in js, "the derivation is shipped, not recomputed"


def test_a_row_is_only_a_use_case_when_it_names_one() -> None:
    """The feature page draws its RULES as rows of the same shape as the use cases above them, on
    purpose: two lists on one page should read as the same kind of thing. But the use-case binder
    claimed every `.uc-row` in the view, so clicking a rule opened `{kind:'usecase', uc:null}` and
    landed the reader on a screen with no name and no crumb. The selector asks for the attribute that
    makes a row a use case, not for the class that makes it look like one."""
    js = (VIEWER_DIR / "viewer.js").read_text()
    assert "diagram.querySelectorAll('.uc-row')" not in js, "a bare row selector claims other pages' rows"
    # The lists are element CARDS now, and the same rule holds one level up: the shared binder acts on
    # `.ecard[data-id]`, and a caller's own control inside a card opts out with `data-card-own`.
    # Only the BINDER half is pinned: the opt-out has no producer since the use-case Happy-Path pill
    # was removed, and pinning a producer that no longer exists would fail on the next honest edit.
    bind = js[js.index("function bindElementCards(root, onDrill) {"):
              js.index("\nfunction ", js.index("function bindElementCards(root, onDrill) {") + 10)]
    assert "root.querySelectorAll('.ecard[data-id]')" in bind
    assert "ev.target.closest('[data-card-own]')" in bind


def test_every_name_on_the_feature_page_resolves_its_view_at_runtime() -> None:
    """`selectTargetFor` is the ONE function that answers "which view draws this id". Regrouping the
    tabs, and the pointing layer being designed beside this, both change where an element lives — so a
    link that hardcoded a tab name would rot silently. Every element name on the page goes through it;
    a ROLE is not an element and has no node, so it opens its own list instead."""
    js = (VIEWER_DIR / "viewer.js").read_text()
    bind = js[js.index("function bindFeaturePage(root) {"):
              js.index("\nfunction ", js.index("function bindFeaturePage(root) {") + 10)]
    assert "selectFromTree(b.getAttribute('data-id'))" in bind
    assert "go({ kind: 'actor', act: b.getAttribute('data-act') })" in bind
    assert "kind: 'container'" not in bind and "kind: 'domain'" not in bind
    # A feature has no box on any diagram, so its home is its own page — without this case a feature
    # id fell through to the default and opened Dependencies.
    target = js[js.index("function selectTargetFor(id) {"):
                js.index("\nfunction ", js.index("function selectTargetFor(id) {") + 10)]
    assert "case 'capability':" in target


def test_a_grouped_card_list_is_one_component_used_by_three_screens() -> None:
    """A third shape, between the flat card list and the card grid: the SAME cards, cut into sections by
    a heading. It earns its place where a set has a natural cut that is not a level — a person and a
    piece of software are both actors, and putting either behind a drill would hide half the set to say
    what a heading says for free. Three screens had hand-rolled the shape, which is the drift the spec's
    "centralize the card designs" exists to stop.

    The cut and the SHAPE are two separate questions, so the component takes both: the heading says
    "these belong together", and list-or-grid says whether the reader is reading the set or choosing one
    out of it. Actors is grouped AND chosen from; a feature page's rules by area, and the four groups of
    unreached components, are grouped and read.

    The section is NOT a card. It was, in a tinted frame containing its members, and two nested card
    shapes on one screen read as two levels of thing when there is only one — the reader had to work out
    whether the frame was itself something to click. So the cards keep the plain look and width, and the
    break is carried by a heading, space and a hairline."""
    js = (VIEWER_DIR / "viewer.js").read_text()
    css = (VIEWER_DIR / "viewer.css").read_text()
    body = js[js.index("function elementCardGroupsHtml(groups, opts) {"):
              js.index("\nfunction ", js.index("function elementCardGroupsHtml(groups, opts) {") + 10)]
    assert "csec" in body and "body(g.ids, g.per)" in body
    # A count and a description are OFFERED, not automatic. Actors passes neither: "4" only restates
    # how many cards follow it, and "Humans" / "Software services" need no sentence to explain them.
    # The two callers that DO pass a count give it a noun ("8 rules"), which is information.
    assert "(g.count ? `<span class=\"csec-count\">${esc(g.count)}</span>` : '')" in body
    assert "const body = (opts && opts.grid) ? elementCardGridHtml : elementCardListHtml;" in body
    assert "mcard" not in js and "mcard" not in css, "the boxed section is gone, not shadowed"
    sec = css[css.index(".csec-head {"): css.index("}", css.index(".csec-head {"))]
    assert "border-bottom" in sec
    for boxed in ("border-radius", "background"):
        rule = css[css.index("\n.csec {") : css.index("}", css.index("\n.csec {"))] if "\n.csec {" in css else ""
        assert boxed not in rule, "a section must not draw itself as a card"
    # An empty group is dropped, and a lone group draws no frame: one heading repeating the page title
    # says nothing.
    assert "filter((g) => g.ids && g.ids.length)" in body
    assert "if (live.length === 1) return body(live[0].ids, live[0].per);" in body
    for caller in ("function actorCardsHtml() {", "function featRulesHtml(ids) {",
                   "function unreachedHtml() {"):
        fn = js[js.index(caller): js.index("\nfunction ", js.index(caller) + 10)]
        assert "elementCardGroupsHtml(" in fn, caller
    assert "feat-rulegroup" not in js, "the hand-rolled group shape is gone, not shadowed"

def test_an_actors_side_is_one_pill_the_card_and_its_page_agree_on() -> None:
    """The card said `SERVICE`; the actor's own page, one click later, said `service` + `STAFF-OWNED`
    about the same actor, and never printed a side on the card at all. Both now read ONE function.

    Four readings:
        person  + user      ->  (nothing)          a person on the customer's side is the ordinary case
        person  + internal  ->  STAFF
        program + internal  ->  INTERNAL SERVICE   a machine the company runs, or pays a vendor to run
        program + user      ->  USER SERVICE       a machine the CUSTOMER set up

    Two words for one stored value, on purpose, and the rule that picks between them is THE READER'S
    WORD MUST FIT THE THING IT LABELS. `staff` is right about a person and wrong about a scheduler or a
    bought payment provider, which is exactly why the model stopped storing it. `internal` is right
    about all three. So the model stores `internal` and each card prints the word that fits what it
    describes. `staff service` was proposed and dropped: it says a program is staff, which is the one
    thing the rename fixed. The two words never meet on one card, and each says "ours".

    Leaving the company's own machines silent hid the single thing the vendor rule exists to settle:
    Mio Coworker's Stripe webhook was authored as the customer's, and a card reading plain `SERVICE`
    looks the same whether that is right or wrong.

    A PERSON stays silent on the customer's side. An actor is a person on the customer's side unless it
    says otherwise — the same rule that drops `human` from every actor card and `user` from a feature
    card. Printing `USER` on every person was tried for one round and undone: it makes the axis look
    complete beside the programs, but the cure is a word on eleven cards that only restates the default.

    `staff` is the reader's word on a FEATURE too, since only human roles vote for its audience."""
    js = (VIEWER_DIR / "viewer.js").read_text()
    css = (VIEWER_DIR / "viewer.css").read_text()
    fn = js[js.index("function actorSidePills(kind, audience) {"):
            js.index("\nfunction ", js.index("function actorSidePills(kind, audience) {") + 10)]
    assert "text: side ? `${side} service` : 'service'" in fn, "a program always prints its side"
    assert "audienceWord(side)" in fn and "staff service" not in fn, "a program is never called staff"
    assert "kind === 'human' && side === 'internal'" in fn, \
        "a person prints a side only when it is the company's"
    # Colour says WHAT it is, the words say whose: both program readings keep the one program colour.
    assert fn.count("ecard-pill-service") == 1 and "cls: `uc-aud-${side}`" in fn
    # The card and the page draw the SAME pills — the page must not compute its own. It draws none at all
    # now: an element page's pills ride the breadcrumb beside the name, read from cardFacts, so there is
    # exactly ONE caller of this helper and the two surfaces cannot disagree by construction.
    code = "\n".join(l for l in js.splitlines() if not l.lstrip().startswith("//"))
    assert "-owned" not in code, "the page's second form for a machine is back"
    assert js.count("actorSidePills(") == 2, "the helper itself, and cardFacts — nothing else"
    head = js[js.index("function actorHeadHtml(actorName) {"):
              js.index("\n}", js.index("function actorHeadHtml(actorName) {"))]
    head = "\n".join(l for l in head.splitlines() if not l.lstrip().startswith("//"))
    assert "pills:" not in head, "the actor's page draws no pills of its own"
    # The reader's word is applied in ONE place, and only where the side is about people.
    assert "function audienceWord(side) {" in js
    # `.ecard-pill` sets a grey background LATER in the file than `.uc-aud-*` sets its own, so a
    # single-class rule loses the cascade and the side pill comes out the same grey as `ACTOR` beside
    # it — present, and easy to read as absent. Both classes, or it silently has no colour.
    assert ".ecard-pill.uc-aud-internal {" in css and ".ecard-pill.uc-aud-user {" in css
    assert "ecard-pill-side" not in css and "ecard-pill-side" not in js
    assert "audienceWord(a)" in js, "the feature card, which is now the only place that draws the word"

def test_a_screen_you_choose_from_is_a_grid_wherever_it_is() -> None:
    """A list is the shape for a set to be READ; a grid is the shape for a set to be CHOSEN between.
    Features and Rules were grids. Actors was a list, and every card on it is a door to that actor's use
    cases — exactly what a feature card and a decision-area card are.

    The reason it was a list had expired. Actor cards used to exist twice: as a GRID on the Features
    view's actor axis, to choose from, and as a LIST on the Actors view, to read, whose cards drilled
    ACROSS into that axis. Removing the axis deleted the grid copy and handed the choosing job to the
    list, which kept its shape. Measured after that: an actor card ran the full 1060px width one per row
    while its sentence used 650px, so 39% of every row was empty, and the counts never justified a
    second shape (8-10 features, 9-12 decision areas, 4-6 actors on the three real maps).

    The People / Software cut stays: the cut and the shape are different questions. This does not bring
    back the boxed section — the break is still a heading, a hairline and space, never a frame.

    One more thing fell out of the grid: `.ecard-grid .ecard-name` gives the name the whole first line,
    so an actor card is now the same shape as every other card in a grid."""
    js = (VIEWER_DIR / "viewer.js").read_text()
    assert "function cardGridHtml(cards) {" in js and "function elementCardGridHtml(ids, per) {" in js
    # The grid class is typed ONCE. Five screens each wrote the div themselves before.
    assert js.count('class="ecard-grid"') == 1, "a hand-rolled card grid is back"
    actors = js[js.index("function actorCardsHtml() {"):
                js.index("\nfunction ", js.index("function actorCardsHtml() {") + 10)]
    assert "], { grid: true });" in actors, "the Actors page must be a grid"
    assert "'Humans'" in actors and "'Software services'" in actors, "the headings name what is under them"
    assert "desc:" not in actors and "count:" not in actors, "no gloss and no bare count on the headings"
    # …and the two screens that really are read, not chosen from, stay lists.
    for caller in ("function featRulesHtml(ids) {", "function unreachedHtml() {"):
        fn = js[js.index(caller): js.index("\nfunction ", js.index(caller) + 10)]
        assert "grid: true" not in fn, caller

def test_no_kind_quietly_joins_the_pill_repeats_the_drill_set() -> None:
    """`TYPE_PILL_REPEATS_DRILL` is a fact ABOUT two other functions: the kinds where the pill's
    destination and the card's destination are the same page. Nothing stopped a later edit to either
    switch from adding a fifth such kind while the Set stayed at four, and the symptom is silent — a
    pill that looks live and repeats a click the reader already made.

    So the Set is checked against the code it describes: every kind it names must resolve the same way
    in both switches, and the four `{ state: { kind:` lines it rests on must still be there."""
    js = (VIEWER_DIR / "viewer.js").read_text()
    sel = js[js.index("function selectTargetFor(id) {"):
             js.index("\nfunction ", js.index("function selectTargetFor(id) {") + 10)]
    drill = js[js.index("function drillInto(id) {"):
               js.index("\nfunction ", js.index("function drillInto(id) {") + 10)]
    for kind, target in (("usecase", "{ kind: 'usecase', uc: id }"), ("block", "{ kind: 'rules', blk: id }"),
                         ("rule", "{ kind: 'rule', br: id }"),
                         ("process", "{ kind: 'deploymentUnit', unit: n.unit }")):
        assert f"case '{kind}':" in sel and target in sel, kind
        assert f"case '{kind}':" in drill and target in drill, kind


def test_the_audience_pill_prints_only_what_it_distinguishes() -> None:
    """`user` is 22 of the 27 features on the three reference maps, so the pill sat on eight cards in
    nine saying what the ninth already implied. It is the same argument the actor cards make for
    dropping their type pill and `human` for dropping its kind pill: a word that is nearly always
    there distinguishes nothing.

    The rule is about the SET, not the word. `user` survives BESIDE `staff`, because "both sides act
    here" is the one thing this pair exists to say, and a lone `staff` would read as "staff only"."""
    js = (VIEWER_DIR / "viewer.js").read_text()
    fn = js[js.index("function shownAudience(list) {"):
            js.index("\n}", js.index("function shownAudience(list) {"))]
    assert "list.length === 1 && list[0] === 'user'" in fn and "? [] : list" in fn
    # ONE surface draws it now: the card. A feature's page used to call this too, for a pill row of its
    # own; those pills ride the breadcrumb beside the name, read from cardFacts, so the page and the card
    # cannot print different sets.
    assert js.count("shownAudience(") == 2, "one definition, one caller"
    head = js[js.index("function featureHeadHtml(capId) {"):
              js.index("\n}", js.index("function featureHeadHtml(capId) {"))]
    head = "\n".join(l for l in head.splitlines() if not l.lstrip().startswith("//"))
    assert "pills:" not in head, "the feature's page draws no pills of its own"


def test_a_grid_of_cards_keeps_one_shape_whatever_the_name_is_long() -> None:
    """A card puts its name and its pills on one wrapping row. Read DOWN a list that is the denser
    shape, but read ACROSS a grid it means a long name pushes the pills to a second line and that one
    card grows taller than the four beside it. In the grid the name takes the whole first line, so
    every card's pills sit in the same place."""
    css = (VIEWER_DIR / "viewer.css").read_text()
    assert ".ecard-grid .ecard-name { flex-basis: 100%; }" in css
    head = css[css.index(".ecard-head {"): css.index("}", css.index(".ecard-head {"))]
    assert "flex-wrap: wrap" in head, "the list shape is unchanged: one row, wrapping only if it must"


def test_a_page_about_one_thing_draws_no_section_for_that_thing() -> None:
    """A role's page used to open with a bordered block whose heading was the page's own title, with the
    use-case cards inside it: the name twice (breadcrumb, then heading) and a card containing cards.
    Both shapes were removed everywhere else in this viewer, and this page had kept them.

    What the role IS moves to the SHARED page hero — the same one a feature's page and a decision area's
    page use — and the cards become a plain list. Sections survive where they are a real cut: one per
    role on the flat catalog a map with no features falls back to."""
    js = (VIEWER_DIR / "viewer.js").read_text()
    ucs = js[js.index("function renderUseCases(sel) {"):
             js.index("\nfunction ", js.index("function renderUseCases(sel) {") + 10)]
    assert "const solo = !!oneActor || one === '-';" in ucs
    assert "if (solo) return elementCardListHtml(ids, per);" in ucs
    assert "oneActor ? actorHeadHtml(oneActor)" in ucs
    # …and the flat catalog still cuts by role, so the guard is not "always drop the section".
    assert "const kinds = new Set((g.roles || []).map" in ucs
    head = js[js.index("function actorHeadHtml(actorName) {"):
              js.index("\nfunction ", js.index("function actorHeadHtml(actorName) {") + 10)]
    assert "pageHeroHtml({" in head, "one hero builder, shared with the feature and rule-area pages"
    assert "actorName" in head and "esc(actorName)" not in head, "the hero must not print the name"
    # The "Other" bucket is not a role: no kind, nothing it wants, and the hero says so.
    assert "g.roles.length === 1 ? g.roles[0] : null" in head


def test_every_card_says_what_it_is_and_only_the_dead_click_goes() -> None:
    """The type pill names what an element IS and, clicked, shows it in its home view. It used to be
    DROPPED on that home view, which left the feature cards as the one card shape in the viewer with
    no identity line, on the very screen a reader meets first.

    Both jobs are separable. The WORD is the card's identity and belongs on every card everywhere: a
    card without it reads as a different kind of object than the cards beside it. The ACTION is a
    control only where it goes somewhere the CARD does not, and it fails that two ways: structurally,
    for four kinds whose pill and whose drill open the same page (a decision area's card was found
    carrying one), and positionally, when the card already sits on the page the pill travels to. Both
    render the word as plain text: no hover, no pointer, no keyboard stop."""
    js = (VIEWER_DIR / "viewer.js").read_text()
    card = js[js.index("function elementCardHtml(id, opts) {"):
              js.index("\nfunction ", js.index("function elementCardHtml(id, opts) {") + 10)]
    assert "const typeHtml = (o.homeType || TYPE_PILL_REPEATS_DRILL.has(c.kind))" in card
    assert "+ typeHtml" in card
    # The four are exactly the kinds whose `selectTargetFor` and `drillInto` answer the same page.
    assert "const TYPE_PILL_REPEATS_DRILL = new Set(['usecase', 'block', 'rule', 'process']);" in js
    assert 'class="ecard-type ecard-type-plain"' in card, "same word, same slot"
    assert "<span" in card.split("o.homeType")[1].split(":")[0], "plain text, not a button"
    assert 'data-ctx="${esc(id)}"' in card, "…and everywhere else it still acts"
    for caller in ("function renderOverview() {", "function actorCardsHtml() {"):
        body = js[js.index(caller): js.index("\nfunction ", js.index(caller) + 10)]
        assert "return { homeType: true," in body, caller
    ucs = js[js.index("function renderUseCases(sel) {"):
             js.index("\nfunction ", js.index("function renderUseCases(sel) {") + 10)]
    assert "return { homeType: !page, extra:" in ucs
    assert "noType" not in js, "the word never goes now; only its action does"
    css = (VIEWER_DIR / "viewer.css").read_text()
    assert ".ecard-type-plain { cursor: default; }" in css


def test_the_coverage_line_reports_reach_and_never_certainty() -> None:
    """"How much of the code does a feature explain" and "how sure is this map" are different
    questions, and only the first is answered here. The second is invisible today: `confidence` and
    `evidence` sit on elements that no view renders, and 381 elements across four live maps say
    `verified` with no skeptic having opened them. One sentence holding both would let a map read as
    well-grounded because its features have wide reach."""
    js = (VIEWER_DIR / "viewer.js").read_text()
    start = js.index("function coverageLineHtml() {")
    line = js[start: js.index("\n}", start)]
    body = "\n".join(ln for ln in line.splitlines() if not ln.strip().startswith("//"))
    assert "reaches" in body
    for word in ("confidence", "verified", "evidence", "sure", "certain"):
        assert word not in body.lower(), word
    assert "componentsUnreached" in line
    # It is a fact about coyodex's own analysis, so it lives on the System tab under "About this map",
    # never on a product view. The reader looking at what the product does did not ask for it.
    assert "sec('map', 'Functional coverage', unreachedHtml()," in js
    assert "coverageLineHtml()" not in js[js.index("function renderOverview() {"):
                                          js.index("\nfunction ", js.index("function renderOverview() {") + 10)]


def test_the_unreached_drill_separates_the_finding_from_the_expected() -> None:
    """The components no feature and no rule reaches are not one pile. Measured on one live map's 13:
    build and deploy tooling took 8, interface contracts 1, shared screen parts 0, and 4 were left
    over. Only the LAST group is a finding, and it is labelled "not classified" rather than "a
    problem" — the map may be incomplete or the code may be dead, and this screen cannot tell which."""
    js = (VIEWER_DIR / "viewer.js").read_text()
    table = js[js.index("const UNREACHED_GROUPS = ["): js.index("\n];", js.index("const UNREACHED_GROUPS = ["))]
    assert [k for k in re.findall(r"\['([a-z]+)',", table)] == ["contracts", "screen", "tooling", "other"]
    assert "'Not classified'" in table
    for bad in ("problem", "dead code", "unused", "wrong"):
        assert bad not in table.lower(), bad


def test_an_unreached_component_is_classified_by_its_whole_path() -> None:
    """One path can match two groups, so the order they are TESTED in is a decision of its own. A live
    map has a bundled demo server whose own folder holds five `widgets/` files beside three others: by
    weight of files alone it read as the product's shared screen parts, when everything under `dev/`
    is scaffolding. The enclosing tree wins over the leaf folder. Below half the files agreeing,
    nothing is claimed at all — the component lands in "not classified" instead of being filed under
    whichever path happened to come first."""
    probe = """
const cases = {
  demo: ['backend/src/x/dev/demo_server.py', 'backend/src/x/dev/README.md',
         'backend/src/x/dev/widgets/a.js', 'backend/src/x/dev/widgets/b.js',
         'backend/src/x/dev/widgets/c.js'],
  widgets: ['frontend/src/components/ui/button.tsx', 'frontend/src/components/ui/dialog.tsx'],
  ports: ['backend/src/x/domain/ports/__init__.py', 'backend/src/x/domain/ports/account.py'],
  shell: ['start.sh', 'stop.sh'],
  compose: ['docker-compose.yml', 'docker/nginx.conf'],
  product: ['tools/coyodex/grammar.py', 'tools/coyodex/anchors.py'],
  split: ['scripts/a.py', 'backend/src/x/service.py', 'backend/src/y/other.py'],
};
const GRAPH = { nodes: {} };
const out = {};
for (const k in cases) { GRAPH.nodes[k] = { files: cases[k] }; out[k] = unreachedClassOf(k); }
console.log(JSON.stringify(out));
"""
    got = json.loads(_run_js_region("const UNREACHED_GROUPS = [",
                                    "// The code no feature and no rule reaches", probe))
    assert got == {"demo": "tooling", "widgets": "screen", "ports": "contracts", "shell": "tooling",
                   "compose": "tooling", "product": "other", "split": "other"}, got


def test_a_map_lands_on_what_the_product_does() -> None:
    """The map should read as WHAT THE PRODUCT DOES first, with code as the evidence you drill into. So
    the landing view is Features, which opens with the product description and then lists everything the
    product does. Each fallback is the next thing down the product row, and only then the machine.

    The description had a tab of its own for one round. A tab is the wrong home for three sentences: the
    reader visits it once and never returns. As the lead of the landing page it cannot be missed and
    costs nothing to scroll past."""
    js = (VIEWER_DIR / "viewer.js").read_text()
    landing = js[js.index("const LANDING ="): js.index("go({ kind: LANDING });")]
    assert "HAS_USECASES ? 'usecases'" in landing
    assert "HAS_HP ? 'hp'" in landing and "HAS_ACTORS ? 'actors'" in landing
    assert "(HAS_DIFF && HAS_GROUPING) ? 'container'" in landing   # a diff still opens on the overlay
    assert "'goal'" not in js and "renderGoal" not in js, "the Goal tab is gone, not hidden"
    # …and the description leads the Features page, above a labelled block of feature cards.
    over = js[js.index("function renderOverview() {"): js.index("\nfunction ", js.index("function renderOverview() {") + 10)]
    assert over.count("productLeadHtml()") == 1
    assert "'<p class=\"block-lbl\">Product features</p>' + grid" in over
    assert "GRAPH.nodes.SYS" in js[js.index("function productLeadHtml() {"):]


def test_code_and_operations_read_as_one_question() -> None:
    """Five group tabs, three of which answered the same second question — how is this thing built and
    run. Product and Data are what the thing IS; everything else is the machine, so Code and Operations
    are one group. Membership rides each button's `data-group`, so the merge is one attribute per
    button and there is no second list to keep in step."""
    js = (VIEWER_DIR / "viewer.js").read_text()
    html = (VIEWER_DIR / "viewer.html").read_text()
    table = js[js.index("const VIEW_GROUPS = ["): js.index("\n];", js.index("const VIEW_GROUPS = ["))]
    assert [g for g in re.findall(r"\['([a-z]+)', '", table)] == ["product", "data", "hood", "glossary"]
    assert "'Under the hood'" in table
    hood = re.findall(r'<button data-view="(\w+)" data-group="hood">', html)
    assert set(hood) == {"container", "context", "tests", "deployment", "system"}, hood


def test_a_component_says_how_many_features_it_serves() -> None:
    """On the code views a component serving four features looked exactly like one serving none. The
    count comes from `componentFeatures` — the Python join — and is never re-counted from the grouped
    list beside it, which is the same join written twice over. Each feature heading is now the way back
    out of the code and into what the product does."""
    js = (VIEWER_DIR / "viewer.js").read_text()
    cnt = js[js.index("function featureCountHtml(id) {"):
             js.index("\nfunction ", js.index("function featureCountHtml(id) {") + 10)]
    assert "COMP_FEATURES[id]" in cnt and "Serves " in cnt
    used = js[js.index("function usedInHtml(id) {"):
              js.index("\nfunction ", js.index("function usedInHtml(id) {") + 10)]
    assert "featureCountHtml(id)" in used
    assert "used-cap-name featref" in used, "a feature heading must open that feature's page"
    assert "selectFromTree(b.getAttribute('data-id'))" in js[js.index("function bindNodeDetailHandlers(root) {"):]


def test_the_path_starts_at_the_view_and_never_at_a_level_inside_it() -> None:
    """The trail always begins with the view. It briefly dropped that first item as an echo of the lit
    tab, and the cost showed one level in: a page began mid-path, and the only way back to the view's
    own landing screen was the tab — which reads as leaving the trail rather than going up it. The
    GROUP is still never here ("Product" is a set of tabs, not a page you can be on).

    The last item is the page's own name, rendered as the document's h1, so NO page draws a heading of
    its own — the duplication every earlier arrangement kept reintroducing somewhere else."""
    js = (VIEWER_DIR / "viewer.js").read_text()
    crumbs = js[js.index("  crumb.innerHTML = '';"):]
    crumbs = crumbs[: crumbs.index("\n}")]
    assert "chain.shift()" not in crumbs, "the view's own name leads the trail; nothing trims it"
    assert "const empty = !chain.length;" in crumbs
    assert "classList.toggle('hint-empty', empty)" in crumbs
    assert "h.className = 'sr-only';" in crumbs
    assert "document.createElement(cur ? 'h1' : 'button')" in crumbs
    assert "crumbsep" in crumbs and "aria-hidden" in crumbs
    css = (VIEWER_DIR / "viewer.css").read_text()
    assert ".hint.hint-empty { padding: 0; border-bottom: 0; }" in css and ".sr-only {" in css
    # No page draws its own name.
    head = js[js.index("function viewHeadHtml(_title, desc) {"):
              js.index("\nfunction ", js.index("function viewHeadHtml(_title, desc) {") + 10)]
    assert "view-title" not in head and "_title" in head
    hero = js[js.index("function pageHeroHtml(o) {"):
              js.index("\nfunction ", js.index("function pageHeroHtml(o) {") + 10)]
    assert "o.name" not in hero and "page-hero-pills" in hero
    assert "page-hero-name" not in js and "view-title" not in js
    for fn in ("renderRule", "renderElementDetails"):
        body = js[js.index(f"function {fn}("): js.index("\nfunction ", js.index(f"function {fn}(") + 10)]
        assert "ruleTitle(r)}</h3>" not in body and "view-title" not in body, fn
    # One heading per page: the app's own name is a brand mark.
    html = (VIEWER_DIR / "viewer.html").read_text()
    import re as _re
    assert not _re.search(r"<h1[ >]", html), "the only h1 is built at runtime, in the breadcrumb"
    assert 'class="brand"' in html

def test_the_title_bar_holds_every_utility_and_wraps_before_it_clips() -> None:
    """Eight controls, all of them things you do to the map rather than places you go: back, forward,
    the three zoom controls, search, help and settings. Search and the legend toggle used to sit in the
    group row, which made that row two things at once. They are quiet icon buttons on the navy ground —
    eight filled chips read as eight destinations.

    At a narrow column the bar wraps into two lines, identity then controls, rather than squeezing."""
    html = (VIEWER_DIR / "viewer.html").read_text()
    css = (VIEWER_DIR / "viewer.css").read_text()
    head = html[html.index("<header>"): html.index("</header>")]
    for control in ("navback", "navfwd", "zoomout", "zoomlevel", "zoomin", "searchbtn", "helpbtn",
                    "setbtn", "legendbtn"):
        assert f'id="{control}"' in head, control
    assert "stageheadutil" not in html and "stageheadutil" not in css
    btn = css[css.index("header button {"): css.index("}", css.index("header button {"))]
    assert "width: 26px" in btn and "height: 26px" in btn and "background: transparent" in btn
    assert "background: rgba(255,255,255,.12)" in css
    assert "@media (max-width: 480px)" in css and "header .brand { flex: 1 0 100%; }" in css

def test_a_page_never_repeats_the_tab_it_was_opened_from() -> None:
    """Six pages printed a title identical to the tab you had just clicked, one line below it. The tab
    is where the page is named; the page does not name it again. A title that says something ELSE —
    an actor, a System collection, "Use cases" on a map recording no features — is information, not an
    echo, and stays. One rule, in the one function every page head goes through."""
    js = (VIEWER_DIR / "viewer.js").read_text()
    head = js[js.index("function viewHeadHtml(_title, desc) {"):
              js.index("\nfunction ", js.index("function viewHeadHtml(_title, desc) {") + 10)]
    # A head with no description of its own is not drawn at all: the page's name is the breadcrumb's
    # last item, and there is nothing else for a head to say.
    assert "return desc ?" in head


def test_the_question_reads_as_a_sentence_and_not_as_a_control() -> None:
    """Set upright at the tabs' own size, right after them, the question read as a fifth disabled tab —
    and the ambiguity is what made it invisible, not the contrast. Italic fixes what it IS before fixing
    how loud it is: nothing else in this app is italic, so one glance says sentence, not control.

    Everything that framed it is gone with the places it used to sit. The dividing rule after the last
    tab went when it left the tab row. The em dash went when it left the page title's line: a dash joins
    two things on one line, and alone at the start of a line it is a stray tick. It has no rule, no
    background and no border either — anything that boxes a sentence turns it back into a bar."""
    js = (VIEWER_DIR / "viewer.js").read_text()
    css = (VIEWER_DIR / "viewer.css").read_text()
    assert "has-after" not in js and "has-after" not in css, "the tab-row rule is gone, not shadowed"
    q = css[css.index("#pageq {"): css.index("}", css.index("#pageq {"))]
    assert "font-style: italic" in q
    assert "border" not in q and "background" not in q, "nothing may box the opening sentence"
    assert "\\2014" not in q and "#pageq::before" not in css, "no dash on a line of its own"
    assert "pageq.textContent = q;" in js, "the stored string is the pure question"

def test_the_app_name_is_a_working_way_back_to_all_maps() -> None:
    """It was an <h1> with a click handler, and became a plain span when the page's one heading moved to
    the breadcrumb — which silently took the link with it. A span with a click handler is not a control:
    no keyboard tab stop, no Enter, nothing announced. So it carries a link role, a tab stop and its own
    key handling, and a home icon says what it does before you hover it."""
    js = (VIEWER_DIR / "viewer.js").read_text()
    html = (VIEWER_DIR / "viewer.html").read_text()
    css = (VIEWER_DIR / "viewer.css").read_text()
    assert 'class="brand-home"' in html and 'aria-hidden="true"' in html
    block = js[js.index("const brand = document.querySelector('header .brand');"):]
    block = block[: block.index("\n  }") + 4]
    assert "brand.setAttribute('role', 'link');" in block
    assert "brand.setAttribute('tabindex', '0');" in block
    assert "e.key === 'Enter' || e.key === ' '" in block
    assert "brand.addEventListener('click', home);" in block
    assert "header .brand.home-link { cursor: pointer; }" in css


def test_an_arrow_from_a_box_to_itself_is_one_arrow_made_of_three_pieces() -> None:
    """A flow step where one box acts on itself draws a loop. Mermaid does not draw that loop as one
    line: it routes it through two invisible helper boxes and emits THREE paths, named
    `<diagram>-<box>-cyclic-special-1 | -mid | -2` — none of which spells `L_<src>_<dst>_<i>`. The
    viewer read only that one spelling, so the loop was painted and then never picked up: no hover, no
    click, no highlight, and the step player froze on the step it carried.

    The reader now reports the loop ONCE (on `-mid`, the piece Mermaid keeps the label on) as an arrow
    whose two ends are the same box, and hands over all three pieces so everything that paints or
    hit-tests an arrow covers the whole loop. The two arrows after it pin the other half of the bug
    class: Mermaid emits one label per PATH — two of them empty — so the index pairing that gives every
    LATER arrow its label must count all three pieces, not one."""
    out = _run_js_region(
        "function eachEdge(root, fn) {",
        "// Stroke an edge's path + glow its label",
        """
const mk = (id) => ({ id, style: {} });
const paths = ['g-C50-cyclic-special-1', 'g-C50-cyclic-special-mid', 'g-C50-cyclic-special-2',
               'g-L_C50_E55_0', 'g-L_U_0_U_15_0'].map(mk);
const labels = ['', '6', '', '7', '8'].map((text) => ({ text }));
const root = { querySelectorAll: (sel) => (sel.includes('edgePaths') ? paths : labels) };
const seen = [];
eachEdge(root, (p, label, m) => seen.push(
  { label: label && label.text, src: m[1], dst: m[2], i: m[3], segs: (p._segs || [p]).map((s) => s.id) }));
console.log(JSON.stringify(seen));
""",
    )
    seen = json.loads(out)
    assert [(s["src"], s["dst"]) for s in seen] == [("C50", "C50"), ("C50", "E55"), ("U_0", "U_15")]
    loop = seen[0]
    assert loop["label"] == "6" and loop["i"] == "0"
    assert loop["segs"] == ["g-C50-cyclic-special-1", "g-C50-cyclic-special-mid",
                            "g-C50-cyclic-special-2"], "all three pieces travel with the arrow"
    # The arrows drawn AFTER the loop still get their own labels — the pairing counted three, not one.
    assert [s["label"] for s in seen[1:]] == ["7", "8"]
    # An ordinary arrow is still one piece, so nothing else pays for the loop.
    assert seen[1]["segs"] == ["g-L_C50_E55_0"]


def test_a_step_the_diagram_cannot_draw_never_traps_the_walk() -> None:
    """Pressing Next used to sit on one step for ever. A step whose arrow this rendering did not draw
    has no selector, so the player resets the diagram — and the reset also SUSPENDS the player. A
    suspended player answers the next press by re-entering the SAME index, so the counter stopped
    dead and every further press repeated the same nothing.

    The step keeps its number and shows nothing, but the walk goes on. Run against the real
    flowGoto/flowStepBy with the middle step of three left undrawn: the counter must reach the last
    step and wrap, not stick at the undrawn one."""
    out = _run_js_region(
        "function flowGoto(i) {",
        "// Called from render() once svg-pan-zoom exists.",
        """
let flowPlay = { uc: 'UC1', steps: [{}, {}, {}], msgEls: [[], [], []], cur: -1, active: false };
// Selecting a drawn step ends in flowSyncCur, which is what re-activates the player after the
// selClear inside flowGoto. Step 2 of 3 (index 1) has NO selector: undrawn in this rendering.
const flowSyncCur = () => { flowPlay.active = true; };
const mainScene = { selectors: { 'flowstep:UC1:0': flowSyncCur, 'flowstep:UC1:2': flowSyncCur } };
function flowSuspend() { flowPlay.active = false; }
function selClear() { flowSuspend(); }
function resetScene() { selClear(); }
function flowReveal() {}
function flowCounter() {}
const walked = [];
for (let k = 0; k < 6; k++) { flowStepBy(1); walked.push(flowPlay.cur); }
console.log(JSON.stringify(walked));
""",
    )
    assert json.loads(out) == [0, 1, 2, 0, 1, 2], "the walk must pass the undrawn step, not sit on it"


def test_the_domain_view_reads_a_self_arrow_through_the_same_one_reader() -> None:
    """The same bug, one view over: an entity related to ITSELF (a parent/child link) is drawn by the
    class diagram as the same three pieces, under the same id spelling — which matches neither the
    flowchart's `L_<src>_<dst>_<i>` nor the class diagram's own `id_<src>_<dst>_<i>`. Found by sweeping
    for the bug class after fixing the flow map, and confirmed against a real Mermaid 11 render.

    So both views read the loop through ONE function. This runs the Domain view's real edge reader over
    a class diagram holding a self relation and two ordinary ones: the loop must come back once, as a
    relation whose two ends are the same entity, and the relations after it must keep their own
    labels."""
    out = _run_js_regions(
        [("function selfArrowParts(paths) {", "// An arrow's screen box:"),
         ("function eachClassEdge(root, fn) {", "// Mermaid's classDiagram markers default")],
        """
const mk = (id) => ({ id });
const paths = ['d-E1-cyclic-special-1', 'd-E1-cyclic-special-mid', 'd-E1-cyclic-special-2',
               'd-id_E1_E2_2', 'd-id_E2_E1_3'].map(mk);
const labels = ['', 'parent', '', 'holds', 'lives in'].map((text) => ({ text }));
const root = { querySelectorAll: (sel) => (sel.includes('relation') ? paths : labels) };
const seen = [];
eachClassEdge(root, (p, label, src, dst) => seen.push(
  { label: label && label.text, src, dst, segs: (p._segs || [p]).map((s) => s.id) }));
console.log(JSON.stringify(seen));
""",
    )
    seen = json.loads(out)
    assert [(s["src"], s["dst"]) for s in seen] == [("E1", "E1"), ("E1", "E2"), ("E2", "E1")]
    assert seen[0]["label"] == "parent"
    assert seen[0]["segs"] == ["d-E1-cyclic-special-1", "d-E1-cyclic-special-mid",
                               "d-E1-cyclic-special-2"]
    assert [s["label"] for s in seen[1:]] == ["holds", "lives in"]
