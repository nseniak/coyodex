#!/usr/bin/env python3
"""Tests for `coyodex audit` — the adversarial pass (L1 self-contradiction + L2 worklist).

The scenario maps are authored directly as JSON model documents — the format the audit
actually reads — so these tests exercise the LIVE pipeline (model audit), not the retired markdown
audit.

Stdlib-only — no pytest required. Run either way (needs an editable install: `make deps`):
    python3 tests/test_audit.py        # built-in runner (prints pass/fail)
    pytest tests/test_audit.py         # if pytest is installed
"""
from __future__ import annotations

import itertools
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from coyodex import audit_model
from coyodex.model import (
    BusinessRule,
    ExtraSection,
    Group,
    HappyStep,
    Role,
    RuleSite,
    Component,
    Dep,
    Edge,
    Entity,
    EntryPoint,
    Flow,
    FlowStep,
    MessagingRow,
    ProjectModel,
    SecurityRow,
    StateMachine,
    StateTransition,
    Store,
    SubFlow,
    UseCase,
    load_model,
)

AUDIT = [sys.executable, "-m", "coyodex.audit_model"]


def audit_md(json_text: str) -> list[audit_model.Finding]:
    """The L1 findings for a scenario map: load the model document, audit it."""
    return audit_model.audit_model(load_model(json_text))


def l2(json_text: str) -> list[audit_model.WorkItem]:
    """The L2 worklist for a scenario map, through the same model-loading path."""
    return audit_model.l2_worklist_model(load_model(json_text))


# --- builders (JSON model documents) -----------------------------------

def make_all_theme_model() -> ProjectModel:
    """A model exercising EVERY worklist tier, so the order assertion is not vacuous on a fixture that
    emits one theme (the earlier version's fixture emitted only `ownership`)."""
    m = ProjectModel(title="T", goal="G")
    m.use_cases = [UseCase(id="UC1", name="Do it")]
    m.components = [Component(id="C1", name="A", purpose="p", entry_point="src/a.py:1"),
                    Component(id="C2", name="B", purpose="p", entry_point="src/b.py:1")]
    m.deps = [Dep(id="D1", name="Postgres", kind="datastore", type="SQL")]
    m.entities = [Entity(id="E1", name="Order", source="src/o.py:1",
                         store=Store(dep="D1", container="orders", mode="row")),
                  Entity(id="E2", name="Audit", source="src/x.py:1")]
    m.security = [SecurityRow(surface="API auth", who="signed-in", source="src/auth.py:9",
                              risk="a hole")]
    m.edges = [
        Edge(src="C1", verb="enforces", dst="C2", why="gate", where="src/a.py:5"),   # security
        Edge(src="C1", verb="uses", dst="D1", why="query", where="src/a.py:7"),      # dep-usage
        Edge(src="C1", verb="persists", dst="E1", why="store", where="src/a.py:9"),  # ownership
        Edge(src="C1", verb="calls", dst="C2", why="helper", where="src/a.py:11"),   # backbone
    ]
    m.messaging = [MessagingRow(name="jobs", broker="D1", publishers=["C1"], consumers=["C2"],
                                source="src/q.py:1")]                               # messaging
    m.components[1].states = StateMachine(states=["new", "done"], source="src/b.py:20")  # lifecycle
    m.entry_points = [EntryPoint(kind="job", trigger="nightly sweep", component="C1",
                                 source="src/a.py:30", cadence="every 24h",
                                 cadence_source="src/a.py:31")]                     # cadence
    m.blocks = [Group(id="BLK1", name="Access", purpose="who may act")]
    m.rules = [BusinessRule(id="BR1", name="Owner-only cancellation", statement="Only an owner may cancel.", block="BLK1",
                            sites=[RuleSite(where="src/a.py:13",
                                            why="rejects a non-owner")]),          # rule
               # An ACCESS rule, so the order pin is not vacuous on the security tier. Without one,
               # every rule in this fixture was `access=False`, the tier under test emitted nothing
               # security-themed, and a change routing access sites to `security` in the WRONG place
               # (interleaving security · rule · security) still passed.
               BusinessRule(id="BR2", name="Sign-in required to read",
                            statement="Only a signed-in user may read a ticket.",
                            block="BLK1", access=True, risk="anyone could read any ticket",
                            sites=[RuleSite(where="src/auth/gate.py:22",
                                            why="rejects an anonymous caller")])]  # security
    return m

def make_precedence_map(bad: bool = True, create_verb: str = "persists") -> str:
    """Two use cases over one entity E1: UC1 READS the order, UC2 CREATES it (`create_verb`).
    `bad=True` orders the Happy Path read-then-create (the read-before-create shape); `bad=False`
    orders it create-then-read (clean). `create_verb` lets a test use a MUTATION verb (`writes`) to
    prove an update is NOT mistaken for a create. No `why:` lines, so the why-less check is a no-op."""
    gp = (
        """[
    {
      "id": "HP1",
      "title": "Andy views the order",
      "uc": "UC1",
      "why": null
    },
    {
      "id": "HP2",
      "title": "Adam creates the order",
      "uc": "UC2",
      "why": null
    }
  ]""" if bad else
        """[
    {
      "id": "HP1",
      "title": "Adam creates the order",
      "uc": "UC2",
      "why": null
    },
    {
      "id": "HP2",
      "title": "Andy views the order",
      "uc": "UC1",
      "why": null
    }
  ]"""
    )
    return f"""{{
  "format": "coyodex-map",
  "title": "",
  "goal": "",
  "commit": null,
  "committed": null,
  "built": null,
  "roles": [],
  "glossary": [],
  "use_cases": [
    {{
      "id": "UC1",
      "name": "View order",
      "actors": [],
      "trigger_outcome": "opens -> sees"
    }},
    {{
      "id": "UC2",
      "name": "Create order",
      "actors": [],
      "trigger_outcome": "submits -> stored"
    }}
  ],
  "happy_path": {gp},
  "subsystems": [],
  "components": [
    {{
      "id": "C1",
      "name": "Viewer",
      "subsystem": null,
      "purpose": "x",
      "entry_point": "f",
      "depends_on": "E1",
      "source": null,
      "confidence": "",
      "extra": {{}}
    }},
    {{
      "id": "C2",
      "name": "Creator",
      "subsystem": null,
      "purpose": "x",
      "entry_point": "f",
      "depends_on": "E1",
      "source": null,
      "confidence": "",
      "extra": {{}}
    }}
  ],
  "deps": [],
  "run_commands": [],
  "entry_points": [],
  "subdomains": [],
  "entities": [
    {{
      "id": "E1",
      "name": "Order",
      "store": {{"notes": "orders"}},
      "meaning": "a customer order",
      "subdomain": null,
      "source": "order.py:1",
      "fields": [],
      "relations": []
    }}
  ],
  "non_entity_types": [],
  "flows": [
    {{
      "uc": "UC1",
      "title": "View order",
      "steps": [
        {{
          "n": 1,
          "src": "Andy",
          "dst": "C1",
          "phrase": "views the order",
          "note": ""
        }}
      ]
    }},
    {{
      "uc": "UC2",
      "title": "Create order",
      "steps": [
        {{
          "n": 1,
          "src": "Adam",
          "dst": "C2",
          "phrase": "creates the order",
          "note": ""
        }}
      ]
    }}
  ],
  "edges": [
    {{
      "src": "C1",
      "verb": "reads",
      "dst": "E1",
      "why": "show it",
      "where": "f#L1"
    }},
    {{
      "src": "C2",
      "verb": "{create_verb}",
      "dst": "E1",
      "why": "store it",
      "where": "f#L2"
    }}
  ],
  "deployment": [],
  "observability": [],
  "security": [],
  "config": [],
  "tests_note": "",
  "tests": [],
  "extras": []
}}"""


def make_actor_mismatch_map(flow_actor: str = "Zoe") -> str:
    """UC1's declared actor is Andy (R1); its flow opens with `flow_actor`. A mismatch when flow_actor
    isn't Andy — the two layers disagree on who drives the use case (both sides are role ids now)."""
    roles = [("R1", "Andy")]
    open_id = "R1"
    if flow_actor != "Andy":
        roles.append(("R2", flow_actor))
        open_id = "R2"
    roles_json = ", ".join(
        f'{{"id": "{i}", "name": "{n}", "kind": "human", "wants": "", "drives": "UC1"}}'
        for i, n in roles)
    return f"""{{
  "format": "coyodex-map", "title": "", "goal": "",
  "commit": null, "committed": null, "built": null,
  "roles": [{roles_json}],
  "glossary": [],
  "use_cases": [{{"id": "UC1", "name": "View order", "actors": ["R1"], "trigger_outcome": "opens -> sees"}}],
  "happy_path": [{{"id": "HP1", "title": "View the order", "uc": "UC1", "why": null}}],
  "subsystems": [],
  "components": [{{"id": "C1", "name": "Viewer", "subsystem": null, "purpose": "x", "entry_point": "f",
                  "depends_on": "", "source": null, "confidence": "", "extra": {{}}}}],
  "deps": [], "run_commands": [], "entry_points": [], "subdomains": [], "entities": [],
  "non_entity_types": [],
  "flows": [{{"uc": "UC1", "title": "View order", "steps": [
    {{"n": 1, "src": "{open_id}", "dst": "C1", "phrase": "views the order", "note": ""}}]}}],
  "edges": [], "deployment": [], "observability": [], "security": [], "config": [],
  "tests_note": "", "tests": [], "extras": []
}}"""


