"""`coyodex access-surface` — the map's auth surface as FILES, for a later build to be measured against.

A rebuild is deliberately blind to its predecessor, and that is right: the independence is the whole
point of a from-scratch build. But it means a security claim can DISAPPEAR between two maps of
unchanged code and nothing in the build notices. On the 2026-08-20 argus pair the access-rule
STATEMENT count held at 21 -> 21 while the enforcement lines went 60 -> 48, and one file lost its
coverage outright: `adapters/auth_google.py`, whose lines verify the Google ID token's signature,
issuer and audience. The previous map claimed it as an access rule. The new map's 61 rules do not
mention a signature, an issuer or an audience anywhere.

`coyodex-eval compare` prints that as a NOTE. Two things make the note too late: it is a
developer-only command, and it runs at retro time against a baseline the build may not read — so on
the run that lost the claim, the note was printed, parked as "a reading job", and only re-read three
retrospectives later.

This writes the surface as data, so `coyodex finalize --access-baseline <file>` can put it in front
of the build's own gate — AFTER the map is written, where reading it cannot contaminate the rebuild,
and BEFORE the commit, which is the last moment anybody looks.
"""
from __future__ import annotations

import json
from pathlib import Path

from coyodex.model import ProjectModel, access_rules

SCHEMA = "coyodex-access-surface/v1"


def access_files(m: ProjectModel) -> dict[str, list[str]]:
    """`{repo-relative file: [rule ids that anchor a site in it]}` — the wording-free half.

    FILES, not statements and not lines. Statements are LLM prose and drift between builds with no
    change in meaning; a line moves when the code above it moves. A file that held enforcement in
    one map and is claimed by no access rule in the next is the one signal that survives both."""
    out: dict[str, list[str]] = {}
    for rule in access_rules(m):
        for site in rule.sites:
            where = (site.where or "").strip()
            if not where:
                continue
            path = where.rsplit(":", 1)[0] if ":" in where else where
            path = path.strip()
            if path:
                out.setdefault(path, [])
                if rule.id not in out[path]:
                    out[path].append(rule.id)
    return {k: sorted(v) for k, v in sorted(out.items())}


def surface_doc(m: ProjectModel) -> dict[str, object]:
    rules = access_rules(m)
    return {"schema": SCHEMA,
            "commit": m.commit or "",
            "access_rules": len(rules),
            "files": access_files(m)}


def write_surface(m: ProjectModel, path: Path) -> dict[str, object]:
    doc = surface_doc(m)
    path.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return doc


def load_surface(path: Path) -> dict[str, list[str]]:
    """`{file: [rule ids]}` from a surface file, or from a whole MAP — both are accepted.

    Accepting a map matters: every archive already holds one, and requiring the operator to
    pre-convert it is the friction that leaves a check unrun."""
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError(f"{path}: not a JSON object")
    if doc.get("schema") == SCHEMA:
        files = doc.get("files")
        return {k: list(v) for k, v in files.items()} if isinstance(files, dict) else {}
    from coyodex.assemble import load_map_or_fragment
    m, _present = load_map_or_fragment(path)
    return access_files(m)


def lost_files(baseline: dict[str, list[str]], m: ProjectModel) -> list[str]:
    """Files the baseline claimed as access enforcement that no access rule in `m` names."""
    now = set(access_files(m))
    return sorted(f for f in baseline if f not in now)
