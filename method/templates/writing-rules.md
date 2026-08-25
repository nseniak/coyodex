## Writing the text a person reads

Every sentence you author into a `purpose`, a trigger→outcome, a rule `statement`, a `risk`, a
`used_for`, a `wants` or a glossary meaning is read ONE BOX AT A TIME. The reader does not read
code, and has no paragraph around the box to lean on. Six rules:

1. **One idea per sentence, at most 20 words.** Two clauses joined by "and" are two sentences.
2. **No em dash.** Write the word that names the link: because, but, so, for example. In a
   one-sentence field a dash hides which of those you meant.
3. **No code in plain text.** No file path, no `name()`, no `--flag`, no snake_case identifier. The
   box already carries the code link, so the sentence exists to say what the thing DOES. A literal
   you must quote goes in backticks, which the check reads as a quotation rather than a name.
4. **Every reference resolves inside the same box.** The box is the unit of reading. A referring
   expression — "it", "this", "that X", "either X", "both", "the other", "such", "the same" — must
   point at something NAMED EARLIER IN THE SAME BOX. Within the box it is good prose: "…discovers
   each MCP's tools, then keeps that list fresh" is fine, and flattening it would be a loss. A
   reference whose antecedent lives in another box, or only in your head, is a defect: replace it
   with the names, or with the glossary words. Bad: "Mounting the MCP servers a team shares, in
   either kind" — the two kinds are named nowhere in the box. Good: "…a remote server at an
   address, or a command run for the team in a sandbox". The special case: an OPENING "It", "This",
   "That" or "They" can never resolve in-box, so never open with one.
5. **Use a glossary word, or add one.** A term the reader has not met belongs in the Glossary, never
   explained a second time in a second box.
6. **Plain words at the SAME precision.** "The system checks the user" is short and useless. Buying
   shortness by dropping the specific is worse than a long sentence.

`coyodex validate` counts rules 1 to 4 and reports them as advisories, so a build gets numbers back
rather than an opinion. Of rule 4 it counts the checkable part: an opening pointer word, and a
mid-sentence "either / both / such / the other" + category noun with no two alternatives named in
the same box. The rest of rule 4, and rules 5 and 6, are yours to obey.
