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

import subprocess
import sys
import tempfile

from coyodex import audit_model
from coyodex.model import load_model

AUDIT = [sys.executable, "-m", "coyodex.audit_model"]


def audit_md(json_text: str) -> list[audit_model.Finding]:
    """The L1 findings for a scenario map: load the model document, audit it."""
    return audit_model.audit_model(load_model(json_text))


def l2(json_text: str) -> list[audit_model.WorkItem]:
    """The L2 worklist for a scenario map, through the same model-loading path."""
    return audit_model.l2_worklist_model(load_model(json_text))


# --- builders (JSON model documents) -----------------------------------
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
      "actor": "Andy",
      "trigger_outcome": "opens -> sees"
    }},
    {{
      "id": "UC2",
      "name": "Create order",
      "actor": "Adam",
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
      "store": "orders",
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
    """UC1's declared Actor is Andy, but its flow opens with `flow_actor` — a mismatch when it isn't
    Andy (the two layers disagree about who drives the use case)."""
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
      "actor": "Andy",
      "trigger_outcome": "opens -> sees"
    }}
  ],
  "happy_path": [
    {{
      "id": "HP1",
      "title": "View the order",
      "uc": "UC1",
      "why": null
    }}
  ],
  "subsystems": [],
  "components": [
    {{
      "id": "C1",
      "name": "Viewer",
      "subsystem": null,
      "purpose": "x",
      "entry_point": "f",
      "depends_on": "",
      "source": null,
      "confidence": "",
      "extra": {{}}
    }}
  ],
  "deps": [],
  "run_commands": [],
  "entry_points": [],
  "subdomains": [],
  "entities": [],
  "non_entity_types": [],
  "flows": [
    {{
      "uc": "UC1",
      "title": "View order",
      "steps": [
        {{
          "n": 1,
          "src": "{flow_actor}",
          "dst": "C1",
          "phrase": "views the order",
          "note": ""
        }}
      ]
    }}
  ],
  "edges": [],
  "deployment": [],
  "observability": [],
  "security": [],
  "config": [],
  "tests_note": "",
  "tests": [],
  "extras": []
}}"""


def make_actor_variant_map(declared: str, opening: str, roles: bool = False) -> str:
    """UC1's declared Actor is `declared`; its flow opens with `opening`. `roles=True` adds a Roles
    list containing only 'Andy', so an opener that is not a defined Role (a background trigger) is
    skipped. Covers the markdown / compound / background-trigger false-positive cases."""
    roles_list = (
        """[
    {
      "name": "Andy",
      "kind": "human",
      "wants": "see it",
      "drives": "UC1"
    }
  ]""" if roles else "[]")
    return f"""{{
  "format": "coyodex-map",
  "title": "",
  "goal": "",
  "commit": null,
  "committed": null,
  "built": null,
  "roles": {roles_list},
  "glossary": [],
  "use_cases": [
    {{
      "id": "UC1",
      "name": "View order",
      "actor": "{declared}",
      "trigger_outcome": "opens -> sees"
    }}
  ],
  "happy_path": [
    {{
      "id": "HP1",
      "title": "View the order",
      "uc": "UC1",
      "why": null
    }}
  ],
  "subsystems": [],
  "components": [
    {{
      "id": "C1",
      "name": "Viewer",
      "subsystem": null,
      "purpose": "x",
      "entry_point": "f",
      "depends_on": "",
      "source": null,
      "confidence": "",
      "extra": {{}}
    }}
  ],
  "deps": [],
  "run_commands": [],
  "entry_points": [],
  "subdomains": [],
  "entities": [],
  "non_entity_types": [],
  "flows": [
    {{
      "uc": "UC1",
      "title": "View order",
      "steps": [
        {{
          "n": 1,
          "src": "{opening}",
          "dst": "C1",
          "phrase": "views the order",
          "note": ""
        }}
      ]
    }}
  ],
  "edges": [],
  "deployment": [],
  "observability": [],
  "security": [],
  "config": [],
  "tests_note": "",
  "tests": [],
  "extras": []
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
      "actor": "Andy",
      "trigger_outcome": "a -> b"
    },
    {
      "id": "UC2",
      "name": "B",
      "actor": "Andy",
      "trigger_outcome": "a -> b"
    },
    {
      "id": "UC3",
      "name": "C",
      "actor": "Andy",
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
      "store": "users",
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
      "actor": "Andy",
      "trigger_outcome": "a -> b"
    },
    {
      "id": "UC2",
      "name": "Create org",
      "actor": "Adam",
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
      "store": "orgs",
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
      "actor": "Andy",
      "trigger_outcome": "a -> b"
    },
    {
      "id": "UC2",
      "name": "B",
      "actor": "Andy",
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
      "actor": "Andy",
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
      "store": "config",
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
      "actor": "Andy",
      "trigger_outcome": "a -> b"
    },
    {
      "id": "UC2",
      "name": "B",
      "actor": "Andy",
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
      "actor": "Andy",
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
      "actor": "Andy",
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
      "actor": "Andy",
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
      "store": "orders",
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


def test_actor_markdown_is_not_a_false_positive() -> None:
    """Finding 4: `**Andy**` (bold) must match `Andy`."""
    assert "actor-attribution" not in _checks(make_actor_variant_map("**Andy**", "Andy"))


def test_compound_actor_matches_any_alternative() -> None:
    """Finding 4: a compound Actor cell 'Admin or Manager' matches an opener of either."""
    assert "actor-attribution" not in _checks(make_actor_variant_map("Admin or Manager", "Admin"))


def test_background_trigger_opener_is_skipped() -> None:
    """Finding 3: with a Roles table, an opener that is not a defined Role (a Scheduler / webhook)
    is a background trigger, not an actor mismatch — skipped."""
    assert "actor-attribution" not in _checks(make_actor_variant_map("Andy", "Scheduler", roles=True))


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
