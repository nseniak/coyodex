# Dispatch — what to do when coyodex is invoked

The user invoked coyodex on a repo. Decide the mode, then read the listed doc(s) **fully** and
follow them — don't restate them or work from memory. All tools live under this clone (`tools/...`).
The clone's `internal/` folder is design rationale, not the method — ignore it.

## Step 0 — did the user name a mode?

If the invocation explicitly names a mode — **`build`**, **`analyze`**, or **`accept`** (the verbs
the README teaches, e.g. `/coyodex analyze`) — do that mode directly: Build → `method.md`, Analyze /
Accept → `method/change-impact.md`. (Bare `/coyodex` names nothing, so fall through to Step 1.)

## Step 1 — is there already a baseline?

Look for `.coyodex/project-map.md` in the analyzed repo.

### No baseline → Build

Create it. Read `method.md` (+ `method/schema-v1.md`, `method/domain-cards.md`) and start from
`method/templates/project-map.template.md`.

### Baseline exists → default to Analyze (never silently rebuild)

A rebuild regenerates the map from scratch and **overwrites the curated, reviewed baseline** — it
loses manual fixes and the pin history. So it is **never** the default. Read the baseline pin from
the header (`**Commit:**` / `**Committed:**` line), then:

1. **Is there anything to analyze?** Compare the pin to the **current working tree** (so a later
   commit *and* uncommitted edits both count), ignoring coyodex's own files. The tree matches the pin
   only when there is no diff **and** no untracked file:

   ```
   git -C <repo> diff --quiet <pin> -- . ':(exclude).coyodex' \
     && [ -z "$(git -C <repo> ls-files --others --exclude-standard -- . ':(exclude).coyodex')" ]
   ```

   (Use the pin's bare sha; if the pin ends in `-dirty` it never matched a clean commit, so skip
   straight to Analyze.)

   - **Both true — current source == the pin** → the baseline is current. Tell the user
     `baseline is up to date @ commit <id> from <date>` and stop; do **not** produce an empty diff.
     (If only `.coyodex/project-map.html` is missing or stale, just re-render it with
     `tools/viewer/render.py` — that is a render, not a rebuild.)
   - **Otherwise — the source differs** (a later commit, uncommitted edits, or new files) →
     **Analyze**: read `method/change-impact.md` and follow it. The diff it computes is
     `git diff <pin>` (pin → working tree) plus any untracked files.

2. **Accept** — when the user says the report looks right, read `method/change-impact.md` (Accept).

3. **Rebuild** — only when the user *explicitly* asks to regenerate from scratch. Warn that it
   **overwrites the existing baseline and discards its curation and pin history**, get confirmation,
   then Build as above.

## Invariant (every mode)

The map is the single source at the analyzed repo's `.coyodex/project-map.md`. After every write,
validate (`tools/validate_analysis.py --check-sources`) then render (`tools/viewer/render.py`) — the
HTML is a rendering, never a second source.