def make_shared_read_map() -> str:
    """Three use cases whose flows all read E1 (via a component that reads it); E1 is never written on
    the path. Exercises per-entity dedup: exactly ONE read-never-created advisory, not three."""
    return """{
  "format": "coyodex-map",
  "title": "",
  "goal": "",
  "commit": null,
  "committed": null,
  "built": null,
  "roles": [],
  "glossary": [],
  "use_cases": [
    {
      "id": "UC1",
      "name": "A",
      "actors": [],
      "trigger_outcome": "a -> b"
    },
    {
      "id": "UC2",
      "name": "B",
      "actors": [],
      "trigger_outcome": "a -> b"
    },
    {
      "id": "UC3",
      "name": "C",
      "actors": [],
      "trigger_outcome": "a -> b"
    }
  ],
  "happy_path": [
    {
      "id": "HP1",
      "title": "A",
      "uc": "UC1",
      "why": null
    },
    {
      "id": "HP2",
      "title": "B",
      "uc": "UC2",
      "why": null
    },
    {
      "id": "HP3",
      "title": "C",
      "uc": "UC3",
      "why": null
    }
  ],
  "subsystems": [],
  "components": [
    {
      "id": "C1",
      "name": "A",
      "subsystem": null,
      "purpose": "x",
      "entry_point": "f",
      "depends_on": "E1",
      "source": null,
      "confidence": "",
      "extra": {}
    },
    {
      "id": "C2",
      "name": "B",
      "subsystem": null,
      "purpose": "x",
      "entry_point": "f",
      "depends_on": "E1",
      "source": null,
      "confidence": "",
      "extra": {}
    },
    {
      "id": "C3",
      "name": "C",
      "subsystem": null,
      "purpose": "x",
      "entry_point": "f",
      "depends_on": "E1",
      "source": null,
      "confidence": "",
      "extra": {}
    }
  ],
  "deps": [],
  "run_commands": [],
  "entry_points": [],
  "subdomains": [],
  "entities": [
    {
      "id": "E1",
      "name": "User",
      "store": {"notes": "users"},
      "meaning": "a user",
      "subdomain": null,
      "source": "u.py:1",
      "fields": [],
      "relations": []
    }
  ],
  "non_entity_types": [],
  "flows": [
    {
      "uc": "UC1",
      "title": "A",
      "steps": [
        {
          "n": 1,
          "src": "Andy",
          "dst": "C1",
          "phrase": "reads the user",
          "note": ""
        }
      ]
    },
    {
      "uc": "UC2",
      "title": "B",
      "steps": [
        {
          "n": 1,
          "src": "Andy",
          "dst": "C2",
          "phrase": "reads the user",
          "note": ""
        }
      ]
    },
    {
      "uc": "UC3",
      "title": "C",
      "steps": [
        {
          "n": 1,
          "src": "Andy",
          "dst": "C3",
          "phrase": "reads the user",
          "note": ""
        }
      ]
    }
  ],
  "edges": [
    {
      "src": "C1",
      "verb": "reads",
      "dst": "E1",
      "why": "x",
      "where": "f#L1"
    },
    {
      "src": "C2",
      "verb": "reads",
      "dst": "E1",
      "why": "x",
      "where": "f#L2"
    },
    {
      "src": "C3",
      "verb": "reads",
      "dst": "E1",
      "why": "x",
      "where": "f#L3"
    }
  ],
  "deployment": [],
  "observability": [],
  "security": [],
  "config": [],
  "tests_note": "",
  "tests": [],
  "extras": []
}"""


def make_cc_routed_read_map() -> str:
    """The mcpolis bug shape, but the precondition read is routed through a `C→C` dependency: UC1's
    flow names only C1; C1 reads C3 (C→C); C3 reads E1 (C→E, but C3 is NOT in the flow). E1 is created
    at HP2. Audit CANNOT see the read (only C→E edges of flow-named components count) — a documented
    false negative that pins the limitation."""
    return """{
  "format": "coyodex-map",
  "title": "",
  "goal": "",
  "commit": null,
  "committed": null,
  "built": null,
  "roles": [],
  "glossary": [],
  "use_cases": [
    {
      "id": "UC1",
      "name": "Sign in",
      "actors": [],
      "trigger_outcome": "a -> b"
    },
    {
      "id": "UC2",
      "name": "Create org",
      "actors": [],
      "trigger_outcome": "a -> b"
    }
  ],
  "happy_path": [
    {
      "id": "HP1",
      "title": "Sign in",
      "uc": "UC1",
      "why": null
    },
    {
      "id": "HP2",
      "title": "Create org",
      "uc": "UC2",
      "why": null
    }
  ],
  "subsystems": [],
  "components": [
    {
      "id": "C1",
      "name": "SignIn",
      "subsystem": null,
      "purpose": "x",
      "entry_point": "f",
      "depends_on": "C3",
      "source": null,
      "confidence": "",
      "extra": {}
    },
    {
      "id": "C2",
      "name": "OrgSvc",
      "subsystem": null,
      "purpose": "x",
      "entry_point": "f",
      "depends_on": "E1",
      "source": null,
      "confidence": "",
      "extra": {}
    },
    {
      "id": "C3",
      "name": "MemberStore",
      "subsystem": null,
      "purpose": "x",
      "entry_point": "f",
      "depends_on": "E1",
      "source": null,
      "confidence": "",
      "extra": {}
    }
  ],
  "deps": [],
  "run_commands": [],
  "entry_points": [],
  "subdomains": [],
  "entities": [
    {
      "id": "E1",
      "name": "Organization",
      "store": {"notes": "orgs"},
      "meaning": "tenant",
      "subdomain": null,
      "source": "o.py:1",
      "fields": [],
      "relations": []
    }
  ],
  "non_entity_types": [],
  "flows": [
    {
      "uc": "UC1",
      "title": "Sign in",
      "steps": [
        {
          "n": 1,
          "src": "Andy",
          "dst": "C1",
          "phrase": "signs in",
          "note": ""
        }
      ]
    },
    {
      "uc": "UC2",
      "title": "Create org",
      "steps": [
        {
          "n": 1,
          "src": "Adam",
          "dst": "C2",
          "phrase": "creates org",
          "note": ""
        }
      ]
    }
  ],
  "edges": [
    {
      "src": "C1",
      "verb": "reads",
      "dst": "C3",
      "why": "resolve membership",
      "where": "f#L1"
    },
    {
      "src": "C3",
      "verb": "reads",
      "dst": "E1",
      "why": "membership→org",
      "where": "f#L2"
    },
    {
      "src": "C2",
      "verb": "persists",
      "dst": "E1",
      "why": "create org",
      "where": "f#L3"
    }
  ],
  "deployment": [],
  "observability": [],
  "security": [],
  "config": [],
  "tests_note": "",
  "tests": [],
  "extras": []
}"""


def make_backward_whyref_map() -> str:
    """HP1's `why:` cites HP2, which comes after it (a backward reference)."""
    return """{
  "format": "coyodex-map",
  "title": "",
  "goal": "",
  "commit": null,
  "committed": null,
  "built": null,
  "roles": [],
  "glossary": [],
  "use_cases": [
    {
      "id": "UC1",
      "name": "A",
      "actors": [],
      "trigger_outcome": "a -> b"
    },
    {
      "id": "UC2",
      "name": "B",
      "actors": [],
      "trigger_outcome": "a -> b"
    }
  ],
  "happy_path": [
    {
      "id": "HP1",
      "title": "First",
      "uc": "UC1",
      "why": "needs the thing from HP2"
    },
    {
      "id": "HP2",
      "title": "Second",
      "uc": "UC2",
      "why": "follows HP1"
    }
  ],
  "subsystems": [],
  "components": [
    {
      "id": "C1",
      "name": "A",
      "subsystem": null,
      "purpose": "x",
      "entry_point": "f",
      "depends_on": "",
      "source": null,
      "confidence": "",
      "extra": {}
    }
  ],
  "deps": [],
  "run_commands": [],
  "entry_points": [],
  "subdomains": [],
  "entities": [],
  "non_entity_types": [],
  "flows": [
    {
      "uc": "UC1",
      "title": "A",
      "steps": [
        {
          "n": 1,
          "src": "Andy",
          "dst": "C1",
          "phrase": "does a",
          "note": ""
        }
      ]
    },
    {
      "uc": "UC2",
      "title": "B",
      "steps": [
        {
          "n": 1,
          "src": "Andy",
          "dst": "C1",
          "phrase": "does b",
          "note": ""
        }
      ]
    }
  ],
  "edges": [],
  "deployment": [],
  "observability": [],
  "security": [],
  "config": [],
  "tests_note": "",
  "tests": [],
  "extras": []
}"""


