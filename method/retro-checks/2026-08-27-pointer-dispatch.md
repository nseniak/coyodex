# Contracts reach agents as pointers, not pasted bodies

Change: one dispatch rule under Phase 1's one-batch bullet — fill each agent's contract into a
scratch file and make the prompt three lines (agent id, absolute path, "read it completely") — and
the trace / skeptic / harvest dispatch paragraphs now say "a POINTER to its filled copy" where they
said "that file's contents" · method.md. Motive: dispatch latency scales with prompt bytes at
~230–320 bytes/s, so pasted contracts cost about an hour of typing per large build (the 2026-08-27
method assessment, item C1); a pasted copy can also drift mid-batch.

Escalation: none — a failed check here is waste or a thin brief, and the existing lint /
completeness checks already catch a thin brief's output.

## Checks

1. expect: in the next build, every fan-out prompt (harvest, trace, rules, skeptics, gap-fill) is a
   pointer brief of a few lines naming a contract file, and assertion 31 scores the FILE each one
   names, not the pointer.
   regression sign: any agent prompt over ~1 KB carrying contract body text, or assertion 31
   reading 0.00 against briefs that cite their use cases in the file.
2. expect: every pointed-at file exists before its agent launches, and no agent replies that it
   could not read its brief; the completeness check ("every prescribed slice came back with its
   sections") passes at the same rate as pasted-contract builds.
   regression sign: an agent works from the three-line prompt alone — its fragment misses whole
   sections its contract prescribed, which is the failure a pasted body could not have.
3. expect: dispatch wall clock for the biggest fan-out drops against the Cost log's previous build
   (the trace fan-out's launch window, first prompt emitted to last).
   regression sign: the launch window is unchanged because bodies are still being pasted, or agents
   burn their saving re-reading the contract repeatedly.
