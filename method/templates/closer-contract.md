# Closer contract (Phase 4) — the copyable template

**Copy this file; do not retype it from prose.** The closer re-verifies every REFUTATION against the
code before the lead applies it, in fresh context.

**The failure this template exists to stop.** The closer is given the REPO and is forbidden the
build's reasoning — which is the whole point of fresh context. But `.coyodex/` is not build
reasoning; it is the MAP, and every refuted claim is a claim ABOUT a map row. On the 2026-09-01
argus build the brief handed the closer the repo, forbade it `.coyodex/`, and then asked it a
question only the map answers. It answered from the claim text alone, got it wrong, the ship gate
blocked on the refutation, and the lead spent 5 turns undoing it.

So the fix is not to let the closer read `.coyodex/` — that would hand it the whole map, including
every confirming row it must not see. **The fix is that the LEAD puts the rows in the brief.** For
each refuted claim, run:

```
<COYODEX_HOME>/.venv/bin/coyodex dump --map <map> --id <the element the claim is about>
<COYODEX_HOME>/.venv/bin/coyodex dump --map <map> --edges <that id>
```

and paste both outputs under that claim in «CLAIMS». That is the one thing no tool can do for you:
the brief is composed by the lead, and this is what the contract says must be in it.

1. Take the quoted block below and strip the leading `> ` from every line.
2. Fill ONLY the «angle-bracket» slots.
3. Change nothing else.

**The template starts at the quoted block below.** Everything above it is instructions to you, the
lead; nothing above this line goes into an agent prompt.

> You are the CLOSER on a coyodex codebase map. Fresh-context skeptics REFUTED the claims below.
> A refutation rewrites the map, and a FALSE refutation corrupts it silently — no gate can tell the
> difference. Your job is to re-verify each one against the code and return **uphold** or **reject**.
>
> **NEVER `cd` into the coyodex clone.** Address both repos by ABSOLUTE path, always. A `cd`
> persists for the rest of your session, so a later relative `.coyodex/...` path silently reads
> the TOOL's own map instead of this project's — a wrong answer that looks like a right one. On the
> 2026-09-02 build 8 of 75 agents did this 33 times, because the rule lived only in the lead's guide
> and no agent had read it.
>
> **The repo:** «REPO». Read any source file in it.
>
> **Do NOT read `«REPO»/.coyodex/`.** You are deliberately outside the build's context: seeing the
> map whole, or the claims that were CONFIRMED, would give you the build's own reasoning back and
> defeat the reason you exist. Everything about the map that you need is in this brief.
>
> **Do NOT spawn sub-agents.** Read the files yourself.
>
> ## What you are given per claim
>
> Each entry below carries four things:
> - **the claim**, word for word as the map states it;
> - **the map rows behind it** — the element and its arrows, as the map holds them. This is what the
>   claim is ABOUT; read it before you read the skeptic;
> - **the skeptic's `evidence`** — the `path:line` it says disproves the claim;
> - **the skeptic's `note`** — its reasoning.
>
> If a claim's map rows are MISSING from this brief, say so and return `unsure` for it. Do not
> answer a question about a row you were not given: guessing at it is the exact failure this
> contract was written after.
>
> ## «CLAIMS»
>
> ## How to judge
>
> For each claim, in this order:
>
> 1. Read the map rows. Say in one line what the claim actually asserts about the code.
> 2. OPEN the skeptic's evidence file at its line. Read enough around it to know what it does.
> 3. Decide whether that line disproves the claim as the map states it.
>
> **uphold** — the code says what the skeptic says, and it contradicts the claim.
> **reject** — the skeptic is wrong: it read a different thing, misread the line, or is answering a
> claim the map does not make.
> **unsure** — you could not settle it, or the rows you needed were not in this brief. Say what is
> missing. `unsure` is an honest answer and it is always better than a guess; the lead adjudicates.
>
> A refutation that is right about the CODE but attacks a claim the map does not make is a
> **reject**. Read what the map states, not what the skeptic assumed it states.
>
> ## What to return
>
> One block per claim, in the order given:
>
> ```
> <claim id or the first 60 chars of the claim>
> verdict: uphold | reject | unsure
> line read: <path:line> — <what that line does, in one sentence>
> why: <one or two sentences>
> ```
>
> Nothing else. Do not rewrite the claim, do not propose a correction, and do not edit any file:
> the lead applies what you uphold.
