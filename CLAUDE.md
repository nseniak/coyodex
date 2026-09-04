# coyodex

## Glossary

The words we use when talking about this project. Use these; don't drift back to
the code's names.

**The product**

- **map** — the whole picture coyodex produces for a project: the diagrams, the
  plain-language text on every box, and the code links. Lives in `.coyodex/`.
- **baseline** — the map as currently accepted, pinned to a commit. What a
  change is compared against.
- **build** — analyzing a project from scratch and producing a new map. Throws
  away hand edits.
- **viewer** — the browser page that shows a map. Served live, never committed.
- **view** (a tab in the viewer) — one screen answering one question. Today:
  Features, Happy Path, Actors, Rules, Entities, Storage, Subsystems,
  Dependencies, Tests, Deployment, System, Glossary.
- **group** — the four tabs above the views: Product, Data, Under the hood,
  Glossary. A group is a set of tabs, never a page you can be on.
- **box** — one thing drawn on a view. **arrow** — a relation between two boxes.
- **code link** — the `file:line` a box points at. A box without one is
  ungrounded, which is a defect.
- **owner** (of a data area) — the feature the area's data exists FOR: the one
  that creates its records and runs their lifecycle. Authored, never derived.
- **owner with no evidence** — the map says an area exists for a feature, but no
  journey of that feature ever touches the area's records. A defect. Distinct
  from *ungrounded*, which is only ever about a missing code link.
- **interface** — one place where the product meets something that is not the
  product. It sends data or events that the product itself does not consume, or
  it receives data or events the product itself did not generate. Excluded: data
  the product writes only to read back (its own database, cache, queue); code and
  build artifacts that become the product; the pipeline that builds and tests it.
  An outside reader *the map records* beats the read-back exclusion. Two things
  are deliberately NOT criteria: who runs the machine, and whether the far side
  does something "business". The word also means a code declaration in a
  TypeScript or Java project, so a map of one shows both meanings.
- **kind** (of an interface) — what kind of thing an interface IS, in one word: a
  screen, a command line, an API, files, a handoff. There are eleven of these
  words. Kind is not PURPOSE: a payment service and a crash reporter are both
  an API, and what tells them apart is the dependency's own purpose word.
  The word *shape* was used for this and is retired: it appeared nowhere in the
  map, so every sentence had to say "the shape field, called kind".
  ALWAYS SAY WHAT IT IS THE KIND OF. Four different things carry a kind and the
  vocabularies do not overlap: an interface's (11 words, above), a way in's (11
  words, the mechanism: `mcp-tool`, `http-route`), an actor's (human or software),
  a dependency's (its context group). A bare "kind" names none of them.
- **who is on the far side** — the people the map can show standing at an interface.
  Never written by hand: it is worked out from the walks. An interface with nobody
  on it is a normal answer, because the product itself is what reaches most of
  the outside services.
- **our interface / their interface** — **ours** = we design it (our command
  line, our web pages). **theirs** = someone else does (a payment processor, a
  sign-in provider). The test: if the far side vanished tomorrow, would this
  thing's design change? The word *surface* was used for this and is
  retired: two words for one idea, and the screens said one while the glossary
  said the other. *Surface* survives only in its security sense, as in attack
  surface, which is a different word.
- **way in** — one address, command or tool an interface is made of. An
  interface groups many; coyodex's own command line is 32 ways in.
- **far side** — who or what is on the other side of an interface.
- **pipe** — something on the path to a far side that is not itself an interface: a
  reverse proxy, a log shipper, the library that calls a service. Name the far
  side, never the pipe.
- **what crosses** — the list on an interface saying, in each direction, what goes
  through it in one sentence, and which stored records. Naming no record is a
  normal answer: a log line, a fetched web page and a source file all cross
  without being stored.
- **user-facing / operator-facing** — who an interface serves. Written by hand, not
  worked out: the actor field that looks like it answers this asks a different
  question, and marks a bought payment service *internal* while its interface is
  user-facing.
- **door** — a crossing between an actor and the product, at an interface, in one
  story. Narrower: an interface is a place, a door is one crossing.
  A door works BOTH ways. A story arrives through one, and hands its result back
  through one, and the way out is drawn even when it is the same interface the
  story came in by. EVERY crossing takes a door, not only the two ends: an
  exchange in the middle of a story goes through one too. Two actors reaching the same goal
  through different doors are two use cases, and a gate blocks the map otherwise.
- **change impact** — the report saying what a code change does to the map.
- **accept** — folding a change-impact report into the baseline.
- **Coyote Effect** — the situation coyodex exists for: your agent wrote a lot
  of code, it runs, and you have lost track of what is under your feet.

