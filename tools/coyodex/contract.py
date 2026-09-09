"""`coyodex contract <name>` — print exactly the text one fan-out agent should receive.

**Why this is a command.** A contract file is two documents in one: instructions to the LEAD at the
top, and the agent's prompt below. Which half is which was described only in prose, and the two
families describe it differently — harvest and trace wrap the agent half in a `>`-quoted block, the
rules and skeptic contracts put it after a `---`. Handing the wrong half to an agent is silent in
one of those shapes: a build filled the skeptic template with a single text replacement and sent the
whole file, so all ten skeptics received the lead's instructions as if they were their own, and four
were told to read a claims file that does not exist.

So the lead stops handling the file. It runs a verb, gets the agent half, and cannot send the header
because it never sees it. The shape difference becomes an internal detail of this module rather than
something every copy command has to know: the same change also retires the `sed 's/^/> /'` step the
writing-rules append needed, which was itself a shape rule a lead had to remember.

Authoring contracts get `method/templates/writing-rules.md` appended, because the agents that write
a map's reader-facing prose are exactly these workers and they never read `method.md`.

**Filling, and why it is the same command.** Printing the agent half left the lead with two jobs the
tool could do: replace the «angle-bracket» slots, and then compose the pointer prompt that sends the
agent to the filled file. Both were done by hand, and both went wrong in the measured way:

  * A slot left unfilled reaches an agent as the literal `«REPO»`, which no gate sees — the fragment
    it returns is well-formed and simply about the wrong thing. So `--fill` REFUSES on a slot with
    no value, on a value that is blank, and on a value that still carries guillemets.
  * A hand-composed brief grows. One build typed 159,993 bytes of brief across six fan-outs, at
    roughly 275 bytes a second — 9.7 minutes spent typing what a pointer says in three lines. So
    `--brief` PRINTS the pointer, and the printed thing is what gets sent. The cap below is not a
    request; a generated brief cannot exceed it, because it is an id, an absolute path and one fixed
    sentence.

`--slots` prints a ready-to-fill JSON skeleton, so the lead never types a slot name either.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

# Contract name → template file. The name is what a lead types, so it is the phase, not the filename.
CONTRACTS: dict[str, str] = {
    "harvest": "harvest-contract.md",
    "trace": "trace-contract.md",
    "rules": "rules-contract.md",
    "skeptic": "skeptic-contract.md",
    # The fifth slice every build has, and the one no template covered. Hand-composed briefs lose
    # the shared machinery: the gap-fill brief was the ONE trace-phase contract of eleven missing
    # "do NOT spawn sub-agents", and it lost four more blocks with it.
    "gapfill": "gapfill-contract.md",
    # The T2b doors retrofit. The rule is ~9 KB of method.md and every build before this template
    # hand-paraphrased it: the 2026-09-01 argus brief was 9,031 bytes of hand-composed text with no
    # gate on the paraphrase, and it dropped the scheduled-work-is-not-an-actor rule outright.
    "doors": "doors-contract.md",
    # The Phase-4 closer. Its brief was hand-composed, and on the 2026-09-01 argus build it handed
    # the closer the repo, forbade it `.coyodex/`, and then asked a question only the map answers.
    # The contract's whole job is to say that the LEAD must paste the `dump --id` / `dump --edges`
    # rows into the brief — the one thing no tool can do, because the lead composes the brief.
    "closer": "closer-contract.md",
    # Appended to ONE harvest brief only — the T5 owner's. The entity-card spec used to sit in the
    # shared harvest contract, where 13 of ~14 agents read a detailed job they were forbidden to do.
    "harvest-t5": "t5-addendum.md",
}

# Which contracts author reader-facing prose, and therefore carry the writing rules. A skeptic
# judges claims and a trace agent writes flow steps; neither authors a sentence a reader meets in a
# box, and a rule an agent cannot act on is prompt weight every one of them pays for.
AUTHORING: frozenset[str] = frozenset({"harvest", "rules"})

WRITING_RULES = "writing-rules.md"
_TEMPLATES = "method/templates"
_DIVIDER = "---"


def home() -> Path:
    """Where the method and its templates live. `COYODEX_HOME` wins, because that is the name every
    command in the method already uses; otherwise the installed package's own clone."""
    env = os.environ.get("COYODEX_HOME", "").strip()
    return Path(env).expanduser().resolve() if env else Path(__file__).resolve().parent.parent.parent


