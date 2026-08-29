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
    fill words that reach nobody."""
    seen: dict[str, None] = {}
    for key in SLOT.findall(render(name, root)):
        seen.setdefault(key.strip(), None)
    return list(seen)


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
          "       coyodex contract <name> --fill <slots.json|-> --out <file> [--brief <agent-id>]\n\n"
          "Print exactly the text one fan-out agent should receive: the contract's agent half,\n"
          "with the writing rules appended for the phases whose agents author map prose\n"
          "(" + ", ".join(sorted(AUTHORING)) + ").\n\n"
          "  --slots   print a ready-to-fill JSON skeleton — every slot of THIS contract as a\n"
          "            key with an empty value, so no slot name is ever typed by hand.\n"
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
    fill_from: str | None = None
    out_path: str | None = None
    brief_id: str | None = None
    i = 1
    while i < len(args):
        a = args[i]
        if a == "--slots":
            want_slots = True
        elif a in ("--fill", "--out", "--brief"):
            i += 1
            if i >= len(args):
                print(f"ERROR: {a} needs a value", file=sys.stderr)
                return 2
            if a == "--fill":
                fill_from = args[i]
            elif a == "--out":
                out_path = args[i]
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
            text = fill(name, _read_values(fill_from))
            target = Path(out_path)
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
