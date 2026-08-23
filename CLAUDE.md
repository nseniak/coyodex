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
  the shape. On a card list, scroll to the card and briefly ring it.
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
