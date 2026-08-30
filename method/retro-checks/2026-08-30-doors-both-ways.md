# A door works both ways: a story arrives through one and hands its result back through one

Change (2026-08-30): a story's ARRIVAL and its FINAL HAND-OFF both go through a door. The arrival
half already existed and was already gated; the hand-off half is new (`Cn → In`, then `In → Rn`, and
drawn even when it is the SAME surface the story arrived by). `interfaces[].actors` gains a THIRD
and strongest source — any role standing at a step next to the surface — and `interfaces[].party` is
DELETED · method.md, method/model.md, method/project-map.schema.json,
method/templates/project-map.template.md, tools/coyodex/model.py, features.py, validate_model.py,
audit_model.py, views.py, json_schema.py, the viewer, eval profile and rubric.

Escalation: if check 2 fails as surfaces authored with openings and no closings, the rule was read as
half a rule — read the doors bullet in method.md before changing any wording, and do not accept the
map. If check 3 fails, the derivation is being second-guessed by an author writing a field that does
not exist, and `assemble` will say so.

## What this change is answering

**The arrival was gated and the hand-off was not, so a map could pass the doors gate having done half
the rule.** Measured on the two live maps the day it shipped: 57 stories ended at a person naming no
surface (coyodex 30, mcpolis 27), and neither map's `interface_doors` count could see it, because
that count rises on the openings alone.

**"ENDPOINTS ONLY" SHIPPED, AND WAS WITHDRAWN THE SAME DAY. Do not bring it back.** The first
version doored only a story's arrival and its final hand-off, on the argument that a strict rule
costs 126 steps and endpoints costs 57. **That 126 was measured on a map with NO doors**, so it
counted the arrival and hand-off steps that endpoints-only was going to door anyway. Nitsan read the
finished picture and asked the right question: mcpolis's invite story routes the admin through the
dashboard at step 1 and step 14, and straight past the dashboard at steps 11 and 12, for the SAME
person and the SAME component. One picture said the wall was there and also said it was not.

Re-measured on the DOORED map, the incremental cost of going strict is:

| | endpoints only | strict |
|---|---|---|
| steps on mcpolis | 579 | 615 (+36, +6%) |
| NEW boxes any picture gains | — | **0** — all 36 sit in a story that already draws its door |
| arrows across the 42 stories | 525 | **522** — fewer |
| stories with fewer arrows / same / more | — | 9 / 27 / 6 |
| the invite story's arrows | 14 | **12** |

The readability argument that bought endpoints-only runs BACKWARDS: the direct person-to-code lines
fold into door arrows already on the page. The only real cost is 6% more steps to scroll. **The
general lesson is the one to keep: a cost measured before a change is not the cost of finishing it.**
Three of the seven agents on this change flagged the same shape in their own words, one person on
both sides of one wall, and the number in the plan out-argued all three until it was re-measured.

**A proxy check was tried and rejected. Do not reintroduce it.** A draft read "the person at the end
is not the person at the start". It is machine-checkable, it fires on 3 flows, and it is blind to the
case that matters: same person, different door — sign up on the public website, get a confirmation
email. First person equals last person, so it stays silent and the email surface never gets its door.
Making the out-door UNCONDITIONAL is what removes the blind spot.

**`party` was deleted, not narrowed.** Over the 15 values on the two live maps, 14 repeated a
neighbour (a dependency standing on the surface, or a role the doors now put at it) and the
fifteenth repeated its own row's `what`. One clause was genuinely lost and was carried into `what` by
hand: mcpolis `I4` recorded an admin's AI client, and the row derives the PERSON rather than the
machine they point at.

## The bug found while writing the checks, which is the general lesson

**An advisory must not merely NAME its escape, it must HONOUR it.** The three retrofit gates all say
"record the use-case id under an 'Interface exceptions' extras heading", and all three read a set
built from `I`/`EP` tokens only, which silently dropped every `UCn`. Proven, not inferred: with all
38 of this repo's use cases recorded under exactly the heading the messages name, all three still
fired at full count. Two of the three had shipped a day earlier. The searchable signature is a
message naming one id family and a branch reading another.

## Checks

