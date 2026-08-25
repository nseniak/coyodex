# Retro-checks — forward-declared verification for method and tool changes

A method or tool change is a promise about the NEXT build: "with this change, builds will do X
instead of Y". The gates cannot test that promise (they only prove nothing broke), the eval tests
it only in aggregate, and by the time the next retro runs, nobody remembers the promise existed.
This directory is where the promise is written down, in git, at the moment the change lands — so
the retro can collect every promise made since the last build and make each one come due.

The retro side of the contract is `eval/retro/method.md`, Step 0c: it diffs this directory across
`tool_commit` of the previous build → `tool_commit` of the build being reviewed, and runs every
check file that range added or modified.

## The convention

**Any commit that changes `method/` or `tools/` in a way that should change build behaviour also
adds one file here.** One file per change. Name: `<YYYY-MM-DD>-<slug>.md`. A pure refactor with no
intended behaviour change needs no file; if you are unsure whether behaviour changes, that doubt
is itself a reason to write the check.

A check file is a prose checklist an agent can settle against one finished build. Every item
must be OBSERVABLE in the build's outputs (the map, the build transcript, the validate/gate
output, the viewer) and must state its failure signature, not just its success:

```markdown
# <one line: the change this checks>

Change: <commit subject or short description> · <files touched>
Escalation: <when a failed item means "run the eval before accepting the map", say so>

## Checks
1. expect: <observable outcome, with the number and its noun where one exists>
   regression sign: <what it looks like when the change backfired>
2. ...
```

Rules, mirrored from the retro's own discipline:

- **Observables, not intentions.** "The agent understands rule 4 better" is not checkable.
  "The two sentences using 'in either kind' come out of the rebuild with both alternatives
  named" is.
- **Numbers keep their nouns.** "advisory count low" is weaker than "fewer than 5 indirect-
  reference advisories survive in the final map".
- **Name the backfire.** Most method changes can make prose worse while silencing their own
  counter. A check without a regression sign only ever confirms.
- **Escalation is explicit.** A check can end with "if this fails, run the eval" — the retro
  reports the trigger and hands it to the operator; it never runs the eval itself.

## Lifecycle

- **Armed** — the file sits in this directory. Every retro whose commit range includes the file
  runs it.
- **Re-armed** — editing an armed file (sharpening an expectation) makes the next retro run it
  again, even if a previous retro confirmed the old wording.
- **Verified** — when a retro confirms all items, it PROPOSES a commit moving the file to
  `verified/` with a `verified in <project> build of <built_at>` line appended. The operator
  commits the move. Files under `verified/` are history, never run again.
- **Failed** — a failed item becomes a finding in the retro's ledger and ranks with the rest;
  the file stays armed until the finding is resolved and a later retro confirms it.