def make_read_never_created_map() -> str:
    """A single step reads E9, which no step ever creates (an external/config entity) — advisory."""
    return """{
  "format": "coyodex-map",
  "title": "",
  "goal": "",
  "commit": null,
  "committed": null,
  "built": null,
  "roles": [],
  "glossary": [],
  "use_cases": [
    {
      "id": "UC1",
      "name": "Load config",
      "actors": [],
      "trigger_outcome": "a -> b"
    }
  ],
  "happy_path": [
    {
      "id": "HP1",
      "title": "Load the config",
      "uc": "UC1",
      "why": null
    }
  ],
  "subsystems": [],
  "components": [
    {
      "id": "C1",
      "name": "Loader",
      "subsystem": null,
      "purpose": "x",
      "entry_point": "f",
      "depends_on": "E9",
      "source": null,
      "confidence": "",
      "extra": {}
    }
  ],
  "deps": [],
  "run_commands": [],
  "entry_points": [],
  "subdomains": [],
  "entities": [
    {
      "id": "E9",
      "name": "AppConfig",
      "store": {"notes": "config"},
      "meaning": "config",
      "subdomain": null,
      "source": "c.py:1",
      "fields": [],
      "relations": []
    }
  ],
  "non_entity_types": [],
  "flows": [
    {
      "uc": "UC1",
      "title": "Load config",
      "steps": [
        {
          "n": 1,
          "src": "Andy",
          "dst": "C1",
          "phrase": "loads config",
          "note": ""
        }
      ]
    }
  ],
  "edges": [
    {
      "src": "C1",
      "verb": "reads",
      "dst": "E9",
      "why": "config",
      "where": "f#L1"
    }
  ],
  "deployment": [],
  "observability": [],
  "security": [],
  "config": [],
  "tests_note": "",
  "tests": [],
  "extras": []
}"""


def make_whyless_map() -> str:
    """HP1 has a `why:`, HP2 does not — a non-initial step missing its precondition (warning)."""
    return """{
  "format": "coyodex-map",
  "title": "",
  "goal": "",
  "commit": null,
  "committed": null,
  "built": null,
  "roles": [],
  "glossary": [],
  "use_cases": [
    {
      "id": "UC1",
      "name": "A",
      "actors": [],
      "trigger_outcome": "a -> b"
    },
    {
      "id": "UC2",
      "name": "B",
      "actors": [],
      "trigger_outcome": "a -> b"
    }
  ],
  "happy_path": [
    {
      "id": "HP1",
      "title": "First",
      "uc": "UC1",
      "why": "the start"
    },
    {
      "id": "HP2",
      "title": "Second",
      "uc": "UC2",
      "why": null
    }
  ],
  "subsystems": [],
  "components": [
    {
      "id": "C1",
      "name": "A",
      "subsystem": null,
      "purpose": "x",
      "entry_point": "f",
      "depends_on": "",
      "source": null,
      "confidence": "",
      "extra": {}
    }
  ],
  "deps": [],
  "run_commands": [],
  "entry_points": [],
  "subdomains": [],
  "entities": [],
  "non_entity_types": [],
  "flows": [
    {
      "uc": "UC1",
      "title": "A",
      "steps": [
        {
          "n": 1,
          "src": "Andy",
          "dst": "C1",
          "phrase": "does a",
          "note": ""
        }
      ]
    },
    {
      "uc": "UC2",
      "title": "B",
      "steps": [
        {
          "n": 1,
          "src": "Andy",
          "dst": "C1",
          "phrase": "does b",
          "note": ""
        }
      ]
    }
  ],
  "edges": [],
  "deployment": [],
  "observability": [],
  "security": [],
  "config": [],
  "tests_note": "",
  "tests": [],
  "extras": []
}"""


def make_l2_map() -> str:
    """A Security & auth entry plus an `enforces` edge — the two L2-worklist sources."""
    return """{
  "format": "coyodex-map",
  "title": "",
  "goal": "",
  "commit": null,
  "committed": null,
  "built": null,
  "roles": [],
  "glossary": [],
  "use_cases": [
    {
      "id": "UC1",
      "name": "Call",
      "actors": [],
      "trigger_outcome": "a -> b"
    }
  ],
  "happy_path": [],
  "subsystems": [],
  "components": [
    {
      "id": "C1",
      "name": "Gate",
      "subsystem": null,
      "purpose": "x",
      "entry_point": "f",
      "depends_on": "C2",
      "source": null,
      "confidence": "",
      "extra": {}
    },
    {
      "id": "C2",
      "name": "Policy",
      "subsystem": null,
      "purpose": "x",
      "entry_point": "f",
      "depends_on": "",
      "source": null,
      "confidence": "",
      "extra": {}
    }
  ],
  "deps": [],
  "run_commands": [],
  "entry_points": [],
  "subdomains": [],
  "entities": [],
  "non_entity_types": [],
  "flows": [],
  "edges": [
    {
      "src": "C1",
      "verb": "enforces",
      "dst": "C2",
      "why": "policy",
      "where": "gate.py#L5"
    }
  ],
  "deployment": [],
  "observability": [],
  "security": [
    {
      "surface": "/api",
      "who": "admins",
      "source": "[require_admin](auth.py#L10)",
      "risk": "escalation"
    }
  ],
  "config": [],
  "tests_note": "",
  "tests": [],
  "extras": []
}"""


def make_l2_dep_map() -> str:
    """The whole broadened worklist on one map: an `enforces` edge (security, ranks first); a `C→D`
    `emits` into an EXPLICIT `datastore` and a `writes` into an UNTAGGED dep (both ground); a `uses`
    into an EXPLICIT `library` (skip — a false 'uses <lib>' is benign); a `C→E` `persists` (ownership);
    and a plain `C→C` `calls` (remaining). The `emits`-into-a-log-dep row is the audit→Elastic
    false-edge class."""
    return """{
  "format": "coyodex-map",
  "title": "",
  "goal": "",
  "commit": null,
  "committed": null,
  "built": null,
  "roles": [],
  "glossary": [],
  "use_cases": [
    {
      "id": "UC1",
      "name": "Call",
      "actors": [],
      "trigger_outcome": "a -> b"
    }
  ],
  "happy_path": [],
  "subsystems": [],
  "components": [],
  "deps": [
    {
      "id": "D1",
      "name": "Elastic Cloud",
      "kind": "datastore",
      "type": "search",
      "used_for": "",
      "where_configured": "",
      "confidence": "",
      "deployment_linked": false,
      "extra": {
        "Purpose": "log storage"
      }
    },
    {
      "id": "D2",
      "name": "logging",
      "kind": "library",
      "type": "stdlib",
      "used_for": "",
      "where_configured": "",
      "confidence": "",
      "deployment_linked": false,
      "extra": {
        "Purpose": "app logs"
      }
    },
    {
      "id": "D3",
      "name": "Mystery",
      "kind": null,
      "type": "?",
      "used_for": "",
      "where_configured": "",
      "confidence": "",
      "deployment_linked": false,
      "extra": {
        "Purpose": "unknown"
      }
    }
  ],
  "run_commands": [],
  "entry_points": [],
  "subdomains": [],
  "entities": [],
  "non_entity_types": [],
  "flows": [],
  "edges": [
    {
      "src": "C1",
      "verb": "enforces",
      "dst": "C2",
      "why": "policy",
      "where": "gate.py#L5"
    },
    {
      "src": "C1",
      "verb": "emits",
      "dst": "D1",
      "why": "ship logs",
      "where": "audit_repo.py#L8"
    },
    {
      "src": "C1",
      "verb": "uses",
      "dst": "D2",
      "why": "log lines",
      "where": "mod.py#L3"
    },
    {
      "src": "C1",
      "verb": "writes",
      "dst": "D3",
      "why": "dump",
      "where": "x.py#L1"
    },
    {
      "src": "C1",
      "verb": "persists",
      "dst": "E1",
      "why": "store",
      "where": "repo.py#L2"
    },
    {
      "src": "C1",
      "verb": "calls",
      "dst": "C3",
      "why": "rpc",
      "where": "client.py#L4"
    }
  ],
  "deployment": [],
  "observability": [],
  "security": [],
  "config": [],
  "tests_note": "",
  "tests": [],
  "extras": []
}"""


