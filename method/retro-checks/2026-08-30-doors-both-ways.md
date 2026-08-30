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

**ENDPOINTS ONLY, and the blind spot is stated rather than hidden.** A strict rule — every crossing
to a person through a door — costs 126 steps across the two maps and was rejected on readability.
Endpoints costs 57. What that leaves uncovered: **a MID-FLOW crossing to a DIFFERENT surface is
checked by nothing.** The closing advisory says so in its own text, so a reader of a firing run
cannot mistake the check for complete coverage.

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

1. expect: every flow whose last step delivers to an actor goes out through a surface — `Cn → In`,
   then `In → Rn` — and the out-door is drawn even when it is the surface the flow opened at.
   regression sign: `validate` reports "flow(s) hand their result to an actor without going through
   a door". Aggregated to one line, so a build cannot lose it in volume.

2. expect: the eval sees BOTH halves. `flows_without_a_closing_door` reads 0 beside a healthy
   `interface_doors`.
   regression sign: `interface_doors` high and `flows_without_a_closing_door` high together — the
   openings were done and the closings were not. This is the reading that looks like success in every
   other count, which is why it has its own number. `flows_without_a_closing_door` reading `None` on
   a map with flows means the profile never computed it.

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