**The viewer's screens** (see the Notion page "feature-driven map spec" for the
design principles these come from)

- **card** — one element, shown as its name, a pill saying what type it is, and
  one sentence. One design, used everywhere an element appears.
- **type pill** — the word on a card saying what kind of thing it is. Clicking
  it shows that element in context.
- **card list** — cards stacked down the page, to be read. **card grid** —
  cards across then down, to be chosen between. **grouped card list** — a card
  list cut into sections by a heading, where the cut is not a level (People and
  Software on Actors).
- **page hero** — the block at the top of a page about one element: its pills,
  the sentence saying what it is, one line of context. It does NOT carry the
  name; the breadcrumb does.
- **element details page** — everything the map holds about one element,
  reached by clicking its card. The info pane shows only the card.
- **home view** — the one view that draws a given element type. One function
  answers "which view shows this thing".
- **drill in** — click a card. A container opens its contents; anything else
  opens its own details.
- **show in context** — click the type pill. On a diagram, select and centre
  the box. On a card list, scroll to the card and briefly ring it.
- **view question** — the one sentence a view answers. It belongs to the view,
  not to any page, so it leads the content and never changes as you drill.
- **group tab row** — the strip of group tabs: Product, Data, Under the hood,
  Glossary. The first strip under the title bar.
- **view tab row** — the strip of view tabs, under the group tab row. With
  Product open it holds Features, Happy Path, Actors, Rules.
- **the trail** — the group tab row, the view tab row and the breadcrumb, read
  as one path. Where you are is the last item in it, and nothing else names it.
  The breadcrumb's last item is the page's title, so no page draws its own
  heading, and on a page about one element it carries that element's pills.
- **source column** — the file browser and the code viewer, on the right. It is
  optional on every screen. The **source rail**, a strip on the right edge,
  opens it; the × in its header closes it.
- **product overview** — the product description, leading the Features page.
- **shareable link** — a viewer address that names one screen, not just the map:
  which tab, how far you drilled, and what is selected. Copy it and someone else
  opens the same screen; reload and you keep your place. The browser's own Back
  and Forward walk it, and the viewer has no Back button of its own.
- **objective** — the labelled sentence at the top of a feature's page or an
  actor's page, saying what that feature or that actor is for.
- **timeline** — the picture on a feature's page and on an actor's page: one
  line of boxes, read left to right, in the order the happy path takes.
- **box** (on a timeline) — one block of the timeline. On a feature's page each
  box is one actor. On an actor's page each box is one feature. A second
  meaning of *box*: on a view it is one drawn thing (see above).
- **station** — a dot on the timeline's line, carrying the title of one happy
  path step.
- **side stop** — a circle under the timeline's line: something this feature or
  this actor can do that the happy path never reaches.
- **lane** — one of the timeline's two bands. The happy path is the upper lane,
  everything else is the lower one.
- **gutter** — the strip on the left of the timeline that names the two lanes.
- **Interfaces** (a view) — the tab under Product, after Happy Path. It answers
  "where does this product meet the outside world?" with two sections, We define
  and We use. Each card opens that interface's own page.
- **what it reaches out to** — the block on a feature's page listing the
  interfaces that feature calls out to. It reads *not stated* on most features,
  because a feature is linked to a service only when a step of its own walk is
  drawn at that service.

**How coyodex is delivered**

- **the method** — `method.md` and the files under `method/`: the instructions
  the coding agent follows to build a map. The product's real logic lives here,
  not in code.
- **the skill** — what `make install` puts into the agent so `/coyodex` works.
- **the tools** — the small programs the agent calls while building (indexing,
  code sizing, validation).

**Working on coyodex**

- **eval** — scoring two maps of the same project to tell whether a change to
  the method made map quality better or worse.
- **retro** — reading a finished build and its chat to find what went wrong in
  the process.
- **gates** — the automatic checks a change must pass before it counts as done:
  the full test run and the type checker. Green gates only prove nothing broke;
  they never prove a change to the method is an improvement.
- **test tier** — which set of tests a change requires; picked from what was
  touched. A path given to the test command silently skips whole tiers.
- **verdict** — how an eval run rates the new map against the baseline:
  **PASS** (as good), **DRIFT** (a measurement moved further than allowed —
  needs a human look, not automatically bad), **REGRESSED** (a hard check got
  worse — blocking).

The word **gate** is also used inside the product, with a different meaning:
there it is a check a *map* must pass. Failing one is a defect in the map, not
in the code.