def make_duplicated_edge_map() -> str:
    """`make_l2_dep_map` with its C→D `emits` row DUPLICATED — the G4 dedupe shape (a repeated edge
    row must not become two skeptic tasks)."""
    return """{
  "format": "coyodex-map",
  "title": "",
  "goal": "",
  "commit": null,
  "committed": null,
  "built": null,
  "roles": [],
  "glossary": [],
  "use_cases": [
    {
      "id": "UC1",
      "name": "Call",
      "actors": [],
      "trigger_outcome": "a -> b"
    }
  ],
  "happy_path": [],
  "subsystems": [],
  "components": [],
  "deps": [
    {
      "id": "D1",
      "name": "Elastic Cloud",
      "kind": "datastore",
      "type": "search",
      "used_for": "",
      "where_configured": "",
      "confidence": "",
      "deployment_linked": false,
      "extra": {
        "Purpose": "log storage"
      }
    },
    {
      "id": "D2",
      "name": "logging",
      "kind": "library",
      "type": "stdlib",
      "used_for": "",
      "where_configured": "",
      "confidence": "",
      "deployment_linked": false,
      "extra": {
        "Purpose": "app logs"
      }
    },
    {
      "id": "D3",
      "name": "Mystery",
      "kind": null,
      "type": "?",
      "used_for": "",
      "where_configured": "",
      "confidence": "",
      "deployment_linked": false,
      "extra": {
        "Purpose": "unknown"
      }
    }
  ],
  "run_commands": [],
  "entry_points": [],
  "subdomains": [],
  "entities": [],
  "non_entity_types": [],
  "flows": [],
  "edges": [
    {
      "src": "C1",
      "verb": "enforces",
      "dst": "C2",
      "why": "policy",
      "where": "gate.py#L5"
    },
    {
      "src": "C1",
      "verb": "emits",
      "dst": "D1",
      "why": "ship logs",
      "where": "audit_repo.py#L8"
    },
    {
      "src": "C1",
      "verb": "uses",
      "dst": "D2",
      "why": "log lines",
      "where": "mod.py#L3"
    },
    {
      "src": "C1",
      "verb": "writes",
      "dst": "D3",
      "why": "dump",
      "where": "x.py#L1"
    },
    {
      "src": "C1",
      "verb": "persists",
      "dst": "E1",
      "why": "store",
      "where": "repo.py#L2"
    },
    {
      "src": "C1",
      "verb": "calls",
      "dst": "C3",
      "why": "rpc",
      "where": "client.py#L4"
    },
    {
      "src": "C1",
      "verb": "emits",
      "dst": "D1",
      "why": "ship logs",
      "where": "audit_repo.py#L8"
    }
  ],
  "deployment": [],
  "observability": [],
  "security": [],
  "config": [],
  "tests_note": "",
  "tests": [],
  "extras": []
}"""


def make_described_map() -> str:
    """Named components with file anchors, a named dep, and an entity card with SOURCE — so worklist
    claims can carry self-describing From/To detail (G1)."""
    return """{
  "format": "coyodex-map",
  "title": "",
  "goal": "",
  "commit": null,
  "committed": null,
  "built": null,
  "roles": [],
  "glossary": [],
  "use_cases": [],
  "happy_path": [],
  "subsystems": [],
  "components": [
    {
      "id": "C1",
      "name": "AuthGate",
      "subsystem": null,
      "purpose": "x",
      "entry_point": "src/auth/gate.py:10",
      "depends_on": "",
      "source": null,
      "confidence": "",
      "extra": {}
    },
    {
      "id": "C2",
      "name": "PolicyStore",
      "subsystem": null,
      "purpose": "x",
      "entry_point": "src/policy.py:5",
      "depends_on": "",
      "source": null,
      "confidence": "",
      "extra": {}
    }
  ],
  "deps": [
    {
      "id": "D1",
      "name": "Elastic",
      "kind": "datastore",
      "type": "search",
      "used_for": "",
      "where_configured": "",
      "confidence": "",
      "deployment_linked": false,
      "extra": {
        "Purpose": "logs"
      }
    }
  ],
  "run_commands": [],
  "entry_points": [],
  "subdomains": [],
  "entities": [
    {
      "id": "E1",
      "name": "Order",
      "store": {"notes": "orders"},
      "meaning": "m",
      "subdomain": null,
      "source": "src/order.py:1",
      "fields": [
        {
          "name": "id",
          "type": "int",
          "markers": []
        }
      ],
      "relations": []
    }
  ],
  "non_entity_types": [],
  "flows": [],
  "edges": [
    {
      "src": "C1",
      "verb": "enforces",
      "dst": "C2",
      "why": "policy",
      "where": "gate.py#L5"
    },
    {
      "src": "C1",
      "verb": "emits",
      "dst": "D1",
      "why": "logs",
      "where": "gate.py#L8"
    },
    {
      "src": "C2",
      "verb": "persists",
      "dst": "E1",
      "why": "store",
      "where": "policy.py#L9"
    }
  ],
  "deployment": [],
  "observability": [],
  "security": [],
  "config": [],
  "tests_note": "",
  "tests": [],
  "extras": []
}"""