1. expect: EVERY step with an actor at one end and code at the other goes through a surface — the
   arrival, the final hand-off, and every exchange in between. `Rn → Cn` / `Cn → Rn` appears nowhere
   in a finished flow.
   regression sign: `validate` reports "flow step(s) ... cross between an actor and the product
   without going through a door". Aggregated to one line, so a build cannot lose it in volume. A
   report naming only MID-story step numbers, with the two ends clean, is the endpoints-only rule
   creeping back.

2. expect: the eval sees it. `crossings_without_a_door` reads 0 beside a healthy `interface_doors`.
   regression sign: `interface_doors` high and `crossings_without_a_door` high together — some doors
   were drawn and others were not. This is the reading that looks like success in every other count,
   which is why it has its own number, and why it counts STEPS rather than flows: a flow counter
   scores a half-doored story as done. `crossings_without_a_door` reading `None` on a map with flows
   means the profile never computed it.

3. expect: `actors` still never appears as an authored field, and the DOOR arm is still ungated.
   regression sign: an `assemble` failure naming `interfaces[].actors` (a build inventing a field the
   schema does not have); or a code change adding a `kind` gate to the door arm. That gate would be
   wrong for a reason worth restating: the gate on the `theirs` arm stops a bad INFERENCE, and a
   written step is not an inference — gating it discards what the map states in favour of what the
   code guesses.

4. expect: no map, fragment or template mentions `party`.
   regression sign: `assemble` or `validate` refusing a fragment with the removed-field sentence for
   `party`. That means a template or a worker contract still documents it, and the fix is the
   document, not the fragment.

5. expect: a flow near the bottom of the 3-15 band does not silently fall under it once doored.
   Doors count 0 toward the band, and the two REWRITTEN steps stop counting too, so a doored flow
   loses up to 2 from its counted length.
   regression sign: a step-count-band advisory appearing on a flow that was clean before its doors
   were added. Measured when this shipped: zero flows on either live map fall under. If one does, the
   flow was too short — never that the doors were wrong.

## The re-author of the surfaces, and what it says about the SHAPE instruction

`96-interface-kind.md` shipped its shape vocabulary with NO rebuild, so the instruction telling an
author how to pick a `kind` had never been read by anyone who was not in the design conversation.
On 2026-08-30 a fresh agent was given the repo and the instruction and asked to write mcpolis's
outside edge from scratch, with no sight of the answer already committed. **It wrote 16 surfaces
where the committed map has 12**, and the differences are the finding. The 12 were kept — the
re-author was a measurement, not a replacement — and these are the gaps it exposed:

1. **`facing` has no tiebreak, and two runs answered it differently on the same code.** The rented
   sandbox exists so a customer's server runs, and only an operator holds the account. One run wrote
   `user`, the other `operator`, and the instruction decides neither. Every bought service has this.
2. **Outgoing email sets two rules against each other.** "Mark the SERVICE, never the library" points
   at the mail relay and gives `api`. "Name the far side, never the pipe" makes the relay a pipe and
   the mailbox the far side, which gives something else. The fresh run minted a new kind, `email`,
   and called the surface `theirs`; the committed map says `api` and `ours`. `side` is undecidable
   from the text here too: email's shape is a public standard (`theirs`) and we write the message
   (`ours`), and both survive the "would its shape change" test.
3. **The split rule is one clause short.** "Split when the AUDIENCES differ" cannot separate the
   operator's web console from the operator's tool server: one audience, two shapes. A row carries
   one `kind`, so the rule needs "split when the SHAPE differs" beside it.
4. **Whether configuration is a surface is never stated.** The `settings` seed exists, which is the
   only hint. One run included the deployment settings, the other did not.
5. **There is no size floor.** A dashboard sending each server's hostname to a free icon service fits
   the definition exactly and is tiny. Nothing says whether a reader wants it.
6. **A health probe and the run command are uncovered.** The exclusion list names build and test
   pipelines only, and `command-line` is a seed.

One rule was reported as working perfectly and should be kept verbatim: *"An HTTP address that only
serves the product's own front end belongs to that front end's surface"* settled about 200 endpoints
with no thought needed.

The instruction's own numbers held: 6 of the 11 seeds were used and exactly one kind was minted,
which is check 4's "at most one mint" in `2026-08-29-interfaces.md` passing on its first real trial.

## The retrofit itself, and the six things the rule never said