def agent_half(text: str) -> str:
    """The half an agent receives, whichever shape the template uses.

    A `>`-quoted template yields its quoted block with the marker stripped. A plain template yields
    everything after its single `---`. Both are detected from the text, never from the filename, so
    a template that changes shape keeps working and a template with NEITHER boundary raises rather
    than silently handing over a lead's instructions."""
    lines = text.splitlines()
    quoted = [i for i, line in enumerate(lines) if line.startswith(">")]
    if quoted:
        block = lines[quoted[0]: quoted[-1] + 1]
        return "\n".join(_unquote(line) for line in block).strip("\n")
    dividers = [i for i, line in enumerate(lines) if line.strip() == _DIVIDER]
    if len(dividers) == 1:
        return "\n".join(lines[dividers[0] + 1:]).strip("\n")
    if not dividers:
        raise ValueError("no agent boundary: the template has neither a `>`-quoted block nor a "
                         "`---` divider, so there is no way to tell the lead's half from the "
                         "agent's")
    raise ValueError(f"ambiguous agent boundary: {len(dividers)} `---` dividers, so the agent half "
                     f"is not defined; a plain template must have exactly one")


def _unquote(line: str) -> str:
    """Strip one `> ` marker. A blank quoted line is `>` with nothing after it."""
    if line.startswith("> "):
        return line[2:]
    return line[1:] if line.startswith(">") else line


def render(name: str, root: Path | None = None) -> str:
    """The full text to hand one agent: the contract's agent half, plus the writing rules when this
    contract's agents author prose a reader meets."""
    if name not in CONTRACTS:
        raise KeyError(name)
    base = (root or home()) / _TEMPLATES
    body = agent_half((base / CONTRACTS[name]).read_text(encoding="utf-8"))
    if name not in AUTHORING:
        return body + "\n"
    rules = (base / WRITING_RULES).read_text(encoding="utf-8").strip("\n")
    return f"{body}\n\n{rules}\n"


#: A slot in the agent half: the text between the guillemets is the key `--fill` looks up.
SLOT = re.compile(r"«([^«»]+)»")

#: The pointer brief's ceiling, in bytes. It is a CEILING and not a target: the generated brief is
#: an id, an absolute path and one fixed sentence, so it lands near 150 bytes on any real path and
#: this only fires on a path long enough to be a mistake. The number exists so the method can name
#: one, after a build typed 159,993 bytes of brief across six fan-outs.
BRIEF_MAX_BYTES = 400

#: The one sentence a pointer brief carries. Fixed text, so no build re-words it into a paragraph.
BRIEF_SENTENCE = "Read it COMPLETELY and follow it — it is your entire brief."


def slots(name: str, root: Path | None = None) -> list[str]:
    """Every slot in the text an agent actually receives, in the order it first appears.

    Read from the AGENT half, never from the template file: the lead's own instructions above the
    divider talk *about* «angle-bracket» slots, and a skeleton listing those would ask the lead to
    fill words that reach nobody.

    A KEY MAY NOT CONTAIN WHITESPACE. A slot whose key is a whole sentence
    (`«absolute paths this agent owns; list a directory first, then read each file»`) is unusable as
    a key: nobody types it, so the skeleton gets filled BY POSITION instead — and a positional fill
    is silent when it is wrong. Measured on the 2026-09-01 argus build: all four brief generators
    bound their slots positionally, across 51 of 55 briefs. `trace` already used bare tokens; this
    refusal is what stops the other templates drifting back."""
    seen: dict[str, None] = {}
    prose_keys: list[str] = []
    for key in SLOT.findall(render(name, root)):
        key = key.strip()
        if re.search(r"\s", key):
            prose_keys.append(key)
        seen.setdefault(key, None)
    if prose_keys:
        listed = "; ".join(f"«{k[:60]}»" for k in dict.fromkeys(prose_keys))
        raise ValueError(
            f"{CONTRACTS[name]} has {len(dict.fromkeys(prose_keys))} slot(s) whose key is prose, "
            f"not a name: {listed}. A key nobody can type is filled by POSITION instead, which is "
            f"silent when it is wrong. Rename each to a bare token (SLICE_KIND, FILES, "
            f"BACKGROUND …) and move the explanation OUTSIDE the guillemets.")
    return list(seen)