def run_audit(json_text: str) -> tuple[int, str]:
    """Drive the audit CLI on the scenario map, written to a JSON model file."""
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        f.write(json_text)
        path = f.name
    r = subprocess.run([*AUDIT, path], capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def _checks(json_text: str) -> dict[str, str]:
    """{check_name: severity} for the L1 findings on a map (direct engine call, no subprocess)."""
    return {f.check: f.severity for f in audit_md(json_text)}


# --- L1: read-before-create (advisory — lossy attribution, must not block) -------
def test_read_before_create_is_advisory() -> None:
    """It surfaces the read-then-create ordering, but as an ADVISORY — the component-granularity
    attribution has real false positives (the audit review), so it must never block a build."""
    checks = _checks(make_precedence_map(bad=True))
    assert checks.get("read-before-create") == "ADVISORY", checks


def test_read_before_create_does_not_block_the_cli() -> None:
    code, out = run_audit(make_precedence_map(bad=True))
    assert code == 0, out
    assert "read-before-create" in out and "AUDIT PASSED" in out, out


def test_correct_order_has_no_finding() -> None:
    """Regression guard: a create-then-read Happy Path is clean — no false positive."""
    assert audit_md(make_precedence_map(bad=False)) == []


def test_write_modeled_create_surfaces_read_before_create() -> None:
    """Finding F1 (2nd review): `writes` is create-OR-update ambiguous and the method uses it for
    creates (the live mcpolis map models 'create the admin membership' as a `writes` edge). A read
    before a later `writes` must still surface the ordering as read-before-create (advisory) — the
    signal must NOT be lost as read-never-created just because the verb was `writes` not `persists`."""
    checks = _checks(make_precedence_map(bad=True, create_verb="writes"))
    assert checks.get("read-before-create") == "ADVISORY", checks
    assert "read-never-created" not in checks, checks


def test_read_never_created_is_deduped_per_entity() -> None:
    """Finding F4 (2nd review): a shared entity read by many steps yields ONE advisory, not one per
    step (which scales to dozens on a real map with common User/Org/Config entities)."""
    dupes = [f for f in audit_md(make_shared_read_map())
             if f.check == "read-never-created"]
    assert len(dupes) == 1, dupes


def test_clean_map_passes_the_cli() -> None:
    code, out = run_audit(make_precedence_map(bad=False))
    assert code == 0, out
    assert "AUDIT PASSED" in out, out


def test_audit_json_output_is_machine_readable() -> None:
    # --json emits {findings, worklist} — the Phase-4 skeptic-batching payload (no regex-parsing
    # the human report). Same exit-code semantics as the text mode.
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        f.write(make_precedence_map(bad=False))
        path = f.name
    r = subprocess.run([*AUDIT, path, "--json"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    payload = json.loads(r.stdout)
    assert set(payload) == {"findings", "worklist", "themes", "theme_counts"}
    # `themes` is the ordered (most-dangerous-first) vocabulary and `theme_counts` the per-theme
    # sizes: what a Phase-4 batcher groups on, so it never has to string-match the prose.
    assert payload["themes"][0] == "security"
    assert set(payload["theme_counts"]) <= set(payload["themes"])
    assert sum(payload["theme_counts"].values()) == len(payload["worklist"])
    assert all({"claim", "anchor", "detail", "why_risky"} <= set(w) for w in payload["worklist"])
    assert all({"check", "severity", "location", "message"} <= set(fi) for fi in payload["findings"])


def test_cc_routed_read_is_a_known_gap() -> None:
    """Finding 5: a precondition read routed through a `C→C` dependency is invisible to the C→E-only
    attribution — a documented false negative. Pin it so the limitation is explicit."""
    assert "read-before-create" not in _checks(make_cc_routed_read_map())


# --- L1: actor-attribution (advisory, guarded against the confirmed false positives) --
def test_actor_attribution_mismatch_is_advisory() -> None:
    assert _checks(make_actor_mismatch_map("Zoe")).get("actor-attribution") == "ADVISORY"


def test_actor_attribution_matches_when_actors_agree() -> None:
    """No finding when the flow opens with the use case's declared actor."""
    assert "actor-attribution" not in _checks(make_actor_mismatch_map("Andy"))


def test_backward_why_ref_is_still_blocking() -> None:
    """The why-ref checks have no false positives, so they stay blocking contradictions."""
    checks = _checks(make_backward_whyref_map())
    assert checks.get("backward-why-ref") == "CONTRADICTION", checks
    code, out = run_audit(make_backward_whyref_map())
    assert code == 1 and "AUDIT FAILED" in out, out


def test_read_never_created_is_advisory_not_blocking() -> None:
    checks = _checks(make_read_never_created_map())
    assert checks.get("read-never-created") == "ADVISORY", checks
    code, _ = run_audit(make_read_never_created_map())
    assert code == 0, "an advisory alone must not block"


def make_dependency_phrasing_model(step_phrase: str, edge_why: str) -> audit_model.ProjectModel:
    from coyodex.model import Edge, Flow, FlowStep, ProjectModel
    return ProjectModel(
        flows=[Flow(uc="UC1", title="t", steps=[FlowStep(n=1, src="C1", dst="C2", phrase=step_phrase)])],
        edges=[Edge(src="C1", verb="uses", dst="C2", why=edge_why)])


def test_dependency_phrasing_flags_step_and_edge() -> None:
    # "A needs B to …" reads as static wiring, not a runtime action — advisory on step text and edge Why.
    m = make_dependency_phrasing_model("the page needs the client to POST", "requires the store to save")
    findings = audit_model.check_dependency_phrasing(m)
    assert {f.location for f in findings} == {"UC1 flow step 1", "edge C1 → C2"}
    assert all(f.severity == "ADVISORY" for f in findings)


def test_dependency_phrasing_allows_actions() -> None:
    # A proper action phrasing raises nothing (and "used to" is intentionally not flagged).
    m = make_dependency_phrasing_model("POSTs the new upstream through the client", "used to save the order")
    assert audit_model.check_dependency_phrasing(m) == []


def test_hp_whyref_ignores_word_with_embedded_hp() -> None:
    # An HP<n> EMBEDDED in a longer word ("PHP7", "BHP2") must NOT read as a Happy-Path cross-reference.
    # The missing word boundary used to make the audit BLOCK (dangling/backward why-ref) on prose like this.
    # (A standalone "HP15" is still ref-shaped and correctly matches — that residual needs typed refs.)
    from coyodex.model import HappyStep, ProjectModel
    m = ProjectModel(happy_path=[
        HappyStep(id="HP1", title="a", uc="UC1"),
        HappyStep(id="HP2", title="b", uc="UC2", why="runs on PHP7 runtime (not BHP2)"),
    ])
    assert audit_model.happy_path_steps(m)[1].why_refs == []


def test_hp_whyref_reads_whole_token() -> None:
    from coyodex.model import HappyStep, ProjectModel
    m = ProjectModel(happy_path=[
        HappyStep(id="HP1", title="a", uc="UC1"),
        HappyStep(id="HP2", title="b", uc="UC2", why="needs the org from HP1"),
    ])
    assert audit_model.happy_path_steps(m)[1].why_refs == [1]


def test_slash_role_name_yields_no_actor_mismatch() -> None:
    # A role NAME containing "/" ("Host LLM / MCP client") is now referenced by its id, so the old
    # string-splitting can't misfire: the use case's actor id and the flow's opening actor id are the
    # same role, so no advisory. (Role ids make the "/"-split bug structurally impossible.)
    from coyodex.model import Flow, FlowStep, ProjectModel, Role, UseCase
    m = ProjectModel(
        roles=[Role(id="R1", name="Host LLM / MCP client", kind="service")],
        use_cases=[UseCase(id="UC1", name="x", actors=["R1"])],
        flows=[Flow(uc="UC1", title="t", steps=[FlowStep(n=1, src="R1", dst="C1", phrase="acts")])],
    )
    assert audit_model.check_actor_attribution(m) == []


def test_whyless_nonfirst_step_warns() -> None:
    checks = _checks(make_whyless_map())
    assert checks.get("why-less-step") == "WARNING", checks


# --- L2 worklist ----------------------------------------------------------------
def test_l2_worklist_lists_security_surfaces_and_enforces_edges() -> None:
    items = l2(make_l2_map())
    claims = " ".join(w.claim for w in items)
    assert "Auth surface" in claims, claims
    assert "enforces" in claims, claims
    anchors = [w.anchor for w in items]
    assert "auth.py#L10" in anchors and "gate.py#L5" in anchors, anchors


def test_l2_worklist_grounds_external_dep_edges() -> None:
    """A `C→D` edge into an external dep is grounded regardless of verb — the system-boundary
    data-flow claim (`emits` into a `datastore`), carrying its call site."""
    items = l2(make_l2_dep_map())
    claims = [w.claim for w in items]
    assert "C1 emits D1" in claims, claims
    assert "audit_repo.py#L8" in [w.anchor for w in items], items


def test_l2_worklist_skips_explicit_library_deps() -> None:
    """A `C→D` edge into a dep EXPLICITLY tagged `library` is skipped — a false 'uses <lib>' is benign
    and that bucket is the high-count one the Context view folds away."""
    claims = " ".join(w.claim for w in l2(make_l2_dep_map()))
    assert "D2" not in claims, claims


def test_l2_worklist_grounds_untagged_dep_by_default() -> None:
    """Fail-safe: ONLY an explicit fold-tag skips a dep. D3 has no `Kind` cell (inference would call it
    'library'), yet its incoming edge is still grounded — an unrecognised external system must not slip
    through, which is exactly how the audit→Elastic edge survived."""
    claims = [w.claim for w in l2(make_l2_dep_map())]
    assert "C1 writes D3" in claims, claims


def test_l2_worklist_ranks_security_before_dep_edges() -> None:
    """Security (`enforces`) claims outrank external-dep data-flow claims in the worklist order."""
    claims = [w.claim for w in l2(make_l2_dep_map())]
    assert claims.index("C1 enforces C2") < claims.index("C1 emits D1"), claims


def test_l2_worklist_grounds_entity_ownership_edges() -> None:
    """A `C→E` ownership edge is grounded — a wrong persists/writes/reads mis-wires the
    subsystem→subdomain bridge."""
    claims = [w.claim for w in l2(make_l2_dep_map())]
    assert "C1 persists E1" in claims, claims


def test_l2_worklist_grounds_remaining_component_edges() -> None:
    """The broadened worklist grounds the WHOLE backbone — a plain `C→C` `calls` edge is on it too."""
    claims = [w.claim for w in l2(make_l2_dep_map())]
    assert "C1 calls C3" in claims, claims


def test_l2_worklist_ranks_backbone_tiers() -> None:
    """Ranking holds across every tier: security < external-dep < entity-ownership < remaining."""
    claims = [w.claim for w in l2(make_l2_dep_map())]
    order = [claims.index(c) for c in
             ("C1 enforces C2", "C1 emits D1", "C1 persists E1", "C1 calls C3")]
    assert order == sorted(order), claims


def test_l2_worklist_dedupes_by_claim() -> None:
    """G4: a duplicated edge row yields exactly ONE worklist claim — the first occurrence, its anchor
    kept — so the skeptic fan-out count is deterministic (no downstream ad-hoc collapse)."""
    items = [w for w in l2(make_duplicated_edge_map())
             if w.claim == "C1 emits D1"]
    assert len(items) == 1, items
    assert items[0].anchor == "audit_repo.py#L8", items


def test_l2_worklist_claims_are_self_describing() -> None:
    """G1: each edge item's `detail` carries both endpoints' names + source files, so a fresh-context
    skeptic given only the item can locate the code with NO map file. The short claim (`C1 enforces
    C2`) stays the stable key."""
    items = {w.claim: w for w in l2(make_described_map())}
    d = items["C1 enforces C2"].detail
    assert d is not None, items
    assert "C1 = AuthGate" in d and "src/auth/gate.py:10" in d, d  # #L10 normalized to :10
    assert "C2 = PolicyStore" in d and "src/policy.py:5" in d, d  # #L5 normalized to :5
    e = items["C2 persists E1"].detail
    assert e is not None and "E1 = Order" in e and "src/order.py:1" in e, e  # #L1 normalized to :1
    dep = items["C1 emits D1"].detail
    assert dep is not None and "D1 = Elastic" in dep, dep


def test_l2_worklist_detail_reaches_the_cli_output() -> None:
    """The self-describing detail is printed (a `who:` line), so an agent driving the CLI — not the
    Python API — can hand a skeptic a claim it can resolve without the map."""
    code, out = run_audit(make_described_map())
    assert code == 0, out
    assert "who: From: C1 = AuthGate (src/auth/gate.py:10)" in out, out  # #L10 normalized to :10


def test_l2_worklist_risk_prose_collapsed_by_default() -> None:
    # A3: the near-identical per-claim `risk:` rationale is hidden by default (behind --verbose); the
    # anchor + `who:` endpoint detail a skeptic actually needs is always kept (see the detail test above).
    worklist = audit_model.l2_worklist_model(audit_model.load_model(make_l2_map()))
    assert worklist
    assert "risk:" not in audit_model._format([], worklist, verbose=False)
    assert "risk:" in audit_model._format([], worklist, verbose=True)


def test_touch_sets_see_subflow_content() -> None:
    # C1 (the writer) appears ONLY inside SF1's steps; the referencing flow's use case must still
    # be attributed the write — sub-flow content is never audit-invisible.
    m = ProjectModel(title="t")
    m.use_cases = [UseCase(id="UC1", name="Do")]
    m.components = [Component(id="C1", name="Writer"), Component(id="C2", name="Front")]
    m.entities = [Entity(id="E1", name="Thing")]
    m.edges = [Edge(src="C1", verb="persists", dst="E1", where="a.py:1")]
    m.subflows = [SubFlow(id="SF1", name="Persist",
                          steps=[FlowStep(n=1, src="C1", dst="E1", phrase="writes", where="a.py:1")])]
    m.flows = [Flow(uc="UC1", title="Do",
                    steps=[FlowStep(n=1, src="C2", dst="E1", subflow="SF1")])]
    writes, _reads = audit_model._touch_sets(m)
    assert "E1" in writes["UC1"]


# --- L2 structured-store tier (WS-A1) -------------------------------------------
def test_l2_worklist_carries_structured_store_claims() -> None:
    # "En is stored in Dn container 'x'" is a skeptic-refutable claim; anchored at the entity's
    # own source. A store with no dep (notes-only / transient) emits no item.
    m = ProjectModel(title="T", goal="g")
    m.deps = [Dep(id="D1", name="MongoDB", kind="datastore", type="document db")]
    m.entities = [
        Entity(id="E1", name="Guild", source="src/g.py:9",
               store=Store(dep="D1", container="guilds", mode="collection")),
        Entity(id="E2", name="Event", store=Store(notes="transient")),
    ]
    items = [it for it in audit_model.l2_worklist_model(m) if "is stored in" in it.claim]
    assert len(items) == 1
    assert "E1" in items[0].claim and "D1 container 'guilds'" in items[0].claim
    assert items[0].anchor == "src/g.py:9"


# --- L2 messaging tier (WS-A5) --------------------------------------------------
def test_l2_worklist_carries_messaging_claims() -> None:
    m = ProjectModel(title="T", goal="g")
    m.components = [Component(id="C1", name="Worker", purpose="works"),
                    Component(id="C2", name="Consumer", purpose="consumes")]
    m.deps = [Dep(id="D1", name="Redis", kind="messaging", type="queue broker")]
    m.messaging = [MessagingRow(name="JOB_QUEUE", kind="job-queue", broker="D1",
                                publishers=["C1"], consumers=["C2"],
                                source="src/queues.py:3")]
    items = [it for it in audit_model.l2_worklist_model(m) if "Channel" in it.claim]
    assert len(items) == 1
    assert "'JOB_QUEUE' on D1" in items[0].claim and "C1" in items[0].claim
    assert items[0].anchor == "src/queues.py:3"


# --- L2 state-machine tier (WS-A3) ----------------------------------------------
def test_l2_worklist_carries_state_machine_claims() -> None:
    m = ProjectModel(title="T", goal="g")
    m.components = [Component(id="C1", name="Manager", purpose="manages",
                              states=StateMachine(states=["idle", "live"],
                                                  transitions=[StateTransition(src="idle",
                                                                               dst="live")],
                                                  source="src/mgr.py:7"))]
    items = [it for it in audit_model.l2_worklist_model(m) if "states" in it.claim]
    assert len(items) == 1
    assert "C1" in items[0].claim and "idle" in items[0].claim
    assert items[0].anchor == "src/mgr.py:7"


# --- L2 cadence tier (WS-A2) ----------------------------------------------------
def test_l2_worklist_carries_anchored_cadence_claims() -> None:
    # a recorded schedule is a drift-prone claim about WHEN code runs — each cadence joins the
    # skeptic worklist, anchored at the DECLARING line (cadence_source), else the EP's own source.
    m = ProjectModel(title="T", goal="g")
    m.entry_points = [
        EntryPoint(kind="poller", trigger="poll twitch", source="src/p.py:1",
                   cadence="every 30s", cadence_source="src/beat.py:12"),
        EntryPoint(kind="http-route", trigger="GET /x", source="src/r.py:1"),  # no cadence → no item
    ]
    items = audit_model.l2_worklist_model(m)
    cadence_items = [it for it in items if "cadence" in it.claim]
    assert len(cadence_items) == 1
    assert "every 30s" in cadence_items[0].claim
    assert cadence_items[0].anchor == "src/beat.py:12"


# --- built-in runner ------------------------------------------------------------
def _run() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_run())


# --------------------------------------------------------------------------------------
# `why:` may cite a USE CASE, not only a walk position (B4)
# --------------------------------------------------------------------------------------

def make_walk(*rows: tuple[str, str, str | None]) -> ProjectModel:
    """rows = (hp_id, uc_id, why) in walk order, with the matching use cases declared."""
    from coyodex.model import HappyStep, ProjectModel, UseCase
    ucs = sorted({uc for _, uc, _ in rows})
    return ProjectModel(
        use_cases=[UseCase(id=u, name=u, trigger_outcome="t") for u in ucs],
        happy_path=[HappyStep(id=hp, uc=uc, title=f"step {hp}", why=why)
                    for hp, uc, why in rows],
    )


def test_uc_why_ref_pointing_backward_is_accepted():
    m = make_walk(("HP1", "UC1", None), ("HP2", "UC2", "needs the org from UC1"))
    assert [f for f in audit_model.check_why_refs(m) if f.severity == audit_model.CONTRADICTION] == []


def test_uc_why_ref_pointing_forward_is_advisory_not_blocking():
    # ADVISORY on purpose: a `UCn` in prose is not necessarily a prerequisite citation ("the same
    # guard UC3 uses"), so blocking here would fail a build on a sentence. `HPn` stays blocking —
    # a position citation can only ever mean one thing.
    m = make_walk(("HP1", "UC1", "needs UC2"), ("HP2", "UC2", None))
    found = audit_model.check_why_refs(m)
    assert [(f.check, f.severity) for f in found] == [("forward-uc-why-ref", audit_model.ADVISORY)]


def test_uc_why_ref_to_an_unknown_use_case_dangles():
    m = make_walk(("HP1", "UC1", None), ("HP2", "UC2", "needs UC99"))
    assert [f.check for f in audit_model.check_why_refs(m)] == ["dangling-why-ref"]


def test_uc_why_ref_to_an_offspine_use_case_is_advisory_not_blocking():
    from coyodex.model import UseCase
    m = make_walk(("HP1", "UC1", None), ("HP2", "UC2", "needs UC3"))
    m.use_cases.append(UseCase(id="UC3", name="off-spine", trigger_outcome="t"))
    found = audit_model.check_why_refs(m)
    assert [(f.check, f.severity) for f in found] == [("offspine-why-ref", audit_model.ADVISORY)]


def test_positional_why_ref_silently_retargets_when_the_walk_is_renumbered():
    """`HPn` names a POSITION, so a walk edit can point an unchanged `why:` at a different step.

    A live build inserted a missing first act late in the run; the renumbering that followed left an
    `HP16` citing `HP19` — a forward reference, and a BLOCKING audit failure found after the final
    assemble. The narrower, always-silent half is shown here: after renumbering, the SAME `why:`
    text resolves to a different step than its author meant, and no check can notice because the
    reference is still well-formed and still backward. A `UCn` citation names the prerequisite
    itself, so neither failure mode can reach it.
    """
    from coyodex.model import HappyStep, ProjectModel, UseCase

    def walk(rows: list[tuple[str, str, str | None]]) -> ProjectModel:
        return ProjectModel(
            use_cases=[UseCase(id=u, name=u, trigger_outcome="t")
                       for u in ("UC1", "UC2", "UC9")],
            happy_path=[HappyStep(id=hp, uc=uc, title=uc, why=why) for hp, uc, why in rows])

    before = walk([("HP1", "UC1", None), ("HP2", "UC2", "needs the org from HP1")])
    after = walk([("HP1", "UC9", None),                       # inserted first act
                  ("HP2", "UC1", None),                       # was HP1
                  ("HP3", "UC2", "needs the org from HP1")])  # citation untouched
    # well-formed and backward in BOTH walks — the audit cannot see the breakage...
    assert audit_model.check_why_refs(before) == []
    assert audit_model.check_why_refs(after) == []
    # ...yet the cited step is no longer the one that creates the org.
    uc_cited = lambda m: {st.hp_id: st.uc for st in audit_model.happy_path_steps(m)}["HP1"]
    assert uc_cited(before) == "UC1" and uc_cited(after) == "UC9"

    # The same prerequisite cited as a use case resolves to the org step in both walks.
    by_uc = walk([("HP1", "UC9", None), ("HP2", "UC1", None),
                  ("HP3", "UC2", "needs the org from UC1")])
    assert audit_model.check_why_refs(by_uc) == []
    assert audit_model.happy_path_steps(by_uc)[2].why_uc_refs == ["UC1"]


def test_an_access_rule_site_is_a_security_claim_not_a_rule_claim():
    """The T7 fold made an auth surface a business rule with `access: true`, but the worklist kept
    theming every rule site `rule`. With `m.security` empty by design, that left the theme the audit
    orders FIRST permanently empty, so Phase 4's "most dangerous first" was ordering, not risk — on
    one real build the three-skeptic majority went to a batch holding 6 access claims of 40 while two
    40/40 batches got one skeptic each."""
    m = make_all_theme_model()
    items = audit_model.l2_worklist_model(m)
    by_theme = {}
    for it in items:
        by_theme.setdefault(it.theme, []).append(it)
    access_claims = [i.claim for i in by_theme.get("security", [])]
    assert any("signed-in user" in c for c in access_claims), \
        "an `access: true` rule site must be a SECURITY claim"
    assert all("signed-in user" not in i.claim for i in by_theme.get("rule", [])), \
        "an access rule site must not ALSO be emitted as a plain rule claim"
    assert any("owner may cancel" in i.claim for i in by_theme.get("rule", [])), \
        "a non-access rule site must still be a `rule` claim"


def test_access_and_rule_tiers_do_not_interleave():
    """Access sites are `security`-themed, so they must be extended BEFORE the `rule` tier. Appending
    them where they are built interleaves security · rule · security and silently breaks the
    declared-order == emission-order contract — on the two real maps that mistake produces 24 and 22
    alternating groups instead of one of each."""
    import itertools
    m = make_all_theme_model()
    themes = [i.theme for i in audit_model.l2_worklist_model(m)]
    groups = [t for t, _ in itertools.groupby(themes)]
    assert len(groups) == len(set(themes)), f"themes are not contiguous: {groups}"


def test_themes_are_closed_and_match_the_worklist_order():
    """The pin an earlier comment CLAIMED existed and did not.

    Two contracts, both previously false: (a) `_THEMES` is closed — a claim built with an unlisted
    theme must fail here, and a bogus theme on 5 of the 8 sites left the whole suite green; (b) the
    declared order IS the emission order, and `backbone` (194 of 398 claims on a live map, the lowest
    risk) was emitted 4th of 8 while sitting 8th in the list, so a consumer batching in worklist order
    spent its first batches on generic edges. Read from this module's own source, so a new claim kind
    joins the test automatically."""
    src = Path(str(audit_model.__file__)).read_text(encoding="utf-8")
    emitted = set(re.findall(r'theme="([a-z-]+)"', src))
    declared = set(audit_model._THEMES)
    assert emitted <= declared, f"theme(s) emitted but not declared in _THEMES: {emitted - declared}"
    assert len(audit_model._THEMES) == len(set(audit_model._THEMES))
    # (b) declared order == emission order, on a model exercising every tier
    m = make_all_theme_model()
    seen = [k for k, _ in itertools.groupby(w.theme for w in audit_model.l2_worklist_model(m))]
    assert seen == [t for t in audit_model._THEMES if t in seen], (
        f"worklist order {seen} contradicts _THEMES {audit_model._THEMES}")
    assert "backbone" in seen and seen[-1] == "backbone", "the largest, lowest-risk tier must be last"


def make_advisory_map() -> ProjectModel:
    """A map with one `read-never-created` advisory: HP1 reads E1, nothing writes it."""
    m = ProjectModel(title="T", goal="G")
    m.roles = [Role(id="R1", name="A", kind="human", wants="x", drives="UC1")]
    m.use_cases = [UseCase(id="UC1", name="Read it", actors=["R1"])]
    m.happy_path = [HappyStep(id="HP1", title="Read", uc="UC1")]
    m.components = [Component(id="C1", name="A", purpose="p", entry_point="a.py:1")]
    m.entities = [Entity(id="E1", name="Thing", source="a.py:1")]
    m.edges = [Edge(src="C1", verb="reads", dst="E1", why="w", where="a.py:2")]
    m.flows = [Flow(uc="UC1", title="Read it",
                    steps=[FlowStep(n=1, src="R1", dst="C1", phrase="asks"),
                           FlowStep(n=2, src="C1", dst="E1", phrase="reads the thing")])]
    return m


def test_an_audit_advisory_can_be_recorded_and_the_suppression_is_reported():
    """Until this existed, `audit` read NO extras heading at all — every advisory family was
    permanently unanswerable, so a finding an operator had judged acceptable re-fired forever and got
    waved through. A live map carried two `read-never-created` advisories through its whole build.

    The suppression is never silent: that is the `runs-in` lesson, where one recorded literal removed
    findings with no trace and a justification written about one thing swallowed unrelated ones."""
    m = make_advisory_map()
    before = audit_model.audit_model(m)
    assert any(f.check == "read-never-created" for f in before), before
    m.extras = [ExtraSection(heading=audit_model.AUDIT_EXCEPTIONS_HEADING,
                             body="read-never-created HP1: external config data, written off-path.")]
    after = audit_model.audit_model(m)
    assert not any(f.check == "read-never-created" for f in after)
    note = [f for f in after if f.check == "recorded-exceptions"]
    assert len(note) == 1 and "read-never-created HP1" in note[0].message


def test_one_audit_record_may_answer_several_ids_of_the_SAME_check():
    """Multi-key, with the check name still scoping every id on the line — the family escape the
    method forbids stays impossible, because the check is named once and applies to the whole list."""
    m = make_advisory_map()
    assert any(f.check == "read-never-created" for f in audit_model.audit_model(m))
    m.extras = [ExtraSection(heading=audit_model.AUDIT_EXCEPTIONS_HEADING,
                             body="read-never-created HP1, HP9: external config data, written off-path.")]
    assert not any(f.check == "read-never-created" for f in audit_model.audit_model(m))
    assert ("read-never-created", "HP9") in audit_model.audit_exceptions(m)


def test_an_audit_record_that_lost_its_check_name_silences_nothing():
    """`HP1: <why>` parses perfectly as an id list and scopes itself to NO check — so it must not
    silence one. It is reported instead (`validate`'s malformed-record advisory)."""
    m = make_advisory_map()
    m.extras = [ExtraSection(heading=audit_model.AUDIT_EXCEPTIONS_HEADING,
                             body="HP1, HP9: external config data, written off-path.")]
    assert audit_model.audit_exceptions(m) == set()
    assert any(f.check == "read-never-created" for f in audit_model.audit_model(m))


def test_a_recorded_line_silences_one_pair_never_a_family():
    """The `runs-in` over-suppression bug, designed out: two findings of the SAME check on different
    ids, one recorded, and the other must survive."""
    m = make_advisory_map()
    # A SECOND component, not just a second entity: reads are attributed at component granularity, so
    # two flows through one component both land on the first HP step and the ids would not differ.
    m.use_cases.append(UseCase(id="UC2", name="Read again", actors=["R1"]))
    m.happy_path.append(HappyStep(id="HP2", title="Again", uc="UC2"))
    m.components.append(Component(id="C2", name="B", purpose="p", entry_point="b.py:1"))
    m.entities.append(Entity(id="E2", name="Other", source="b.py:1"))
    m.edges.append(Edge(src="C2", verb="reads", dst="E2", why="w", where="b.py:2"))
    m.flows.append(Flow(uc="UC2", title="Read again",
                        steps=[FlowStep(n=1, src="R1", dst="C2", phrase="asks"),
                               FlowStep(n=2, src="C2", dst="E2", phrase="reads the other")]))
    assert len([f for f in audit_model.audit_model(m) if f.check == "read-never-created"]) == 2
    m.extras = [ExtraSection(heading=audit_model.AUDIT_EXCEPTIONS_HEADING,
                             body="read-never-created HP1: deliberate.")]
    left = [f for f in audit_model.audit_model(m) if f.check == "read-never-created"]
    assert len(left) == 1 and left[0].location.startswith("HP2"), left


def test_a_recorded_line_that_matches_nothing_is_reported():
    """A line that silences nothing reads as a decision the operator never had to make — a stale id, a
    fixed advisory, or a misspelled check name."""
    m = make_advisory_map()
    m.extras = [ExtraSection(heading=audit_model.AUDIT_EXCEPTIONS_HEADING,
                             body="read-never-created HP99: stale.")]
    notes = [f for f in audit_model.audit_model(m) if f.check == "recorded-exceptions"]
    assert any("matched no finding" in f.message and "HP99" in f.message for f in notes), notes


def test_a_contradiction_can_never_be_recorded_away():
    """CONTRADICTIONS are self-inconsistencies in the map, not judgement calls. Only ADVISORY findings
    are suppressible; a blocking finding with an escape hatch would be no gate at all."""
    m = make_advisory_map()
    m.happy_path[0].why = "after HP9"          # a dangling `why:` ref — CONTRADICTION
    blocking = [f for f in audit_model.audit_model(m) if f.severity == audit_model.CONTRADICTION]
    assert blocking, "expected a contradiction to record against"
    eid = blocking[0].location.split()[0].strip("()")
    m.extras = [ExtraSection(heading=audit_model.AUDIT_EXCEPTIONS_HEADING,
                             body=f"{blocking[0].check} {eid}: try to wave this through.")]
    still = [f for f in audit_model.audit_model(m) if f.severity == audit_model.CONTRADICTION]
    assert len(still) == len(blocking), "a contradiction was suppressed"


def test_a_line_with_no_why_is_not_a_recorded_decision():
    """An id alone is a dismissal, not a decision — the record must carry the reasoning."""
    m = make_advisory_map()
    m.extras = [ExtraSection(heading=audit_model.AUDIT_EXCEPTIONS_HEADING,
                             body="read-never-created HP1")]
    assert any(f.check == "read-never-created" for f in audit_model.audit_model(m))


def test_theme_batches_carry_the_anchor_the_hand_script_dropped():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        _theme_batches_carry_the_anchor(td)


def _theme_batches_carry_the_anchor(tmp_path: str) -> None:
    """`--batches` exists because the hand-rolled batcher wrote `f.write(c['claim'])` and nothing
    else, so 360 of 408 dispatched claims reached the skeptics as a bare `C140 calls C78` — while
    the prompt promised them the claim would end with its `path:line` anchor in square brackets.
    The tool held an anchor for 400 of 404 items the whole time."""
    from coyodex.audit_model import BATCH_SCHEMA, l2_worklist_model, write_theme_batches

    own_map = Path(__file__).resolve().parents[1] / ".coyodex" / "project-map.json"
    m = load_model(own_map.read_text(encoding="utf-8"))
    worklist = l2_worklist_model(m)
    written = write_theme_batches(worklist, Path(tmp_path), cap=40)
    assert written, "coyodex's own map must produce at least one theme batch"
    total = anchored = 0
    for name, n in written:
        payload = json.loads((Path(tmp_path) / name).read_text(encoding="utf-8"))
        assert payload["schema"] == BATCH_SCHEMA, "the artifact is versioned from day one"
        assert len(payload["claims"]) == n <= 40
        for c in payload["claims"]:
            total += 1
            assert set(c) == {"claim", "anchor", "detail", "why_risky"}
            anchored += bool(c["anchor"])
    assert total == len(worklist), "every worklist claim lands in exactly one batch"
    assert anchored > total * 0.9, (
        f"only {anchored}/{total} dispatched claims carry an anchor — the defect this removes")


def test_a_renamed_use_case_that_left_its_flow_title_behind_is_flagged():
    """The other half of a late rename. A live map had two use cases repointed and renamed near the
    end of a build without re-tracing: `actor-attribution` fired on the actor half and was recorded,
    while the stale flow title went unnoticed by anything. Measured before writing: across three
    live maps name and title agree 39/40, 26/27 and everywhere else, and both exceptions were
    exactly this defect."""
    from coyodex.audit_model import check_flow_title
    m = ProjectModel(title="t", goal="g")
    m.use_cases = [UseCase(id="UC1", name="Rebuild the company knowledge graph", actors=["R1"])]
    m.flows = [Flow(uc="UC1", title="Build the knowledge graph from connected sources", steps=[])]
    assert [f for f in check_flow_title(m) if f.check == "flow-title"]
    m.flows[0].title = "Rebuild the company knowledge graph"
    assert not check_flow_title(m), "an agreeing title must not fire"


def test_a_flow_title_record_does_not_silence_a_different_check_on_the_same_use_case():
    """A record adjudicates one (check, id) PAIR, never a whole family. Reading every UC id under
    'Audit exceptions' — rather than the pairs — let an unrelated `actor-attribution` record
    silence this check on the same use case, which hid the very case it was written for."""
    from coyodex.audit_model import audit_exceptions
    m = ProjectModel(title="t", goal="g")
    m.extras = [ExtraSection(heading="Audit exceptions",
                             body="actor-attribution UC1: the scheduler opens it, deliberate.")]
    pairs = audit_exceptions(m)
    assert ("actor-attribution", "UC1") in pairs
    assert ("flow-title", "UC1") not in pairs


def make_prose_map() -> ProjectModel:
    """A map with exactly three reader-facing prose fields, one of them blank."""
    m = ProjectModel(title="Demo", goal="A demo.")
    m.components = [Component(id="C1", name="Checkout", purpose="Books an order."),
                    Component(id="C2", name="Ledger", purpose="")]
    m.rules = [BusinessRule(id="BR1", name="Owner-only", statement="Only the owner may cancel.",
                            risk="A stranger could cancel an order.")]
    return m


def test_prose_batches_carry_every_non_empty_field_and_the_rules() -> None:
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        written = audit_model.write_prose_batches(make_prose_map(), out, cap=10)
        assert written == [("prose-1.json", 3)]     # C2's empty purpose is dropped
        payload = json.loads((out / "prose-1.json").read_text())
        assert payload["schema"] == audit_model.PROSE_BATCH_SCHEMA
        assert [f["where"] for f in payload["fields"]] == ["C1 purpose", "BR1 statement", "BR1 risk"]
        assert "UNKNOWN WORD" in payload["instructions"]


def test_a_second_run_at_a_smaller_cap_leaves_no_stale_prose_batch() -> None:
    """The claim batches paid for this once: two runs at different caps left the smaller run's extra
    files behind and a glob dispatched 23 duplicates while the tool printed the honest total."""
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        audit_model.write_prose_batches(make_prose_map(), out, cap=1)
        assert len(list(out.glob("prose-*.json"))) == 3
        audit_model.write_prose_batches(make_prose_map(), out, cap=10)
        assert [p.name for p in sorted(out.glob("prose-*.json"))] == ["prose-1.json"]


def test_json_findings_carry_where_as_well_as_location(capsys):
    """The text report prints `where: …`; `--json` emitted only `location`.

    A build read the human output, reached for `--json`, wrote `f.get("where", "")`, matched
    nothing, printed an empty result, and spent the next turn re-doing the same extraction by
    grepping the text report. Both keys ship now: renaming `location` alone would break anything
    already reading it.
    """
    from coyodex import audit_model
    m = make_precedence_map(bad=True)
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "map.json"
        p.write_text(m, encoding="utf-8")
        audit_model.main([str(p), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["findings"], "the fixture must produce at least one finding"
    for f in payload["findings"]:
        assert f["where"] == f["location"], f
