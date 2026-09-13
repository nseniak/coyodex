#!/usr/bin/env python3
"""The static export: does a folder of files really behave like the served map?

Two halves, and the second is the one that matters.

The first half checks the FILES: every address the page asks for is written, the code comes back at
the path the viewer spells, and no repo path can put a file outside the export folder.

The second half opens a REAL BROWSER on an exported folder served by a plain file server — no
coyodex server anywhere — and drives it. That is the only check that can see the export drift away
from the viewer: a new question `viewer.js` learns to ask the server is a question the export does
not write down, and every file-level assertion here would stay green while a hosted map broke.
`plain_file_server` deliberately uses the stdlib's own static handler, because a static host is
exactly what it is standing in for.

Conventions: top-level test functions, no classes/fixtures (helpers are `make_*` / `_*`).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import threading
from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterator
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from coyodex.viewer.export import ExportError, _safe_target, export_project, main
from coyodex.viewer.serve import load_project

_FIXTURE_MAP = Path(__file__).resolve().parent / "fixtures" / "mcpolis-project-map.json"

# Every address the page asks a server for, that an export must answer with a file. The code files
# live under api/src/ and are checked separately.
_ADDRESSES = ["api/view", "api/health", "api/tree", "api/symbols", "api/rawmap"]


# --- builders -------------------------------------------------------------------------------------
def make_git_repo(root: Path, files: dict[str, str]) -> str:
    """Init a git repo at `root`, write + commit `files` (path -> text), return the commit SHA."""
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t", "GIT_CONFIG_GLOBAL": "/dev/null",
           "GIT_CONFIG_SYSTEM": "/dev/null"}
    run = lambda *a: subprocess.run(["git", "-C", str(root), *a], check=True,  # noqa: E731
                                    capture_output=True, env=env)
    root.mkdir(parents=True, exist_ok=True)
    run("init", "-q")
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    run("add", "-A")
    run("commit", "-q", "-m", "init")
    out = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], check=True,
                         capture_output=True, env=env)
    return out.stdout.decode().strip()


def make_mapped_repo(parent: Path, name: str, extra: dict[str, str] | None = None) -> Path:
    """A real git repo holding the fixture map, re-pinned to its own commit — so the export has
    actual code to read, the way a mapped project does."""
    root = parent / name
    files = {"README.md": "# a project\n", "src/app.py": "def run():\n    return 1\n"}
    files.update(extra or {})
    root.mkdir(parents=True, exist_ok=True)
    (root / ".coyodex").mkdir(parents=True, exist_ok=True)
    shutil.copy(_FIXTURE_MAP, root / ".coyodex" / "project-map.json")
    sha = make_git_repo(root, files)
    m = json.loads((root / ".coyodex" / "project-map.json").read_text())
    m["commit"] = sha
    (root / ".coyodex" / "project-map.json").write_text(json.dumps(m))
    return root


@contextmanager
def make_export(extra: dict[str, str] | None = None) -> Iterator[Path]:
    """A mapped repo, exported. Yields the export folder."""
    with tempfile.TemporaryDirectory() as td:
        root = make_mapped_repo(Path(td), "alpha", extra)
        proj = load_project(str(root))
        assert proj is not None
        out = Path(td) / "site"
        export_project(proj, out)
        yield out


@contextmanager
def plain_file_server(folder: Path) -> Iterator[str]:
    """The stdlib's own static file handler over `folder` — a stand-in for any web host. It runs no
    coyodex code at all, which is the point: whatever the page manages here, it manages on GitHub
    Pages."""
    handler = partial(SimpleHTTPRequestHandler, directory=str(folder))
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}/"
    finally:
        httpd.shutdown()
        httpd.server_close()


@contextmanager
def _page(url: str) -> Iterator[Any]:
    """A Chromium page on `url`, first-run overlay dismissed, JS errors collected on `js_errors`."""
    playwright = pytest.importorskip("playwright.sync_api", reason="playwright not installed")
    with playwright.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as exc:  # driver installed, browser binary not
            pytest.skip(f"chromium not available: {exc}")
        page = browser.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.js_errors = errors  # type: ignore[attr-defined]
        page.goto(url)
        if url.startswith("file:"):
            # The viewer never boots here — that IS the case under test. Wait for the shell's own
            # guard instead of a screen the page cannot reach.
            page.wait_for_timeout(1200)
        else:
            page.wait_for_selector("#crumb h1", state="attached")
            page.evaluate("() => { const b = document.getElementById('coachok'); if (b) b.click(); }")
        try:
            yield page
        finally:
            browser.close()


# --- the files ------------------------------------------------------------------------------------
def test_the_export_answers_every_address_the_page_asks_for() -> None:
    """A missing one is a screen that breaks only once the map is hosted."""
    with make_export() as out:
        assert (out / "index.html").is_file()
        assert (out / "viewer.js").is_file() and (out / "viewer.css").is_file()
        for addr in _ADDRESSES:
            assert (out / addr).is_file(), f"{addr} not written"


def test_the_shell_asks_for_its_script_and_style_relatively() -> None:
    """An absolute /static/ path works on a server rooted at / and nowhere else — a map published
    under https://host/repo/map/ would load no script and no stylesheet at all."""
    with make_export() as out:
        html = (out / "index.html").read_text()
        assert '"viewer.css"' in html and '"viewer.js"' in html
        assert "/static/" not in html