#: A behavioural id — the layer a structural slice exists to SERVE. `Rn` (role), `UCn` (use case),
#: `CAPn` (feature), `HPn` (happy-path step).
_BEHAVIOURAL_ID = re.compile(r"\b(?:CAP\d+|UC\d+|HP\d+|R\d+)\b")

def _slot_content_faults(name: str, values: dict[str, str]) -> list[str]:
    """Faults in what a slot was filled WITH, as opposed to whether it was filled.

    Measured on the 2026-09-02 build, and invisible to every other check because a filled slot is a
    filled slot:

    * **`SERVES` naming no behavioural id.** The whole point of that slot is that a structural slice
      is cut to serve the behavioural layer, and `method.md` says a brief naming no use case is a
      brief cut from the file tree. All 14 harvest briefs filled it with a MAP-SECTION NAME
      ("T5 domain model"), which reads like an answer and is not one. Assertion 31 went 1.00 → 0.00
      and the harvest came back with components carrying no backbone edge.

    (A second shape — a component budget on a slice that authors none — was tried and reverted; see
    the comment at the end of this function.)"""
    faults: list[str] = []
    serves = (values.get("SERVES") or "").strip()
    if serves and not _BEHAVIOURAL_ID.search(serves):
        faults.append(
            f"«SERVES» names no behavioural id: {serves[:80]!r}. It must list the `Rn` / `UCn` / "
            f"`CAPn` / `HPn` ids whose behavior runs through this slice's files — that is what "
            f"makes the slice cut to the behavioural layer instead of to the file tree. A "
            f"map-section name ('T5 domain model') reads like an answer and is not one: all 14 "
            f"briefs on one build filled it that way, and the harvest came back with components "
            f"carrying no backbone edge at all")
    # A batch id filled with a PATH. The skeptic contract composes `.coyodex/verify/claims-«CLAIMS».json`
    # and `verdicts-«BATCH».json` from these two, so a path here builds a file name that exists
    # nowhere — 38 of 38 briefs on one build named `claims-/Users/…/claims-backbone-1.json.json`.
    # SKEPTIC ONLY: the closer contract has its own «CLAIMS», a pasted block of claims and `dump`
    # output that carries `path:line`, and the first version of this check refused every closer fill.
    for key in ("BATCH", "CLAIMS") if name == "skeptic" else ():
        v = (values.get(key) or "").strip()
        if v and ("/" in v or v.lower().endswith(".json")):
            faults.append(
                f"«{key}» looks like a path, not an id: {v[:80]!r}. The contract composes "
                f"`.coyodex/verify/claims-«CLAIMS».json` and `verdicts-«BATCH».json` from these, so "
                f"each is the bare batch id between `claims-` and `.json` (`backbone-1`)")
    # NOT CHECKED HERE: a component budget on a slice that authors no components. It was written,
    # and it is reverted. `«SLICE_KIND»` is FREE TEXT — a real value is a sentence — so matching it
    # against words like `config` or `entit` refuses legitimate structural slices: "config loading
    # and startup", "HTTP routing and config parsing", "deployment scripts and the CI workflow"
    # were all refused by the version that shipped. And the remedy it demanded made the brief
    # WORSE: writing `0` puts "Expect roughly 0 components" in front of a slice that really has
    # seven. The retro's own reader called this half unimplementable before it was written, and was
    # right: catching it needs an ENUM of slice kinds, which the contract does not have.
    return faults


def fill(name: str, values: dict[str, str], root: Path | None = None) -> str:
    """The contract with every slot replaced — or a refusal naming exactly what is wrong.

    Refuses BEFORE writing anything, and reports every fault at once: a lead that has to re-run this
    three times to learn three missing slots is the brief→re-read loop this verb exists to end."""
    text = render(name, root)
    present = slots(name, root)
    faults: list[str] = []

    unknown = sorted(set(values) - set(present))
    if unknown:
        faults.append(f"no such slot in the {name} contract: {', '.join(unknown)} "
                      f"(its slots are: {', '.join(present)})")
    missing = [k for k in present if k not in values]
    if missing:
        faults.append(f"no value given for: {', '.join(missing)}")
    for key in present:
        if key not in values:
            continue
        value = values[key]
        if not isinstance(value, str):
            faults.append(f"«{key}»: value is {type(value).__name__}, not a string")
        elif not value.strip():
            faults.append(f"«{key}»: value is blank — a slot filled with whitespace reaches the "
                          f"agent as an empty instruction, which no gate can see")
        elif SLOT.search(value):
            faults.append(f"«{key}»: value still carries «guillemets», so it is a slot name and "
                          f"not a filled value")
    faults += _slot_content_faults(name, values)
    if faults:
        raise ValueError("; ".join(faults))

    out = SLOT.sub(lambda m: values[m.group(1).strip()], text)
    left = SLOT.findall(out)
    if left:  # unreachable by construction; a silent survivor is the whole failure mode
        raise ValueError(f"slot(s) survived the fill: {', '.join(sorted(set(left)))}")
    return out


