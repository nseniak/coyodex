"""coyodex-eval — the method-quality regression harness.

The eval runs the whole coyodex method on pinned reference repos, extracts deterministic quality
signals from each produced map (this package's :mod:`profile`), and compares them against a blessed
baseline to catch a method/tooling change that made the maps WORSE. See the coyodex-tests workspace
(external) for the data side: pinned sources, baselines, run archives, thresholds, and rubric.

Stdlib-only, like the rest of the core CLI — scoring reuses the validator's and audit's exact parse
(``grammar``) so a map is never scored through a second, drifting grammar.
"""
from __future__ import annotations
