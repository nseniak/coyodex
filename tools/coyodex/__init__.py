"""coyodex — a top-down, drillable map of a codebase.

Importing this package pulls in NOTHING third-party: the core gate (validate +
render) is stdlib-only. tree-sitter is imported lazily, only inside the pre-index
code path (see internal/docs/design-notes.md, "dependency firewall").
"""
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("coyodex")
except PackageNotFoundError:  # running from source without an (editable) install
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