def brief(agent_id: str, path: Path) -> str:
    """The three-line pointer prompt to SEND. The brief is generated, never composed."""
    agent_id = agent_id.strip()
    if not agent_id or agent_id.split() != [agent_id]:
        raise ValueError(f"agent id {agent_id!r} must be one word with no spaces — it is what the "
                         f"fan-out's completion notifications are named by")
    if not path.is_absolute():
        raise ValueError(f"{path} is not absolute. An agent does not share the lead's working "
                         f"directory, so a relative brief path resolves somewhere else or nowhere")
    text = f"{agent_id}\n{path}\n{BRIEF_SENTENCE}\n"
    size = len(text.encode("utf-8"))
    if size > BRIEF_MAX_BYTES:
        raise ValueError(f"the brief is {size} bytes, over the {BRIEF_MAX_BYTES}-byte pointer cap "
                         f"— the path alone is too long to send as a pointer")
    return text


_USAGE = ("usage: coyodex contract <" + " | ".join(CONTRACTS) + "> [--slots]\n"
          "       coyodex contract <name> --fill <slots.json|-> --out <file> [--brief <agent-id>]\n"
          "                                                                   [--force]\n"
          "       coyodex contract skeptic --from-batches <dir> --fill <slots.json> --out-dir <dir>\n"
          "                                [--votes <theme>=N]...\n\n"
          "Print exactly the text one fan-out agent should receive: the contract's agent half,\n"
          "with the writing rules appended for the phases whose agents author map prose\n"
          "(" + ", ".join(sorted(AUTHORING)) + ").\n\n"
          "  --from-batches  one skeptic brief per claims-*.json in <dir>, BATCH and CLAIMS filled\n"
          "            from the file names, --votes <theme>=N writing N voters (-a, -b, -c) over one\n"
          "            claims file. An existing brief is SKIPPED, never rewritten; the pointer\n"
          "            prompts to send are printed. Every build hand-wrote this loop with --force.\n"
          "  --slots   print a ready-to-fill JSON skeleton — every slot of THIS contract as a\n"
          "            key with an empty value, so no slot name is ever typed by hand.\n"
          "  --force   overwrite an existing --out. Without it an existing file is REFUSED: under\n"
          "            pointer dispatch a filled contract is an agent's whole brief, so rewriting\n"
          "            one rewrites the instructions of an agent that may still be running.\n"
          "  --fill    fill those slots and write the result to --out. REFUSES on a slot with no\n"
          "            value, a blank value, a value still carrying «guillemets», or a key that is\n"
          "            no slot of this contract — and reports every fault at once, so learning\n"
          "            three missing slots costs one run and not three.\n"
          "  --out     where the filled contract is written. Required with --fill; nothing is\n"
          "            written unless the fill is clean.\n"
          "  --brief   also print the three-line pointer prompt to SEND for that agent id: the id,\n"
          "            the absolute --out path, and one fixed sentence. That printed text is the\n"
          "            whole brief; a pasted contract is ~13 KB times the fan-out.\n\n"
          "  coyodex contract harvest --slots > slots.json          # fill the values, then:\n"
          "  coyodex contract harvest --fill slots.json \\\n"
          "                           --out /abs/scratch/h1.md --brief h1\n\n"
          "Without --fill it writes the unfilled agent half to stdout:\n"
          "  coyodex contract harvest > <scratch>/harvest-contract.md\n\n"
          "The lead never handles the template itself, so the lead's own instructions at the top\n"
          "of that file cannot reach an agent. COYODEX_HOME overrides where the templates are\n"
          "read from.\n")


BUDGETS_FILE = "budgets.json"


