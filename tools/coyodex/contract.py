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
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Contract name → template file. The name is what a lead types, so it is the phase, not the filename.
CONTRACTS: dict[str, str] = {
    "harvest": "harvest-contract.md",
    "trace": "trace-contract.md",
    "rules": "rules-contract.md",
    "skeptic": "skeptic-contract.md",
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


_USAGE = ("usage: coyodex contract <" + " | ".join(CONTRACTS) + ">\n\n"
          "Print exactly the text one fan-out agent should receive: the contract's agent half,\n"
          "with the writing rules appended for the phases whose agents author map prose\n"
          "(" + ", ".join(sorted(AUTHORING)) + ").\n\n"
          "Redirect it into the agent's scratch file, then fill the «angle-bracket» slots:\n"
          "  coyodex contract harvest > <scratch>/harvest-contract.md\n\n"
          "The lead never handles the template itself, so the lead's own instructions at the top\n"
          "of that file cannot reach an agent. COYODEX_HOME overrides where the templates are\n"
          "read from.\n")


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or "-h" in args or "--help" in args:
        print(_USAGE)
        return 0 if args else 2
    name = args[0]
    if name not in CONTRACTS:
        print(f"ERROR: unknown contract '{name}' — one of {', '.join(CONTRACTS)}", file=sys.stderr)
        return 2
    try:
        sys.stdout.write(render(name))
    except FileNotFoundError as exc:
        print(f"ERROR: {exc.filename} not found — set COYODEX_HOME to the coyodex clone",
              file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"ERROR: {CONTRACTS[name]}: {exc}", file=sys.stderr)
        return 2
    return 0
