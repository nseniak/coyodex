#!/usr/bin/env python3
"""Read-only tolerance for maps an older coyodex wrote (`coyodex_eval.legacy_map`).

`coyodex-eval score` on the map a rebuild replaced exited 1 with
`$.grounding.claims_grounded: unknown field`, so the comparison a retrospective rests on could not
run: the archived map is BY DEFINITION older than the tool reading it. Writing paths keep the strict
loader and the loud refusal; only the eval looks backwards.

Run either way (needs an editable install: `make deps`):
    python3 eval/tests/test_legacy_map.py
    pytest eval/tests/test_legacy_map.py
"""
from __future__ import annotations

import json

import pytest

from coyodex.model import ModelError
from coyodex_eval.legacy_map import load_model_tolerating_legacy


def make_map(grounding: dict | None = None) -> str:
    doc: dict = {
        "format": "coyodex-map", "title": "t", "goal": "g",
        "use_cases": [{"id": "UC1", "name": "Do"}],
        "components": [{"id": "C1", "name": "A", "source": "a.py:1"}],
    }
    if grounding is not None:
        doc["grounding"] = grounding
    return json.dumps(doc)


def test_a_current_map_takes_the_strict_path_and_reports_no_adaptation():
    model, notes = load_model_tolerating_legacy(make_map({
        "claims_total": 10, "claims_challenged": 10, "claims_confirmed": 9,
        "claims_refuted": 1, "claims_unverifiable": 0}))
    assert notes == ()
    assert len(model.components) == 1


def test_a_map_with_no_grounding_at_all_is_untouched():
    model, notes = load_model_tolerating_legacy(make_map())
    assert notes == ()
    assert model.grounding is None


def test_the_retired_grounding_block_is_dropped_and_the_map_loads():
    """The exact map that blocked a live retrospective: `claims_grounded`, no verdict split."""
    model, notes = load_model_tolerating_legacy(make_map({
        "claims_total": 254, "claims_grounded": 254, "claims_refuted": 13}))
    assert len(notes) == 1 and "claims_grounded" in notes[0]
    assert len(model.components) == 1


def test_the_dropped_block_is_never_translated_into_the_new_counts():
    """`claims_grounded` counted claims that got a VERDICT, so the confirmed/refuted/unverifiable
    split cannot be recovered from it. Inventing one would put a fabricated number where the honest
    answer is 'this map does not record that'."""
    model, _notes = load_model_tolerating_legacy(make_map({
        "claims_total": 254, "claims_grounded": 254, "claims_refuted": 13}))
    assert model.grounding is None, "a legacy grounding record must be dropped, never adapted"


def test_a_map_broken_in_some_other_way_still_fails_loudly():
    broken = json.dumps({"format": "coyodex-map", "title": "t", "goal": "g",
                         "components": [{"id": "NOPE1", "name": "A", "source": "a.py:1"}]})
    with pytest.raises(ModelError):
        load_model_tolerating_legacy(broken)


def test_a_legacy_block_plus_a_real_error_still_raises():
    """Adapting the known retirement must not smuggle a genuinely invalid map past the loader: the
    adapted document is handed to the STRICT loader again."""
    doc = json.loads(make_map({"claims_total": 1, "claims_grounded": 1}))
    doc["components"] = [{"id": "WRONG9", "name": "A", "source": "a.py:1"}]   # not a `Cn` id
    with pytest.raises(ModelError):
        load_model_tolerating_legacy(json.dumps(doc))


def test_a_non_object_document_raises_rather_than_being_adapted():
    with pytest.raises(ModelError):
        load_model_tolerating_legacy(json.dumps(["not", "a", "map"]))


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
