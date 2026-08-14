#!/usr/bin/env python3
"""Read a map written by an OLDER coyodex, for read-only eval work.

`coyodex.model.load_model` refuses a renamed field on purpose: a build must never assemble, validate
or commit a map whose schema has moved on, and the refusal names the rename so the operator fixes the
source. That is right for every WRITING path, and it is what this module leaves alone.

It is wrong for the eval, which exists to look BACKWARDS. `coyodex-eval score` on the map a rebuild
replaced exited 1 with `$.grounding.claims_grounded: unknown field`, so the comparison the whole
retrospective rests on could not run at all — the archived map, by definition, was built by an older
tool. The reviewer hand-patched a copy to get a number, which is the same adaptation done worse:
untracked, unexplained, and one keystroke from fabricating the split it could not recover.

So: one small, explicit, READ-ONLY table of retirements, each dropping data rather than inventing it,
each returning a note the caller must show. Never importable from `tools/coyodex` — a writing path
that wants this is a writing path with a bug.
"""
from __future__ import annotations

import json
from typing import Any

from coyodex.model import ModelError, ProjectModel, load_model

#: Retired top-level blocks: the block, the field that dates it, and what a reader loses by dropping
#: it. DROPPED, never translated — `claims_grounded` counted claims that got a VERDICT, so the
#: confirmed/refuted/unverifiable split it predates cannot be recovered from it, and synthesising one
#: would put a fabricated number where the honest answer is "this map does not record that".
_RETIRED_BLOCKS: tuple[tuple[str, str, str], ...] = (
    ("grounding", "claims_grounded",
     "grounding predates the claims_challenged/confirmed/refuted/unverifiable split and was dropped"),
)


def load_model_tolerating_legacy(map_text: str) -> tuple[ProjectModel, tuple[str, ...]]:
    """Load a map for READING. Returns the model and a note per legacy adaptation applied.

    Tries the strict loader first, so a current map takes the identical path it always did and the
    notes are empty. Only a `ModelError` naming a retirement in `_RETIRED_BLOCKS` triggers an
    adaptation; every other `ModelError` propagates unchanged, because a map that is broken in some
    NEW way must still fail loudly.
    """
    try:
        return load_model(map_text), ()
    except ModelError:
        pass
    try:
        doc: Any = json.loads(map_text)
    except ValueError:
        raise
    if not isinstance(doc, dict):
        return load_model(map_text), ()          # not our case — re-raise the original shape error
    notes: list[str] = []
    for block, dating_field, what_is_lost in _RETIRED_BLOCKS:
        body = doc.get(block)
        if isinstance(body, dict) and dating_field in body:
            doc.pop(block, None)
            notes.append(f"legacy map: `{block}.{dating_field}` is retired — {what_is_lost}")
    if not notes:
        return load_model(map_text), ()          # nothing we know how to adapt — let it raise
    # Re-serialise and take the STRICT loader again, so an adapted map is held to exactly the same
    # standard as any other. An adaptation that leaves the map invalid is still an error.
    return load_model(json.dumps(doc)), tuple(notes)
