#!/usr/bin/env python3
"""Write a map as a STATIC SITE — a folder of plain files anyone can host, so a link to the viewer
can be shared with people who have neither the repo nor coyodex.

The viewer is normally served: `coyodex serve` answers the page's questions live, reading code out of
git at the map's commit. An export answers the SAME questions in advance, by writing one file per
address the page asks for. Nothing runs on the host — the reader's browser does all the drawing, as
it already does today — so the folder works on GitHub Pages, Netlify, a cloud bucket, or any web
server that can hand back a file.

  <out>/index.html            the viewer shell (`viewer.html`, verbatim)
  <out>/viewer.js|.css        the frontend (verbatim; the shell asks for both RELATIVELY)
  <out>/api/view              the map's data — every diagram, flow and colour (`exported: true`)
  <out>/api/health            the probe the page uses to decide it may show the source column
  <out>/api/tree              the file browser's tree, at the map's commit
  <out>/api/symbols           the code symbols search offers (empty without a pre-index)
  <out>/api/rawmap            the stored map, byte-for-byte (the map inspector reads this)
  <out>/api/src/<path>        every file tracked at the map's commit, as the code viewer reads them

WHAT AN EXPORT CANNOT DO, and why it is only this: the change-impact explorer and the code-diff view
project an ARBITRARY diff onto the map, which takes git and a running engine. Every other interaction
— every view, every drill-down, the source column, search over elements, files and symbols, the map
inspector, the shareable links — is answered from the files above and works unchanged.

The addresses are the served ones, so the frontend needs no static-mode fork: one `viewer.js` renders
both. That is deliberate. The moment the two spellings differ, an export starts drifting away from
the viewer it is meant to be a copy of, and only a person opening a hosted map would ever find out.
`tests/test_export.py` runs the browser over an exported folder for the same reason.

Stdlib only (subprocess + json), like the rest of the render path — see the dependency firewall note
in `serve.py`. `coyodex export` is the entry point.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from coyodex.viewer.serve import (
    _FRONTEND_DIR,
    _STATIC_FILES,
    TEXT_MAX,
    Project,
    _git,
    _valid_commit,
    load_project,
    project_symbols,
    project_tree,
    project_view,
    safe_rel,
)

# GitHub Pages runs Jekyll over a published folder unless this file is present, and Jekyll drops
# every path starting with `_` or `.`. A repo with a `_config` or `__init__.py` in it would lose
# those files from the code viewer for no reason the publisher could see.
NOJEKYLL = ".nojekyll"
README = "README.md"


class ExportError(Exception):
    """Something the publisher must fix before the folder is worth hosting."""


_README_TEXT = """# A coyodex map, as a static site

This folder is a whole coyodex map: the diagrams, the text on every box, and the project's code at
the commit the map describes. It is plain files — nothing runs on the server.

## Reading it on your own machine

It has to be SERVED. Do not double-click `index.html`: a browser never runs a page's script when the
page comes straight off the disk, so you get an empty shell. (Open it anyway and the page tells you
this, with the commands below already filled in for your folder.)

In a terminal in this folder, whichever your machine has:

```
python3 -m http.server 8000
ruby -run -e httpd . -p 8000
npx serve -l 8000
```

Then open <http://localhost:8000/>.

## Publish it

Copy the folder onto any web host and open `index.html` through the host's address:

* **GitHub Pages** — commit it (say, as `docs/map/`) and turn Pages on for that folder.
* **Netlify / Vercel / Cloudflare Pages** — drag the folder in; there is nothing to build.
* **A cloud bucket or an intranet server** — upload the folder and serve it as a site.

Anyone with the link can then read the map, with no repo and no coyodex install. Who is allowed to
open it is the host's business: a public site is public, and a private one uses the host's own
access control.

## What a reader gets

Every view and drill-down, the file browser and the code at the map's commit, search over elements,
files and code symbols, and links that open on one exact screen. The change-impact explorer is the
one thing missing: projecting a diff onto the map needs git and a live server.

## Keeping it current