def test_the_exported_bundle_says_it_is_exported() -> None:
    """The one flag the page reads to know there is no server behind it."""
    with make_export() as out:
        assert json.loads((out / "api/view").read_text())["exported"] is True


def test_the_code_is_written_where_the_viewer_asks_for_it() -> None:
    with make_export() as out:
        assert (out / "api/src/src/app.py").read_text() == "def run():\n    return 1\n"
        assert (out / "api/src/README.md").read_text() == "# a project\n"


def test_the_map_itself_ships_byte_for_byte() -> None:
    """The map inspector reads the STORED map, so a re-serialised copy would name different slots."""
    with tempfile.TemporaryDirectory() as td:
        root = make_mapped_repo(Path(td), "alpha")
        proj = load_project(str(root))
        assert proj is not None
        out = Path(td) / "site"
        export_project(proj, out)
        assert (out / "api/rawmap").read_bytes() == (root / ".coyodex/project-map.json").read_bytes()


def test_a_repo_path_can_never_write_outside_the_export() -> None:
    """The write-side guard. Reading a traversal path is refused by the server; writing one would
    scatter a repo's files across the publisher's disk, which is worse and permanent."""
    with tempfile.TemporaryDirectory() as td:
        dest = (Path(td) / "site" / "api" / "src")
        dest.mkdir(parents=True)
        dest = dest.resolve()
        for bad in ["../escape.txt", "../../escape.txt", "/etc/passwd", "a/../../b", ""]:
            assert _safe_target(dest, bad) is None, f"{bad!r} was allowed out"
        ok = _safe_target(dest, "deep/nested/file.py")
        assert ok is not None and dest in ok.parents


def test_the_export_reports_a_map_with_no_symbols() -> None:
    """Search still works without a pre-index; it just finds no classes or functions. The command
    says so rather than leaving the publisher to discover it on the hosted page."""
    with make_export() as out:
        assert json.loads((out / "api/symbols").read_text())["symbols"] == []


def test_export_refuses_a_folder_that_already_holds_something() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = make_mapped_repo(Path(td), "alpha")
        out = Path(td) / "site"
        out.mkdir()
        (out / "someone-elses-work.txt").write_text("do not scatter files over me")
        assert main([str(root), "--out", str(out)]) == 1
        assert not (out / "index.html").exists()
        assert main([str(root), "--out", str(out), "--force"]) == 0
        assert (out / "index.html").is_file()
        assert (out / "someone-elses-work.txt").is_file()  # --force adds, it does not wipe


def test_export_names_the_project_after_its_folder_not_the_cwd() -> None:
    """`coyodex export .` must not produce a site that calls the project "project"."""
    with tempfile.TemporaryDirectory() as td:
        root = make_mapped_repo(Path(td), "alpha")
        out = Path(td) / "site"
        assert main([str(root) + "/.", "--out", str(out)]) == 0   # a path git would call "."
        assert json.loads((out / "api/health").read_text())["project"] == "alpha"


def test_export_refuses_a_map_with_no_commit() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = make_mapped_repo(Path(td), "alpha")
        f = root / ".coyodex" / "project-map.json"
        m = json.loads(f.read_text())
        m["commit"] = ""
        f.write_text(json.dumps(m))
        assert main([str(root), "--out", str(Path(td) / "site")]) == 1


def test_a_framing_mistake_stops_the_export_instead_of_writing_wrong_files() -> None:
    """The guard on `git cat-file --batch`: a size or id that does not match what `ls-tree` said
    would put one file's bytes under another file's name, and the folder would look complete."""
    from coyodex.viewer import export as export_mod
    with tempfile.TemporaryDirectory() as td:
        root = make_mapped_repo(Path(td), "alpha")
        rows = export_mod._ls_tree(root, load_project(str(root)).commit)  # type: ignore[union-attr]
        assert rows, "the fixture repo should have files"
        lied = [(p, "0" * 40, s) for p, _oid, s in rows]  # ids git will not return
        dest = Path(td) / "dest"
        dest.mkdir()
        with pytest.raises(ExportError):
            export_mod._write_blobs(root, lied, dest.resolve(),
                                    export_mod.ExportReport(out=dest, slug="a", commit="b"))


