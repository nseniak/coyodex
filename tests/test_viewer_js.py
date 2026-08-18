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
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not installed — skipping viewer JS syntax gate")
    assert js_path.exists(), f"expected {js_path} to exist"
    result = subprocess.run(
        [node, "--check", str(js_path)], capture_output=True, text=True
    )
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
    detail = js[js.index("function nodeDetailHtml"):js.index("function bindNodeDetailHandlers")]

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
    assert "const tab = stateTitle({ kind: topView(t.state.kind) })" in locate_code
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
    a four-view sub row."""
    css = (VIEWER_DIR / "viewer.css").read_text()
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
    assert "renderUseCases(s.kind === 'actor' ? { actor: s.act } : { cap: s.cap });" in js
    # In diff mode a card carries its members' change, or dropping the use cases one level down would
    # hide every "changed" badge behind a click.
    feat = js[js.index("function renderOverview() {"): js.index("\nfunction ", js.index("function renderOverview() {") + 10)]
    assert "g.ucs.some((n) => usecaseDiffState(n.id))" in feat


def test_the_axis_switch_lives_on_the_overview_and_nowhere_else() -> None:
    """Both axes (feature / actor) are properties of the OVERVIEW, which is the level that has two ways
    to cut the same use cases. On a list already scoped to one card an axis switch either does nothing
    or silently swaps which card you are reading. It used to live on a flat "all use cases" page that
    was the only route to the actor axis, and that page restated the overview's card names in a chip
    bar AND again in every section heading, right after you had read them as cards. Both axes draw
    cards from ONE grouping function each, shared with the list that drills out of them."""
    js = (VIEWER_DIR / "viewer.js").read_text()
    over = js[js.index("function renderOverview() {"): js.index("\nfunction ", js.index("function renderOverview() {") + 10)]
    assert "uc-groupby" in over and "capabilityGroups()" in over and "actorGroups()" in over
    lst = js[js.index("function renderUseCases(sel) {"): js.index("\nfunction ", js.index("function renderUseCases(sel) {") + 10)]
    assert "uc-groupby" not in lst, "the list level must not carry an axis switch"
    assert "feat-all" not in js, "the flat all-use-cases page is gone"
    # Two axes, two states, both filed under the same tab so the crumb reads Features > the card.
    assert "if (s.kind === 'actor') return [{ kind: 'usecases' }, { kind: 'actor', act: s.act }]" in js
    assert "kind === 'actor'" in js[js.index("function topView(kind) {"):]


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
    """The overview has two axes, so a use case belongs to one group on each. Naming its FEATURE while
    the reader arrived through an ACTOR put a card they never opened in the trail, and clicking that
    crumb navigated them to a screen they had never seen. The middle crumb follows the axis the
    overview is on. A use case in no feature still gets one, or that drill is the only one in the
    viewer no breadcrumb can undo."""
    js = (VIEWER_DIR / "viewer.js").read_text()
    anc = js[js.index("if (s.kind === 'usecase') {"):]
    anc = anc[: anc.index("\n  }")]
    assert "ucGroupBy() === 'actor'" in anc and "actorGroupOf(s.uc)" in anc
    assert "CAP_OF_UC[s.uc] ? CAP_OF_UC[s.uc].id : '-'" in anc
    assert "function actorGroupOf(ucId) {" in js and "actorGroups().find(" in js


def test_a_feature_found_by_search_opens_the_features_tab() -> None:
    """A feature is drawn as no box anywhere, so `selectTargetFor` had nothing to select and fell to
    its `default`, opening Dependencies — a confident wrong answer to a hit the index itself labels a
    feature. Its home is its own card's list."""
    js = (VIEWER_DIR / "viewer.js").read_text()
    assert "case 'capability':" in js
    assert "return { state: { kind: 'capability', cap: id }, selectId: null };" in js
    assert "capability: 'feature'" in js


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
    assert "{ kind: 'usecase', uc: li.getAttribute('data-uc'), act: oneActor }" in js
    assert "const act = s.act || (ucGroupBy() === 'actor' ? actorGroupOf(s.uc) : '');" in js