def record_budget(repo: Path, agent_id: str, expected: str) -> Path | None:
    """`<repo>/.coyodex/verify/budgets.json`: the component budget each harvest brief was handed,
    keyed by agent id. `lint-fragment --expect` checks one slice against its own budget; nothing
    summed the budgets against what shipped — 60 dispatched, 114 shipped, every slice over, and
    the guard added for an earlier build of the same shape was per fragment only. `finalize`
    reads this file. The digits in the slot are the budget (`~8` records 8); a slot with none
    (`a few`) records nothing, and the brief is still written."""
    digits = "".join(ch for ch in expected if ch.isdigit())
    if not digits:
        return None
    path = repo / ".coyodex" / "verify" / BUDGETS_FILE
    try:
        doc = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    except ValueError:
        doc = {}
    harvest = doc.setdefault("harvest", {}) if isinstance(doc, dict) else {}
    harvest[agent_id] = int(digits)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return path


def batch_ids(batches_dir: Path) -> list[tuple[str, str]]:
    """`(batch id, theme)` for every `claims-*.json` an `audit --batches` run wrote, in name order."""
    out: list[tuple[str, str]] = []
    for f in sorted(batches_dir.glob("claims-*.json")):
        try:
            theme = str(json.loads(f.read_text(encoding="utf-8")).get("theme", ""))
        except (OSError, ValueError):
            theme = ""
        out.append((f.stem[len("claims-"):], theme))
    return out


def fill_from_batches(values: dict[str, str], batches_dir: Path, out_dir: Path,
                      votes: dict[str, int], root: Path | None = None) -> list[tuple[str, Path, str]]:
    """One skeptic brief per batch file (`votes` per theme: `{"security": 3}` writes `-a`, `-b`,
    `-c` voters over one claims file). Returns `(batch id, path, state)` with state `written` or
    `skipped`: an existing brief is NEVER rewritten, because under pointer dispatch it may be an
    agent's running instructions — the loop every build hand-wrote passed `--force` on all 38.
    `BATCH` and `CLAIMS` are this verb's to fill; a slots file naming them is refused."""
    if "BATCH" in values or "CLAIMS" in values:
        raise ValueError("--from-batches fills «BATCH» and «CLAIMS» itself; leave them out of the "
                         "slots file")
    out: list[tuple[str, Path, str]] = []
    out_dir.mkdir(parents=True, exist_ok=True)
    for bid, theme in batch_ids(batches_dir):
        n = votes.get(theme, 1)
        voters = [bid] if n <= 1 else [f"{bid}-{chr(ord('a') + k)}" for k in range(n)]
        for voter in voters:
            target = out_dir / f"skeptic-{voter}.md"
            if target.exists():
                out.append((voter, target, "skipped"))
                continue
            text = fill("skeptic", {**values, "BATCH": voter, "CLAIMS": bid}, root)
            target.write_text(text, encoding="utf-8")
            out.append((voter, target, "written"))
    return out