# --- the browser, over a plain file server ----------------------------------------------------------
def test_a_hosted_map_renders_and_navigates() -> None:
    with make_export() as out, plain_file_server(out) as url, _page(url) as page:
        page.evaluate("() => document.querySelector('[data-view=\"glossary\"]').click()")
        page.wait_for_timeout(700)
        assert page.evaluate("() => location.hash") == "#v=glossary"
        assert "Glossary" in str(page.evaluate(
            "() => (document.getElementById('crumb').textContent || '').trim()"))
        assert not page.js_errors, page.js_errors


def test_a_hosted_map_keeps_your_place_on_reload() -> None:
    """A shareable link is the whole reason the export exists."""
    with make_export() as out, plain_file_server(out) as url, _page(url) as page:
        page.evaluate("() => document.querySelector('[data-view=\"glossary\"]').click()")
        page.wait_for_timeout(700)
        page.reload()
        page.wait_for_selector("#crumb h1", state="attached")
        page.wait_for_timeout(700)
        assert page.evaluate("() => location.hash") == "#v=glossary"
        assert not page.js_errors, page.js_errors


def test_a_hosted_map_shows_the_source_column_and_loads_a_file() -> None:
    """The code viewer is the half of the export that needed a new address (`api/src/<path>`), so
    it is the half most likely to break."""
    with make_export() as out, plain_file_server(out) as url, _page(url) as page:
        assert page.evaluate("() => document.body.classList.contains('served')"), \
            "the source column never revealed itself — api/health was not reachable"
        loaded = page.evaluate("""async () => {
            const r = await fetch('api/src/src/app.py');
            return r.ok ? await r.text() : ('HTTP ' + r.status);
        }""")
        assert loaded == "def run():\n    return 1\n"
        assert not page.js_errors, page.js_errors


def test_a_hosted_map_offers_no_impact_explorer_and_no_way_back_to_a_server() -> None:
    """Both need a coyodex server. Offering either on a hosted page is a dead control."""
    with make_export() as out, plain_file_server(out) as url, _page(url) as page:
        assert page.evaluate("() => document.getElementById('impactctl').hidden") is True
        assert page.evaluate("() => !!document.querySelector('header .brand.home-link')") is False
        assert not page.js_errors, page.js_errors


def test_a_hosted_map_works_in_a_SUBFOLDER_of_the_site() -> None:
    """The GitHub Pages shape: https://user.github.io/<repo>/<folder>/, not the site root. Every
    address the page asks for is relative to its own directory, and this is the test that says so —
    an absolute one would 404 here while passing every root-served check above."""
    with make_export() as out:
        site = out.parent / "pages"
        (site / "myrepo").mkdir(parents=True)
        shutil.copytree(out, site / "myrepo" / "map")
        with plain_file_server(site) as base, _page(base + "myrepo/map/") as page:
            assert page.evaluate("() => document.body.classList.contains('served')"), \
                "the page could not reach its own api/ from a subfolder"
            assert page.evaluate(
                "() => getComputedStyle(document.querySelector('header')).display") != "block", \
                "the stylesheet did not load from a subfolder"
            assert page.evaluate(
                "async () => (await fetch('api/src/src/app.py')).status") == 200
            assert not page.js_errors, page.js_errors


def test_a_hosted_map_never_asks_for_an_address_the_export_did_not_write() -> None:
    """THE DRIFT GATE. Every request the page makes to its own origin is recorded; any that 404s is
    a question `viewer.js` learned to ask and the export does not answer. Without this, the export
    rots silently as the viewer grows, and only a person opening a hosted map would find out."""
    with make_export() as out, plain_file_server(out) as url, _page(url) as page:
        misses: list[str] = []
        page.on("response", lambda r: misses.append(f"{r.status} {r.url}") if r.status >= 400 else None)
        # Walk every view the map offers, which is where the page asks for what it needs.
        views = page.evaluate(
            "() => [...document.querySelectorAll('[data-view]')].map(b => b.dataset.view)")
        for v in views:
            page.evaluate(f"() => {{ const b = document.querySelector('[data-view=\"{v}\"]');"
                          f" if (b) b.click(); }}")
            page.wait_for_timeout(350)
        page.evaluate("() => { const s = document.getElementById('srcrail'); if (s) s.click(); }")
        page.wait_for_timeout(600)
        assert not misses, f"the hosted map asked for something the export did not write: {misses}"
        assert not page.js_errors, page.js_errors