The 42 mcpolis flows were doored by five parallel workers on 2026-08-30, each reading only the new
rule and its own batch. It worked — `interface_doors` went from 0 to 129 and the closing gate from 27
to 0 — and every one of the six gaps below was found by a worker, not by a check. Four of the five
found the FIRST one independently, which is what makes it the one to remember.

1. **"The step keeps the phrase it already had" gave the surface a person's voice.** An arrival's old
   phrase is a HUMAN action, so leaving it on the rewritten `In → Cn` step made the map say *the
   dashboard clicks Add*, and made the new step and the kept step say one thing twice. 11 of 11 in
   one batch. The rule is now asymmetric: at the ARRIVAL the old phrase MOVES to the actor step and
   the surface step is written fresh; at the HAND-OFF the old phrase is already the product's action
   and STAYS. If a future draft ever re-symmetrises those two ends, this is the paragraph it broke.
2. **The hand-off is often NOT the arrival surface, and the rule named only one reason.** "Unless the
   last step plainly delivers somewhere else (a mail, a written file)" reads as non-interactive
   delivery only. Three workers hit two more shapes: the last step's component lives behind ANOTHER
   surface (set up on the dashboard, answered at the gateway), and the last step reaches a DIFFERENT
   ACTOR from the one who opened the story (an admin sets a rule, a member's assistant is refused).
   All three chose correctly on their own judgment, and a literal reading would have drawn a gateway
   refusal on a dashboard screen.
3. **The anchor for a web page had two defensible answers, and one worker used both.** The route line
   that mounts the page, or the clicked widget's own line. Four of eight flows in one batch needed a
   supplied anchor, so it is not a corner case. The rule now names the ROUTE line, and separately
   says a `Cn → In` step anchors where the component DELIVERS to the surface.
4. **The rule named an upkeep job as an actor in one breath and as a timer in the next.** mcpolis's
   `R6 Upkeep job` starts 7 of its 42 flows from inside the process. Both readings of the text
   applied and they disagreed. The test is now the two FIELDS, never the name: `kind: service` AND
   `audience: internal` is the product's own work and takes no arrival door. Those 7 flows are the
   whole difference between the 42 that mechanically open at a role and the 35 that owe a door.
5. **A pipe was hiding in shared machinery, and no check could see it.** `owed_migrations` read
   `m.flows` and never `m.subflows`, so mcpolis's "open a session to a mounted server" carried 3
   steps naming a dep that stands on a surface while `validate` reported zero owed. A sub-flow is
   ridden by several stories, so one unmigrated step there draws the pipe in every one of them. Fixed
   in the same change, reported under the sub-flow's OWN id, and the `Interface exceptions` heading
   gained its own key so it can adjudicate an `SFn`.
6. **The migration rule said `theirs` and the checker never agreed.** The checker migrated a step at
   any dep standing on any surface, and it was right: the mail service standing on our own outgoing
   email surface is exactly the step that gives that surface its story. The text now says ANY.

Two more came out of the correction round itself, once the phrase rule was fixed and re-applied.
**A note follows the phrase it annotates**, so at an arrival it moves out to the actor step: a note
reading "the bin only appears for an admin" explains a gesture, and pinning it to the machine step
left it annotating a sentence that no longer mentions the bin. And **re-voicing alone is not enough
when the human phrase already names the payload** — "drops the settings file in" followed by "carries
the settings file inward" is one fact said twice, the second time more weakly. An arrival whose human
phrase is an act of ATTENTION ("opens", "picks", "confirms") separates on its own; one whose phrase is
a HANDOVER needs the surface step to say what it GUARANTEES or CHECKS about what it carries. 4 of 7
in one batch, and 2 of 11 in another.

Two smaller ones, recorded without a rule change: a flow whose LAST step is the actor acting again
(`Rn → Cn`) has no hand-off and takes no out-door, which the rule now states and marks as a smell
worth reading twice; and a flow whose first step is a role who was ALREADY there ("leaves the audit
page in live mode") gets an arrival door that is close to fiction, which a test on "does the actor
actually cross here" would catch and a test on the shape of step 1 cannot.

**What the retrofit did NOT prove**, and this must not be reported as a rebuild: that the doors step
gets SCHEDULED at all in a real build. That failure has shipped twice, and only a full run catches it.

## What going STRICT then found, on the same 42 stories

Doing the middle of every story turned up things the two ends never could. All of it came from the
workers, none from a check.

1. **A story that stopped before its own outcome.** mcpolis's UC38 says in its own words *"they are
   emailed once, so they sign in again"*, and its last step was the product marking its own record.
   No step ever reached a person, so the outgoing-email surface had nobody on it and check (a) said
   so. Reading the code found the answer is TWO people, never at once: a per-person server mails the
   member, a shared team server mails the org admins instead. The story now ends with both, and the
   surface has its people. **The title and the outcome are still wrong for the shared branch** — on
   that path the member whose sign-in broke is never told at all.
2. **A surface with zero traffic got its first walk.** `I8 Google sign-in` was authored, carried a
   `hosted-screen` shape, and no story in the map had ever named it. Doing the mid-story crossings
   put the sign-in redirect through it in three stories. A surface no walk visits is a surface nobody
   can check, and only the strict rule reached it.
3. **The map is MISSING a surface, and the strict rule is what made the gap visible.** Two stories
   send a person to a MOUNTED SERVER'S OWN sign-in page, which the product does not host. There is no
   surface for it: `I7 Mounted MCP servers` is shaped `agent-tools` and its rows describe forwarded
   tool calls, not a person clicking Approve. Those two crossings currently route through the
   dashboard, which misnames the place. Recorded rather than papered over. Under the old rule the
   same moment was two direct person-to-code lines, which said nothing at all.
4. **"No new box" is a RESULT, not a target.** One worker picked an already-drawn surface over the
   true one specifically to keep this change's own "adds no new box" measurement true. That is the
   metric steering the map. The rule now says the sentence out loud: name the surface the actor is
   really at, even when it puts a new box on the picture.
5. **Two workers resolved the same anchor question opposite ways in one day**, leaving one map with
   two conventions for one shape. The old step's anchor is usually the CLICKED WIDGET, because the
   old step was the person clicking — and that line now describes the ACTOR step, which takes no
   anchor. The route line wins, and the rule says so rather than leaving it to taste.
6. **A crossing in shared machinery is drawn in every story that rides it.** One sub-flow step pushed
   a notice straight at a person, and both parent stories drew it. The crossing sweep now reports a
   sub-flow under its OWN id and step number: reading it off the expanded steps named a step number
   the parent flow does not have, and reported it once per riding flow. Same rule the two-door actor
   check already states, found again one function away.

## The check that asks whether a door is the RIGHT door

Every other door check verifies that a door EXISTS. None can tell a right door from a wrong one, and
that gap was measured rather than assumed: repointing EVERY door on the 42-story map onto the crash
reporter — a nonsense map — raised 2 advisories and **zero** blocking problems.

So a nudge was added: a person derived at a surface shaped `api` or `content` (one program calling
another). It names TWO causes, because either can be the wrong one — the walk names the wrong
surface, or the surface wears the wrong shape.

expect: 0, or a line the author has adjudicated.
regression sign: it fires on a surface nobody has looked at. On the nonsense map it names the crash
reporter with five roles at it. On the real map it fires ONCE, on outgoing email, and there the
answer is the SECOND cause: the mail really does land in front of a member, and `api` is the wrong
shape for it — the same row a fresh re-author of that section minted a new kind for. That agreement
between two independent routes is the strongest signal this change produced about the shape
vocabulary, and it is still unresolved.

### What the workers said about strict, unprompted

Three of three said keep it. The two cases they named are worth recording, because both are about the
MIDDLE of a story: an admin who was drawn behind an address at step 1 and beside it at step 6, for
the same component, three steps in a row; and a sign-in detour that under the old rule showed a person
wired straight into backend code while the surface box sat unused on the same picture. The cost they
named is real and small: one story went from 16 steps to 22, and a person who enters a screen, leaves
and re-enters now says that screen three times.

## The adversarial review, and what it broke

A fresh-context reviewer was pointed at the finished change and told that "this looks good" is a
failed review. It found **two blocking defects, eight serious ones, and three mutations that survived
the whole 2911-test suite**. All are fixed. The three worth carrying forward:

1. **TWO COPIES OF ONE IDEA, AND THEY DISAGREED.** "Who is an actor" was written out three times —
   in `interface_actors`, in the door checks, and in the eval profile — and two of them differed. The
   door checks exempted the product's own timer; the derivation did not. So a door closing onto that
   timer registered as a far side and SILENCED the advisory that exists to say a surface hands
   something over to nobody. Every gate stayed green, and the viewer published the product as
   standing outside itself. There is now ONE `outside_actor_ids`, read by all three.
   **The general rule: a definition written twice is a definition that will disagree with itself, and
   the disagreement shows up as SILENCE.**
2. **A MUTATION NOBODY THOUGHT OF.** Dropping half the timer exemption — exempting every INTERNAL
   role rather than every internal SERVICE role — passed all 2911 tests while hiding **46 of the 140
   findings on this repo's own map**, because internal HUMAN roles stopped owing doors. "17 of 17
   mutations caught" only ever means "the 17 the author imagined".
3. **A TEST THAT LOOPED OVER THE CONSTANT IT WAS TESTING.** Shrinking the machine-shaped kind
   vocabulary shrank the test with it, so the mutation stayed green. The vocabulary is now pinned
   literally. This is the third vacuous assertion this element has produced; the shape to look for is
   a test whose expectations are computed from the thing under test.

Three more worth naming, all now fixed: a scoped record (`UCn/doors`) silenced NOTHING while a bare
`UCn` silenced all three retrofit gates, which is exactly the shape `_recorded_ids`' own docstring
forbids; the "no interfaces authored" advisory named an escape the line reader could never parse, so
an author who followed the instruction was told nothing and the line fired forever; and a sub-flow
REFERENCE step was reported as an undoored crossing, demanding an edit its author cannot make.

**What the review CLEARED**, so nobody re-audits it: the `party` deletion is complete in both repos,
the `IFACE_KEY` widening does not over-match, and the door arm's missing kind gate is sound.

## The A/B: does the fixed method text actually work?

The wording was rewritten eleven times over this change, each time because a worker had guessed. That
raises the obvious question: is the text better, or just longer? It was measured rather than argued.

**The experiment.** Take the mcpolis flows from BEFORE any doors existed. Give a fresh agent the
method text and nothing else — no worklist, no pre-computed arrival surfaces, no corrections, one
pass. Score against the map that had taken THREE correction rounds to reach. Eight stories, chosen
because they are where the old text failed: the invite story (mid-story crossings, same-surface
out-door), the join story (a trip out to a sign-in provider), and the four upkeep-job timers.
The gold answer was written down before the agent started.

| | round 1 | round 2 (after seven more wording fixes) |
|---|---|---|
| stories whose door set matches the corrected map | **7 of 8** | **7 of 8** |
| stories whose STEP COUNT matches exactly | 6 of 8 | **7 of 8** |
| crossings left undoored in scope | 0 | 0 |
| timer stories wrongly given an arrival door | 0 | 0 |
| findings the worker raised | 11 | 9 |

**What that proves.** Work that took three rounds of correction now lands in one pass. The two
hardest fixes held on first contact: the phrase-voice rule (4 of 5 workers got it wrong before) and
the `kind`+`audience` timer test, which round 2 called decisive and needed no judgement on.

**Four of round 1's findings are GONE in round 2**, and each maps to a specific fix: "where does a
mid-story crossing happen" (replaced by tracking where the person is standing, which round 2 used
explicitly and did not question); "you tell me to say so but not where"; and two that were artefacts
of a truncated extract, not of the method.

**The invented-guarantee clause worked, visibly.** Round 1 wrote surface phrases ending "for this
team", "naming only this one address" — and admitted writing them to satisfy the clause rather than
because anything checked them. Round 2, with the clause softened to allow "it passes the request on",
wrote plain true sentences instead.

**What it does NOT prove, and the number to keep.** Round 2 raised nine findings, and THREE of them
were caused by text added in that very round. Each pass fixes real gaps and opens narrower ones:
round 1's findings were whole missing rules, round 2's are edge cases at rule boundaries (an anchor
when the surface is a screen and the component is a server endpoint; where a person stands AFTER a
round trip; a flow with two endings). **The findings converge; they do not reach zero.** Anyone
planning to "finish" this text should price that in.

**The one story the text misses in both rounds**, and it is the right kind of miss: the email story
still ends without naming who receives the mail. That fix never came from the doors rule — it came
from advisory (a) firing and an agent then reading the code. Running the round-2 output through
`validate` reports it. **Text plus check reach the right answer; text alone does not**, and that is
the division of labour the change is built on.

### Round 3: six stories the text had never seen

Rounds 1 and 2 used the same eight stories, so the wording had been shaped around them. Round 3 ran
the same protocol on six it had never touched, picked for a SHAPE the anchor rules never mention: the
gateway and the admin address are `agent-tools` surfaces with no page, no route and no click, and one
story's actor is a headless agent — a role that is a `service` and still outside the product.

**6 of 6 door sets matched the corrected map. 6 of 6 step counts matched.** Better than the tuned
batch, whose one miss needs a check rather than a sentence. **The text generalises.**

**And it raised 13 findings against round 2's 9** — the wording is harder to FOLLOW off the shape it
was tuned on, even though it produces the right answer. Three name the bias outright: there is no
anchor rule for middleware, the split-the-phrase paragraph assumes the actor has hands, and *"the
anchor rule is written for web pages and nothing else"*.

**The best finding shortened the rule instead of lengthening it.** A worker doing a gateway, where no
page and no route exists, went and read the surface's WAYS IN to get its line. That is the general
rule the page-shaped wording had been hiding: **a way in already carries the line where the outside
reaches the code**, and a web page's way in IS its route line. Four paragraphs of page-specific
instruction collapse into one sentence that works on every shape. Recorded because the pattern
generalises: *when a rule needs a special case for a new shape, look for the field that already
answers it for all of them.*

**One live defect it exposed.** 15 of the 58 surface-into-component steps on the mcpolis map are
still anchored on a clicked WIDGET rather than the way in. The anchor instruction reached one of the
three workers who touched those files, so one map carries two conventions — the very thing the rule
warns about, committed by the session that wrote the warning. Every one derives mechanically EXCEPT
where a story's steps run on a different page from its own entry point, which is an open finding of
its own; so this wants a worker, not a script.

## THE ENFORCEMENT AUDIT — which rules a tool can see, and which will drift unseen

The class of defect this change kept producing is not a wrong rule. It is **a rule no tool can see**,
which then drifts and looks exactly like nothing happening. So every rule in the doors text was
sorted by whether an instrument exists. Read this before adding another sentence to `method.md`.

### Enforced — a check fires when the rule is broken

| the rule | what watches it |
|---|---|
| every crossing goes through a door | the crossing sweep |
| the out-door is drawn even at the same surface | the same sweep |
| the product's own timer is not an actor | `outside_actor_ids`, one definition, shared |
| name the surface, never the pipe | the migration gate, flows AND sub-flows |
| a story opens at its own authored door | the opening gate |
| a door does not count toward the length band | the band's own exemption |
| a sub-flow reference step is not a crossing | `_is_undoored_crossing` |
| an `ours` surface that sends and reaches nobody | advisory (a) |
| a person at a machine-shaped surface | advisory (c) |
| **a door's anchor is the way in's own line** | **advisory (d)** |
| plain language, one idea, no code names | the prose checks |

### NOT enforced, and one of these is the most-broken rule in the change

- **WHICH surface a door uses.** Advisory (c) catches one slice — a person at an `api` or `content`
  shape. Nothing else. Repointing every door on a 42-story map onto the crash reporter raised 2
  advisories and zero problems.
- **The phrase voice**: the person's words must not end up on the surface step. **Four of five
  workers broke this**, which makes it the most-broken rule here, and it has NO instrument. The
  obvious check was built and measured and REJECTED: a gesture-word list scored 9 hits on a clean
  map, every one a false positive ("the console opens that team's pages", "ready to paste", "asks
  the person to pick an account" are all correct surface sentences), while missing a real defect
  ("flips one server's switch"). Bad precision and bad recall together. **Do not ship that check.**
  This rule is held by the wording alone and by nothing else.
- **A note travels with the phrase it annotates.** Checkable in principle, low value, not built.

### The pattern worth carrying to the next element

**Restate a rule in terms of a field the model already records, and it becomes a check.** "Use the
route line" is unenforceable, because nothing says what a route is. "Use the way in's own `source`"
is enforceable, because a way in is a field with a source on it. The second wording is also SHORTER.
When a rule needs a special case for a new shape, look for the field that already answers it for all
of them — that is where both the brevity and the instrument come from.