The export is a snapshot, pinned to one commit, like the map itself. After the map changes, run
`coyodex export` again and republish.
"""


@dataclass
class ExportReport:
    """What one export wrote — the numbers `main` prints and the tests assert on."""

    out: Path
    slug: str
    commit: str
    files: int = 0                       # code files written under api/src/
    bytes_written: int = 0
    skipped_large: list[str] = field(default_factory=list)   # over TEXT_MAX (the server refuses these too)
    skipped_unsafe: list[str] = field(default_factory=list)  # a path that failed safe_rel — never seen in practice
    symbols: int = 0                     # code symbols search will offer (0 = no pre-index shipped)


# ── the code at the map's commit ─────────────────────────────────────────────────────────────────
# One `git ls-tree -l` names every file with its size and object id; one `git cat-file --batch`
# streams their contents. Two processes for a whole repo, rather than one `git show` per file.
#
# NOT `git archive`: it honours `export-ignore` in the repo's own .gitattributes, so a repo that
# marks a directory export-ignore would produce an export whose code viewer is silently missing
# files the map links to — a difference from the served viewer that nobody would think to look for.


def _ls_tree(repo_root: Path, commit: str) -> list[tuple[str, str, int]]:
    """(path, blob-oid, size) for every FILE tracked at ``commit``. Non-blobs (a submodule's commit
    entry) are left out: there is nothing to serve for one."""
    if not _valid_commit(commit):
        return []
    code, out = _git(repo_root, ["ls-tree", "-r", "-l", commit])
    if code != 0:
        return []
    rows: list[tuple[str, str, int]] = []
    for line in out.decode("utf-8", "replace").splitlines():
        meta, _, path = line.partition("\t")
        bits = meta.split()
        if len(bits) != 4 or bits[1] != "blob" or not path:
            continue
        mode, kind, oid, raw_size = bits  # `ls-tree -l` fields: mode type oid size
        del mode, kind
        try:
            size = int(raw_size)
        except ValueError:
            continue
        rows.append((path, oid, size))
    return rows


def _write_blobs(repo_root: Path, rows: list[tuple[str, str, int]], dest: Path,
                 report: ExportReport) -> None:
    """Write each blob in ``rows`` to ``dest/<path>``, reading them all from one `cat-file --batch`.

    The batch protocol is `<oid> SP <type> SP <size> LF <contents> LF` per request, and the reader
    below CHECKS the oid and size it gets back against the ones `ls-tree` gave. A framing mistake
    here would otherwise write one file's bytes under another file's name — an export that looks
    complete and is quietly wrong. A mismatch stops the export instead.
    """
    wanted = [r for r in rows if r[2] <= TEXT_MAX]
    for path, _oid, size in rows:
        if size > TEXT_MAX:
            report.skipped_large.append(path)
    if not wanted:
        return
    stdin = "".join(f"{oid}\n" for _p, oid, _s in wanted).encode("ascii")
    proc = subprocess.run(["git", "-C", str(repo_root), "cat-file", "--batch"],
                          input=stdin, capture_output=True, timeout=600)
    if proc.returncode != 0:
        raise ExportError("could not read the project's files out of git "
                          f"({proc.stderr.decode('utf-8', 'replace').strip()[:200]})")
    buf, pos = proc.stdout, 0
    for path, oid, size in wanted:
        nl = buf.find(b"\n", pos)
        if nl < 0:
            raise ExportError(f"git's file stream ended early, at {path}")
        header = buf[pos:nl].decode("utf-8", "replace").split()
        if len(header) != 3 or header[0] != oid or header[1] != "blob" or header[2] != str(size):
            raise ExportError(f"git returned {' '.join(header)!r} where {oid} blob {size} was "
                              f"expected, for {path} — the export would be wrong, so it stopped")
        start = nl + 1
        data = buf[start:start + size]
        pos = start + size + 1  # +1 for the LF git puts after the contents
        target = _safe_target(dest, path)
        if target is None:
            report.skipped_unsafe.append(path)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        # The directory now EXISTS, so resolve it: `--force` can point at a folder someone already
        # put a symlink in, and mkdir would have followed it straight out of the export.
        try:
            if target.parent.resolve() != dest and dest not in target.parent.resolve().parents:
                report.skipped_unsafe.append(path)
                continue
        except OSError:
            report.skipped_unsafe.append(path)
            continue
        target.write_bytes(data)
        report.files += 1
        report.bytes_written += len(data)


def _safe_target(dest_root: Path, rel: str) -> Path | None:
    """``dest_root/rel``, but only when it really lands inside ``dest_root``.

    `safe_rel` is the same gate the server puts in front of a READ; this repeats it on the WRITE
    side, because writing is where a bad name does lasting damage — a `..` or an absolute path would
    scatter a repo's files across the publisher's disk instead of into the export. ``dest_root`` is
    already resolved by the caller, so the containment test below is on real paths."""
    if not safe_rel(rel):
        return None
    target = dest_root / rel
    try:
        target.relative_to(dest_root)
    except ValueError:
        return None
    return target


# ── the export ───────────────────────────────────────────────────────────────────────────────────


def export_project(proj: Project, out: Path) -> ExportReport:
    """Write ``proj`` into ``out`` as a static site. ``out`` is created if it does not exist; the
    caller has already decided it is safe to write there (see `main`)."""
    report = ExportReport(out=out, slug=proj.slug, commit=proj.commit)
    api = out / "api"
    api.mkdir(parents=True, exist_ok=True)

    # The shell + the frontend, verbatim. The shell asks for its script and stylesheet RELATIVELY,
    # so the same file works here and under /coyodex/<slug>/ — nothing is rewritten on the way out.
    shutil.copyfile(_FRONTEND_DIR / "viewer.html", out / "index.html")
    for name in _STATIC_FILES:
        shutil.copyfile(_FRONTEND_DIR / name, out / name)
    (out / NOJEKYLL).write_text("", encoding="utf-8")
    (out / README).write_text(_README_TEXT, encoding="utf-8")

    # The page's questions, answered in advance under the addresses it actually asks.
    bundle = dict(project_view(proj))
    bundle["exported"] = True
    _write_json(api / "view", bundle)
    _write_json(api / "health", {"ok": True, "project": proj.slug, "commit": proj.commit})
    _write_json(api / "tree", project_tree(proj))
    symbols = project_symbols(proj)
    report.symbols = len(symbols)
    _write_json(api / "symbols", {"symbols": symbols, "commit": proj.commit})
    try:
        shutil.copyfile(proj.map_json, api / "rawmap")
    except OSError as e:
        raise ExportError(f"could not copy the map itself: {e}") from e

    src = api / "src"
    src.mkdir(parents=True, exist_ok=True)
    _write_blobs(proj.repo_root, _ls_tree(proj.repo_root, proj.commit), src.resolve(), report)
    return report


def _write_json(path: Path, obj: object) -> None:
    path.write_text(json.dumps(obj), encoding="utf-8")


# ── CLI ──────────────────────────────────────────────────────────────────────────────────────────

_HELP = """coyodex export — write a map as a static site you can host and share.

  coyodex export [<repo>] [--out <dir>] [--force]

  <repo>     the project folder holding .coyodex/project-map.json (default: the current folder)
  --out DIR  where to write the site (default: ./coyodex-export)
  --force    write into a folder that already has something in it

