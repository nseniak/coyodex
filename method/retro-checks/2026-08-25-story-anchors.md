# Off-walk features get a story anchor, and the story column reads as one story

Change: one story column — the Features diagram's "Off the happy path" column is gone; every
feature sits in one column, the happy path unbroken and the off-happy-path features in a block after it,
ordered by an authored `capabilities[].story` anchor ({place: before|after, feature: CAPn}) with a
derived fallback (the feature's actors' last flow step). A `before` anchor on a walk feature is the
one placement that keeps an off feature among the happy path · method.md, method/model.md,
method/project-map.schema.json, tools/coyodex/model.py, validate_model.py, features.py, viewer.

Escalation: if check 3 fails (anchors placing features where the story misreads), run the eval
before accepting the map.

## Checks

1. expect: the next MCP Hero build authors a `story` anchor on each of its 2 off-happy-path features —
   "Marketing and self-serve onboarding" anchored `before` the organizations/sign-in feature
   (a prospect reads about the product BEFORE step 1), and "Conversational administration"
   anchored `after` the admin's last clicked feature (it is a chat variant of that work).
   regression sign: no anchors at all (the instruction was not read), or an anchor authored on a
   feature the walk already reaches (its position is derived; the anchor is dead weight there).
2. expect: every `story.feature` resolves to a defined capability id and never to the capability
   itself (`coyodex validate` reports zero problems from story anchors).
   regression sign: validate reports a dangling or self-referencing anchor.
3. expect: the rendered story column reads as the product story — lead-in features (anchored
   `before`) ahead of the walk's first feature, and the trailing block ordered so each variant
   feature follows the work it extends rather than landing last for want of an anchor.
   regression sign: an anchor that contradicts the walk's own reading (a marketing feature after
   onboarding is complete), or anchors invented to reorder ON-walk features.