def test_the_export_carries_a_launcher_anyone_can_double_click() -> None:
    """A browser cannot start a local server, so the folder has to bring one. Without the execute
    bit a double-click opens the script in a text editor instead of running it."""
    import os
    import stat
    from coyodex.viewer.export import LAUNCHER
    with make_export() as out:
        launcher = out / LAUNCHER
        assert launcher.is_file()
        assert os.stat(launcher).st_mode & stat.S_IXUSR, "the launcher is not executable"
        body = launcher.read_text()
        assert body.startswith("#!/bin/sh")
        # It must RUN each candidate, not just look it up: on a stock Mac `command -v python3`
        # finds a stub that cannot execute.
        assert 'probe python3 -c ""' in body
        assert "ruby" in body and "node" in body


def test_the_launcher_actually_serves_the_map() -> None:
    """Run it for real and fetch the page through it — the one check that the script is not merely
    well-formed text."""
    import shutil as _sh
    import subprocess
    import time
    from urllib.request import urlopen
    from coyodex.viewer.export import LAUNCHER
    if not _sh.which("python3") and not _sh.which("ruby"):
        pytest.skip("no runtime the launcher can use on this machine")
    with make_export() as out:
        port = "8731"
        proc = subprocess.Popen(["sh", str(out / LAUNCHER)], cwd=str(out),
                                env={**os.environ, "PORT": port, "PATH": os.environ.get("PATH", "")},
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            page = None
            for _ in range(50):
                try:
                    with urlopen(f"http://127.0.0.1:{port}/index.html") as r:
                        page = r.read().decode("utf-8", "replace")
                    break
                except Exception:
                    time.sleep(0.2)
            assert page and "coyodex viewer" in page, "the launcher never served the map"
        finally:
            proc.terminate()
            proc.wait(timeout=10)


def test_opening_the_export_as_a_local_file_says_what_to_do() -> None:
    """THE FIRST THING ANYONE DOES with a folder of files is double-click index.html, and a browser
    refuses to run a module script off the disk — so `viewer.js` never executes and cannot report
    anything. Without the shell's own inline guard the reader gets the bare shell, tabs and all, and
    no explanation. That is exactly what happened the first time someone opened one."""
    with make_export() as out:
        with _page((out / "index.html").as_uri()) as page:
            text = str(page.evaluate("() => document.body.innerText"))
            assert "has to be served" in text, text[:400]
            assert "open-map.command" in text, text[:400]
            # the address is a LINK, not text to retype
            assert page.evaluate(
                "() => !!document.querySelector('a[href=\"http://localhost:8000/\"]')")


def test_a_served_export_never_shows_the_boot_guard() -> None:
    """The guard must not fire on a working page: the module sets the flag it watches for."""
    with make_export() as out, plain_file_server(out) as url, _page(url) as page:
        assert page.evaluate("() => window.__coyodexBooted") is True
        assert "has to be served" not in str(page.evaluate("() => document.body.innerText"))
        assert "could not start" not in str(page.evaluate("() => document.body.innerText"))


# --- the served viewer still works ------------------------------------------------------------------
def test_the_served_map_redirects_its_bare_address_to_the_slash_form() -> None:
    """Everything the page asks for is relative to its own directory now, so the slash is load-
    bearing: without it the browser drops the slug and every request resolves one level too high."""
    from coyodex.viewer.recents import RecentsStore
    from coyodex.viewer.serve import Handler, build_projects
    with tempfile.TemporaryDirectory() as td:
        root = make_mapped_repo(Path(td), "alpha")
        projects = build_projects([str(root)])
        slug = next(iter(projects))
        Handler.store = RecentsStore()
        Handler.projects = projects
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        try:
            with urlopen(f"{base}/coyodex/{slug}") as r:   # urllib follows the 301
                assert r.url.endswith(f"/coyodex/{slug}/")
            for name in ("viewer.js", "viewer.css"):       # the relative assets, under the map path
                with urlopen(f"{base}/coyodex/{slug}/{name}") as r:
                    assert r.status == 200 and r.length
            with urlopen(f"{base}/coyodex/{slug}/api/src/src/app.py") as r:
                assert r.read().decode() == "def run():\n    return 1\n"
            for bad in ("api/src/../../../etc/passwd", "api/src/"):
                try:
                    urlopen(f"{base}/coyodex/{slug}/{bad}")
                    raise AssertionError(f"{bad} was served")
                except HTTPError as e:
                    assert e.code == 400
        finally:
            httpd.shutdown()
            httpd.server_close()
