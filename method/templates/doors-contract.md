# Doors contract (T2b retrofit) — the copyable template

**Copy this file; do not retype it from prose.** The doors rule is ~9 KB of `method.md`, and every
build before this template hand-paraphrased it into a brief. A paraphrase of a rule this long is a
rewrite: on the 2026-09-01 argus build the brief was 9,031 bytes of hand-composed text with no gate
on the paraphrase, and the one rule it dropped (scheduled work is not an actor) was inert only by
luck — that map had no `kind: service` + `audience: internal` role for it to break.

1. Take the quoted block below and strip the leading `> ` from every line.
2. Fill ONLY the «angle-bracket» slots.
3. Change nothing else. If a rule reads wrong for this repo, fix it in `method.md` AND here, so the
   next build inherits the fix instead of re-deriving it.

**The slot leads keep under-filling is «FLOWS».** A doors agent works one batch of flows; naming
them by id, with their use case, is what keeps two agents from doring the same flow twice.

**The template starts at the quoted block below.** Everything above it is instructions to you, the
lead; nothing above this line goes into an agent prompt.

> You are putting SURFACES into stories on a coyodex codebase map — the "doors" retrofit.
>
> **NEVER `cd` into the coyodex clone.** Address both repos by ABSOLUTE path, always. A `cd`
> persists for the rest of your session, so a later relative `.coyodex/...` path silently reads
> the TOOL's own map instead of this project's — a wrong answer that looks like a right one. On the
> 2026-09-02 build 8 of 75 agents did this 33 times, because the rule lived only in the lead's guide
> and no agent had read it.
>
> **Your flows: «FLOWS».** Work only these; another agent has the rest.
> **The map:** «MAP». **The repo:** «REPO».
> **Surfaces already authored:** «SURFACES» — the `In` rows with their names and their `ways_in`.
> Use these; do not invent one.
>
> Do this work yourself — do NOT spawn your own sub-agents, and do NOT write a program that edits
> the map. Author the steps.
>
> ## What a door is
>
> A story crosses between an ACTOR and the product, and every crossing goes through a door.
> `Rn → Cn` and `Cn → Rn` are never the finished shape. Rewrite each into two steps with the
> surface in the middle: `Rn → In` then `In → Cn` coming in, `Cn → In` then `In → Rn` going out.
>
> **"Actor" means any `Rn` OUTSIDE the product** — a person, or a program somebody else runs.
> **The product's own scheduled work is NOT an actor here**, even though the map draws it as one: a
> role that is `kind: service` AND `audience: internal` is a timer, a boot hook or a signal handler
> inside the process. Read those two fields; do NOT read the role's name. BOTH are required — an
> internal HUMAN role is an operator, who very much comes in through a door. A flow such a role
> starts takes no arrival door, a step handing back to it is not a hand-off, and it never stands on
> the far side of a surface.
>
> ## Every crossing, not only the two ends
>
> 1. **The ARRIVAL.** The flow's FIRST step names the surface the actor comes in by.
> 2. **The FINAL HAND-OFF.** When the LAST step delivers to an actor, it goes out the same way —
>    **draw the out-door even when it is the SAME surface the story arrived by.**
> 3. **EVERY EXCHANGE IN BETWEEN.** A preview at step 4, a question answered at step 6: each one
>    takes a door too. An "endpoints only" rule was tried and REJECTED; do not reintroduce it.
>
> ## Which surface
>
> **The ARRIVAL: look it up, do not guess.** It is the surface whose `ways_in` hold the use case's
> `entry_points`. If those entry points sit on MORE than one surface, STOP and say so: two doors
> onto one goal is a use-case split, not a flow with two openings.
>
> **The HAND-OFF is the same surface only when the story ends where it began.** It is a DIFFERENT
> surface whenever the last step ends somewhere else, in three shapes: the result is delivered with
> no screen (a mail, a written file); the last step's component lives behind another surface; or the
> last step reaches a DIFFERENT ACTOR from the one who opened it. Read the LAST step, not the first.
>
> **A MID-STORY crossing takes the surface the actor is standing at RIGHT THEN. TRACK IT.** Read
> down the steps holding one fact: where is the person standing now? They start where the story
> opened, and stay there until a step MOVES them (a redirect out, a link handed over, a mail sent).
> **Do NOT use the `ways_in` lookup mid-story** — the map may author the RETURN address of a sign-in
> round trip as a way in of your own dashboard, and following it would say the person picked their
> account on your screen. They did not.
>
> **A trip out and back is ONE two-way door, at the surface they went to**: `Cn → I8`, `I8 → Rn`
> going out; `Rn → I8`, `I8 → Cn` coming back. Our own callback address is the PIPE on the return
> leg, and naming a pipe is what this rule exists to stop.
>
> **Name the surface the actor is really at, even when it puts a NEW box on the picture.** A
> redirect to a sign-in provider is THAT PROVIDER's screen, not the address that issued it. Picking
> an already-drawn box to keep the box count down is choosing the wrong surface.
>
> **A use case with no `ways_in` has no authored answer.** Pick the surface whose OWN SENTENCE
> describes where the actor stands. Only if none does is the map missing a surface.
>
> **If no surface fits, add NO door and SAY SO in the report you hand back** — naming the flow, the
> step, and what the person is really standing at. There is no field for it and you must not invent
> one. An invented door is worse than a missing one: the next reader cannot tell it was invented.
>
> **A flow whose LAST step is the actor acting AGAIN (`Rn → Cn`) still takes a door** — an inbound
> one — because it is a crossing like any other. It has no hand-off, and that is a smell worth
> reading twice: the story stops mid-conversation, so say in your report whether it is traced to its
> outcome or hands over to another use case.
>
> **Nothing OUTSIDE the step list changes.** A door is a STEP. The surface's own `carries` rows are
> authored separately and are not yours to touch.
>
> **A door is not only a way IN, and the direction is read off the INSIDE end** — never off whose
> surface it is. `Cn → In` and `In → Rn` are the product reaching OUT; `Rn → In` and `In → Cn` are
> the story coming IN. Both are commonly present on one surface (a request and its answer), and
> **neither maps to `side`**: the files a product writes are OUR surface written OUT through, and a
> chat platform is SOMEONE ELSE'S surface stories arrive IN from. Do not read `side` to decide a
> direction, and do not change `side` because of one.
>
> **An actor reaching a DEPENDENCY or a stored RECORD is a crossing too** (`Rn → D7`, `Rn → E3`) and
> takes the same treatment.
>
> **Name the surface, never the thing standing on it — and a dep and an actor differ.** A step
> reaching an outside SERVICE names the surface, and the dep is then DERIVED rather than drawn:
> `C12 → D7` becomes `C12 → I7`. A step reaching an ACTOR names the surface and the actor is KEPT:
> `C43 → R1` becomes `C43 → I3 → R1`. A dep is a pipe the surface replaces; an actor is somebody the
> surface stands in front of. Without either, a reader sees the PIPE and not the door — a flow that
> draws `web browser` as its only outside box is naming the thing this rule tells you never to name.
>
> ## Which phrase goes where
>
> Renumber the whole list and write both steps' phrases in the STORY's own words. **A phrase belongs
> to whoever ACTS in it**, so the old step's DIRECTION decides which step keeps it — never where it
> sits in the story.
>
> **INBOUND (`Rn → Cn`) — the old phrase is a HUMAN action, so it MOVES to the new actor step**, and
> the rewritten `In → Cn` gets a FRESH phrase in the surface's own voice. Leaving the human phrase on
> the surface step makes the map say *the dashboard clicks Add*. Measured: 11 of 11 arrivals came
> back with a screen doing a person's action.
>
> **OUTBOUND (`Cn → Rn`) — the old phrase is already the product's action, so it STAYS** on
> `Cn → In`, and the new `In → Rn` is written fresh, saying what the surface puts in front of them.
>
> **A phrase that is half GESTURE and half PAYLOAD splits between the two steps**, and most are. The
> gesture goes on the actor step; the payload becomes the surface step's own sentence. Do not move
> the whole thing and then hunt for something else to say.
>
> **When the phrase is ALL payload**, say what the surface GUARANTEES or CHECKS about what it
> carries. **If it genuinely guarantees nothing, say it passes the request on, and stop.** Do NOT
> invent a guarantee: a sentence that sounds like a check and is not one makes the map untrue, and
> no check anywhere can catch it.
>
> **A NOTE travels with the phrase it annotates**, so on an inbound crossing it moves out to the
> actor step.
>
> ## Anchors
>
> **An ANCHOR never sits on a step you create against an actor.** `In → Cn` and `Cn → In` are
> element-to-element and `validate` BLOCKS without a `where` or a `no_call_site`, so the rewritten
> step needs one and often did not have one before.
>
> **USE THE WAY IN'S OWN `source` LINE.** Pick the way in THIS STEP comes through and take its
> `source`. That works on every shape: a web page's way in IS its route line, a gateway's is its tool
> handler, a command line's is its command. Take the way in this step comes through, not the use
> case's own entry point, when a story moves between two of them.
>
> **This BEATS "keep the anchor it had" when they disagree**, and they disagree often: the old
> step's anchor is usually the CLICKED WIDGET, which describes the ACTOR step — and the actor step
> takes no anchor at all. On an INBOUND crossing, DISCARD that widget line. An anchor that was
> ALREADY on an actor step before you started is harmless; leave it.
>
> **Going OUT (`Cn → In`), anchor the line where the component DELIVERS to the surface** — the
> return, the render, the write — not the route. Use `no_call_site` when the wiring is genuinely
> event-driven or config-wired.
>
> ## Length
>
> A step with a surface at EITHER end does NOT count toward the 3–15 step band — it is structure,
> not detail. So doors LOWER a flow's counted length by one per crossing. If a doored flow now reads
> as too short, the flow was too short; the doors are not wrong.
>
> ## What to return
>
> Write your edits to `«REPO»/.coyodex/build-fragments/«AGENT_ID».json` yourself and return only
> that path, plus:
> - one line per flow: its id, how many crossings you doored, and which surfaces;
> - **every flow where no surface fitted**, with the step and what the actor is really standing at.
>
> Then run
> `«COYODEX_HOME»/.venv/bin/coyodex lint-fragment --repo «REPO» «AGENT_ID».json`
> and fix every row it reports until it exits clean, before you hand back.
>
> **With `--repo`, the verdict line ends with an anchor-drift count when any of your `where`s point
> at a line that cannot be acting** — an import, a comment, a `def`, a blank line. Read the FIRST
> line: `LINT OK — 0 problems, 3 advisory warning(s) (3 anchor drift)`. The drift rows are advisory
> and never fail the lint, which is exactly why they get missed: six fragments once passed clean and
> produced 86 drifted anchors at the lead's `validate`, costing fifty turns of repair after their
> authors were gone. This job is more exposed to it than most, because most of your anchors are NEW
> — anchor the line where the surface actually reaches the component, or set `no_call_site`.
