"""Test setup that applies to BOTH roots (`tests` and `eval/tests`).

It does two things: make `PYTHONPATH` ABSOLUTE, anchored on the checkout this file lives in, and
keep every test out of `coyodex serve`'s remembered-projects list (the block at the bottom).

WHY. Seventeen test files start a python CHILD process, and only two hand it an environment of their
own. The rest inherit ours — including `PYTHONPATH=tools`, which is how the CLI is put on the path.
That value is RELATIVE, and most of those children run with `cwd=` set to a fixture directory. There
is no `tools` there, so the import falls through to the editable install, which points at whichever
checkout was installed — normally the main one.

In the main checkout the two happen to agree and nothing is visible. In a WORKTREE they do not:

    parent reads:  .../worktrees/<branch>/tools/coyodex/__init__.py
    child reads:   /Users/…/Projects/coyodex/tools/coyodex/__init__.py

So a worktree's subprocess tests were green about code that was not the code under edit. That is not
theoretical: `test_assembly_fixture` passed for a whole day's work against a stale pinned fixture,
because the child assembling the map was running the OTHER checkout's model, which had not yet grown
the new field. It only failed once the branch was merged — after several honest-looking green runs.

WHAT IT DOES. Every RELATIVE entry in `PYTHONPATH` is re-anchored on this file's directory; absolute
entries are left exactly as they are. So `PYTHONPATH=tools` keeps meaning "this checkout's tools" no
matter what directory a child is started in, and a caller who passed a full path is not second-
guessed. Nothing is added that was not already there: a run with no `PYTHONPATH` still uses the
installed package, which is what a plain `pytest` is asking for.

The guard that this stays true is `tests/test_cli_contract.py`'s child-reads-the-same-tools test.
"""
from __future__ import annotations

import os
from pathlib import Path

_ROOT = Path(__file__).resolve().parent


def _absolute_pythonpath(raw: str | None) -> str | None:
    """`raw` with every relative entry anchored on the repo root. None/empty passes through."""
    if not raw:
        return raw
    parts = [p for p in raw.split(os.pathsep) if p]
    fixed = [p if os.path.isabs(p) else str((_ROOT / p).resolve()) for p in parts]
    return os.pathsep.join(fixed)


_fixed = _absolute_pythonpath(os.environ.get("PYTHONPATH"))
if _fixed:
    os.environ["PYTHONPATH"] = _fixed

# THE SECOND THING. A finished `assemble` or `render` into a `.coyodex/` folder registers that
# folder in ~/.coyodex/serve-recents.json, the landing page's cards (`viewer/recents.py`). The CLI
# sweep's `ship` recipe does exactly that on a throwaway `<tmp>/shiprepo`, so every test run left
# one more dead card on the page — 577 of them by 2026-09-12. This is the product's own opt-out,
# the one the eval sets for its throwaway builds; every child process inherits it through
# `os.environ`. A test that wants to SEE registration happen injects its own store and clears
# the switch for its own body (`tests/test_serve.py::test_register_project`).
os.environ["COYODEX_NO_SERVE_REGISTER"] = "1"
