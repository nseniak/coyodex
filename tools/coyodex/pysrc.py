"""Parse THIRD-PARTY Python source without leaking ITS own warnings into coyodex output.

`ast.parse` / `compile` of a user file that contains a non-raw regex string (`"\\d"`) emits a
`SyntaxWarning: invalid escape sequence` at parse time. When no filename is passed the warning is
attributed to `<unknown>:<line>` — noise printed at the top of `coyodex validate` / `preindex` that
looks like a coyodex bug but is the scanned repo's own code. Pass the real filename (correct
attribution if it ever surfaces) and swallow the scanned file's SyntaxWarnings.
"""
from __future__ import annotations

import ast
import warnings


def parse_python(source: str, filename: str) -> ast.Module:
    """`ast.parse(source)` with the scanned file's own SyntaxWarnings suppressed and its real
    filename attached. Raises the same exceptions as `ast.parse` (SyntaxError / ValueError)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        return ast.parse(source, filename=filename)