def test_a_mode_switch_is_the_quietest_control_in_the_header() -> None:
    """Three stacked bars of segments read as three levels of tabs, and the bottom one is not a tab:
    the Features axis is a MODE. In its own strip it wore the same solid indigo as the GROUP row, so
    the least important control on screen shouted as loudly as the one deciding which fifth of the map
    you are in. It rides the view row now, right-aligned, in that row's own weight. The quieting is
    scoped to `#viewextra`: the flow picker reuses `.uc-seg` in a card floating over the diagram,
    where a solid active state is correct."""
    css = (VIEWER_DIR / "viewer.css").read_text()
    quiet = css[css.index("#viewextra .uc-seg button.on {"):]
    quiet = quiet[: quiet.index("}")]
    assert "#6366f1" not in quiet, "the mode switch must not borrow the group row's solid indigo"
    assert "#e0e7ff" in quiet
    loud = css[css.index("\n.uc-seg button.on {"):]
    assert "#6366f1" in loud[: loud.index("}")], "the floating flow picker keeps the loud style"


def test_every_header_row_starts_at_the_same_edge() -> None:
    """The search button sat before the group row and pushed it 42px in, so the group row, the view row
    and the switch each began at a different x and the three read as unrelated strips. Measured after:
    15px and 14px, the 1px being the group control's own border. The utilities are what moves."""
    html = (VIEWER_DIR / "viewer.html").read_text()
    head = html[html.index('<div id="stageheadrow">'): html.index('<div id="stagesubrow">')]
    assert head.index('id="groupsw"') < head.index('id="searchbtn"'), "nothing may precede the group row"
    assert 'id="stageheadutil"' in head
    css = (VIEWER_DIR / "viewer.css").read_text()
    util = css[css.index("#stageheadutil {"): css.index("}", css.index("#stageheadutil {"))]
    assert "margin-left: auto" in util


def test_a_views_mode_switch_never_survives_a_move_to_another_view() -> None:
    """The switch belongs to ONE view. Left in the header it would float above a view it does not act
    on — the same failure the floating flow picker had, and it is cleared in the same place, before the
    HTML-tab early returns. Its answer moved to the info pane, so a view's question has one home."""
    js = (VIEWER_DIR / "viewer.js").read_text()
    render = js[js.index("  const fp = document.getElementById('flowpicker');"):]
    assert "viewextra.innerHTML = '';" in render[:600]
    over = js[js.index("function renderOverview() {"): js.index("\nfunction ", js.index("function renderOverview() {") + 10)]
    assert "viewextra.innerHTML = HAS_CAPABILITIES" in over
    assert "uc-groupby-why" not in js, "the axis answer belongs to the info pane, not beside the switch"
    assert "function viewQuestion(view) {" in js
    assert "ucGroupBy() === 'actor') return 'What can each role do?'" in js
    assert "viewQuestion(view) ? `<p class=\"viewq\">" in js


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
    assert 'class="feat-card" data-sys=' in js          # the same card component as the Features tab
    assert "go({ kind: 'sysSection', sys:" in js
    assert "const head = live.length > 1 ?" in js       # one band draws no label
    # The drill is a real level: keyed, titled, and reachable back up by breadcrumb.
    assert "const base = [{ kind: 'system' }, { kind: 'sysSection', sys: s.sys }];" in js
    assert "return s.epk ? base.concat([{ kind: 'sysSection', sys: s.sys, epk: s.epk }]) : base;" in js
    assert "'gid', 'sys', 'epk'];" in js                 # …and its keys survive a right-pane navigation


def test_the_only_pinned_lines_are_the_ones_that_still_say_something() -> None:
    """The System section header was sticky back when nine collections shared one scrolling page and it
    told you which one you had scrolled into. Each collection has its own page now, its title sits at
    the top of it, and the breadcrumb names it permanently — so a sticky copy repeated a label already
    on screen and pushed the column headers further down. What still earns a pin is the index bar
    (which kind am I in) and the table's own COLUMN headers (what is this cell)."""
    css = (VIEWER_DIR / "viewer.css").read_text()
    title = css[css.index(".system-wrap .uc-actor {"): css.index("}", css.index(".system-wrap .uc-actor {"))]
    assert "sticky" not in title
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
    assert "go({ kind: 'sysSection', sys: sysId, epk: b.getAttribute('data-epk') })" in js
    assert "'gid', 'sys', 'epk'];" in js


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