def _read_values(source: str) -> dict[str, str]:
    raw = sys.stdin.read() if source == "-" else Path(source).read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError(f"--fill expects a JSON object of slot -> value, found "
                         f"{type(data).__name__}")
    return data


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or "-h" in args or "--help" in args:
        print(_USAGE)
        return 0 if args else 2
    name = args[0]
    if name not in CONTRACTS:
        print(f"ERROR: unknown contract '{name}' — one of {', '.join(CONTRACTS)}", file=sys.stderr)
        return 2

    want_slots = False
    force = False
    fill_from: str | None = None
    out_path: str | None = None
    brief_id: str | None = None
    from_batches: str | None = None
    out_dir: str | None = None
    votes: dict[str, int] = {}
    i = 1
    while i < len(args):
        a = args[i]
        if a == "--slots":
            want_slots = True
        elif a == "--force":
            force = True
        elif a in ("--fill", "--out", "--brief", "--from-batches", "--out-dir", "--votes"):
            i += 1
            if i >= len(args):
                print(f"ERROR: {a} needs a value", file=sys.stderr)
                return 2
            if a == "--fill":
                fill_from = args[i]
            elif a == "--out":
                out_path = args[i]
            elif a == "--from-batches":
                from_batches = args[i]
            elif a == "--out-dir":
                out_dir = args[i]
            elif a == "--votes":
                theme, _, n = args[i].partition("=")
                if not theme or not n.isdigit():
                    print(f"ERROR: --votes expects <theme>=<count>, got '{args[i]}'", file=sys.stderr)
                    return 2
                votes[theme] = int(n)
            else:
                brief_id = args[i]
        else:
            print(f"ERROR: unknown option '{a}'", file=sys.stderr)
            return 2
        i += 1

    if want_slots and (fill_from or out_path or brief_id):
        print("ERROR: --slots prints the skeleton and writes nothing; it does not combine with "
              "--fill / --out / --brief", file=sys.stderr)
        return 2
    if out_path and not fill_from:
        print("ERROR: --out has nothing to write without --fill", file=sys.stderr)
        return 2
    if brief_id and not fill_from:
        print("ERROR: --brief names the file --fill writes, so it needs --fill", file=sys.stderr)
        return 2
    if from_batches is not None:
        if name != "skeptic" or not fill_from or not out_dir:
            print("ERROR: --from-batches is `contract skeptic --from-batches <dir> --fill <slots> "
                  "--out-dir <dir> [--votes <theme>=N]`", file=sys.stderr)
            return 2
        try:
            results = fill_from_batches(_read_values(fill_from), Path(from_batches), Path(out_dir), votes)
        except ValueError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 2
        for voter, target, state in results:
            print(f"{state:8} {voter:20} {target}")
        written = [(v, t) for v, t, s in results if s == "written"]
        print(f"{len(written)} brief(s) written, {len(results) - len(written)} skipped (existing "
              f"briefs are never rewritten). Pointer prompts to SEND, one per agent:")
        for voter, target in written:
            print(); print(brief(voter, target.resolve()))
        return 0
    if fill_from and not out_path:
        # Never to stdout: the point of the pair is that the agent reads a FILE and the lead sends
        # a pointer to it. A filled contract on stdout is one pipe away from being pasted.
        print("ERROR: --fill needs --out <file>; a filled contract is read by the agent from a "
              "file, never pasted into its prompt", file=sys.stderr)
        return 2

    try:
        if want_slots:
            print(json.dumps({k: "" for k in slots(name)}, indent=2, ensure_ascii=False))
            return 0
        if fill_from is not None and out_path is not None:
            values = _read_values(fill_from)
            text = fill(name, values)
            target = Path(out_path)
            # REFUSE an existing file. Under pointer dispatch a filled contract IS an agent's whole
            # brief, and the agent reads it whenever it gets round to it — so overwriting one is
            # rewriting the instructions of something that may still be running. On the 2026-08-29
            # mcpolis build turn 125 hand-wrote `briefs/t1.md` for an agent launched at turn 127,
            # and turn 160's generator looped `--out …/briefs/{aid}.md` with `aid="t1"` and rewrote
            # it mid-flight. Exit 0, no warning. The lead saw only the downstream fragment-name
            # collision, 19 turns later.
            if target.exists() and not force:
                print(f"ERROR: {target} already exists. A filled contract is an agent's whole brief "
                      f"under pointer dispatch, so overwriting one rewrites the instructions of an "
                      f"agent that may still be running. Pick another path, or pass --force if you "
                      f"know nothing is reading it.", file=sys.stderr)
                return 2
            pointer = ""
            if brief_id is not None:
                # Composed BEFORE the write, so a brief that cannot be sent does not leave a
                # filled contract behind that nothing points at. The path is checked AS GIVEN and
                # never resolved first: resolving turns a relative path into a plausible absolute
                # one built from the lead's cwd, which is the exact wrong-directory mistake the
                # absolute-path rule exists to catch — silently, and in the agent's prompt.
                pointer = brief(brief_id, target)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
            if name == "harvest":
                # The budget this brief hands its agent, recorded where `finalize` sums them.
                repo_slot = values.get("REPO_ABS") or values.get("repo") or ""
                if repo_slot and values.get("agent-id") and values.get("EXPECTED_COMPONENTS"):
                    record_budget(Path(repo_slot), str(values["agent-id"]),
                                  str(values["EXPECTED_COMPONENTS"]))
            print(f"filled {name} contract ({len(slots(name))} slot(s)) -> {target}",
                  file=sys.stderr)
            if brief_id is not None:
                sys.stdout.write(pointer)
            return 0
        sys.stdout.write(render(name))
    except FileNotFoundError as exc:
        print(f"ERROR: {exc.filename} not found — set COYODEX_HOME to the coyodex clone",
              file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"ERROR: --fill {fill_from}: not readable JSON ({exc})", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"ERROR: {CONTRACTS[name]}: {exc}", file=sys.stderr)
        return 2
    return 0