The folder it writes is plain files — no server runs on the host. Put it on GitHub Pages, Netlify, a
cloud bucket or any web server, and the link opens the same viewer `coyodex serve` shows, minus the
change-impact explorer (which needs git behind it). The site is pinned to the map's commit: after the
map changes, export again.
"""


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "-h" in args or "--help" in args:
        print(_HELP)
        return 0
    out_arg, force, folders = None, False, []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--out":
            i += 1
            if i >= len(args):
                print("coyodex export: --out needs a folder", file=sys.stderr)
                return 2
            out_arg = args[i]
        elif a == "--force":
            force = True
        elif a.startswith("-"):
            print(f"coyodex export: unknown option {a}", file=sys.stderr)
            return 2
        else:
            folders.append(a)
        i += 1
    if len(folders) > 1:
        print("coyodex export: one project folder at a time", file=sys.stderr)
        return 2

    # Resolved, because the project's NAME is its folder's name: `coyodex export .` would otherwise
    # produce a site that calls the project "project".
    root = (Path(folders[0]).expanduser() if folders else Path.cwd()).resolve()
    proj = load_project(str(root))
    if proj is None:
        print(f"coyodex export: no readable map in {root} "
              f"(expected {root}/.coyodex/project-map.json)", file=sys.stderr)
        return 1
    if not proj.commit:
        print("coyodex export: this map is not pinned to a commit, so there is no code to export "
              "with it. Rebuild the map, then export.", file=sys.stderr)
        return 1

    out = Path(out_arg).expanduser() if out_arg else Path.cwd() / "coyodex-export"
    # NEVER write into a folder that already holds something, unless told to. An export is many files
    # in many directories; pointed at the wrong place it would scatter them through someone's work.
    if out.exists() and any(out.iterdir()) and not force:
        print(f"coyodex export: {out} is not empty. Pass --force to write into it anyway, or "
              f"--out <dir> to pick somewhere else.", file=sys.stderr)
        return 1
    try:
        report = export_project(proj, out)
    except ExportError as e:
        print(f"coyodex export: {e}", file=sys.stderr)
        return 1

    print(f"coyodex export: wrote {report.out}")
    print(f"  {report.slug} at commit {report.commit[:10]} — "
          f"{report.files} code files, {report.bytes_written / 1_048_576:.1f} MB")
    if not report.symbols:
        print("  NOTE: no code symbols. Search will find elements, files and terms, but not classes "
              "or functions. Build `.coyodex/preindex.json` (coyodex preindex .) and export again.")
    if report.skipped_large:
        print(f"  {len(report.skipped_large)} file(s) left out for being over "
              f"{TEXT_MAX // 1_000_000} MB — the served viewer refuses these too: "
              f"{', '.join(report.skipped_large[:3])}"
              + (" …" if len(report.skipped_large) > 3 else ""))
    if report.skipped_unsafe:
        print(f"  {len(report.skipped_unsafe)} file(s) left out for an unsafe path: "
              f"{', '.join(report.skipped_unsafe[:3])}", file=sys.stderr)
    print("  To read it here, serve the folder — a browser will not run the viewer's script off the "
          "disk, so opening index.html directly shows an empty page (which says so, and gives you "
          "these commands):")
    print(f"    cd '{report.out}' && python3 -m http.server 8000")
    print("    then open http://localhost:8000/")
    print("  To share it: put the folder on a web host and send that link.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
