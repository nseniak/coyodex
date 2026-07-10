#!/usr/bin/env python3
"""Tests for the grouping/rendering pipeline: the graph builder (build_graph), the view
derivation (views.model_to_graph), the Mermaid card generators + view bundle (gen_viewer), and the
served generic frontend (viewer.html / viewer.js).

Stdlib-only — no pytest required. Run either way (needs an editable install: `make deps`):
    python3 tests/test_grouping.py        # built-in runner (prints pass/fail)
    pytest tests/test_grouping.py         # if pytest is installed
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import cast

from coyodex import grammar
from coyodex.model import load_model
from coyodex.viewer import build_graph, gen_viewer
from coyodex.views import model_to_graph

VIEWER_DIR = Path(gen_viewer.__file__).resolve().parent  # the served shell + viewer.js/css live here


def bundle_of(json_text: str, report: Path | None = None) -> gen_viewer.ViewBundle:
    """The view bundle a served map exposes at /api/view — the data the generic frontend fetches. The
    render→HTML file is gone; the diagrams/flows/config now live here (build_view_bundle), so the tests
    that used to grep the baked HTML assert on this bundle (and on the static shell for page chrome)."""
    return gen_viewer.build_view_bundle(parse_map(json_text), report, VIEWER_DIR)


def make_grouped_map(layout: str = "proper") -> str:
    """A two-subsystem grouped map. layout='proper' has an ID + Component(name) column;
    layout='agent' drops them (id in col 0, Subsystem at index 1) — the regression case."""
    if layout == "agent":
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
  "subsystems": [
    {
      "id": "S1",
      "name": "Edge",
      "purpose": "x",
      "parent": null,
      "source": "a/",
      "confidence": "V"
    },
    {
      "id": "S2",
      "name": "Core",
      "purpose": "x",
      "parent": null,
      "source": "a/",
      "confidence": "V"
    }
  ],
  "components": [
    {
      "id": "C1",
      "name": "C1",
      "subsystem": "S1",
      "purpose": "x",
      "entry_point": "f",
      "depends_on": "C2",
      "source": null,
      "confidence": "",
      "extra": {}
    },
    {
      "id": "C2",
      "name": "C2",
      "subsystem": "S2",
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
      "verb": "uses",
      "dst": "C2",
      "why": "reach engine",
      "where": "f"
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
  "subsystems": [
    {
      "id": "S1",
      "name": "Edge",
      "purpose": "x",
      "parent": null,
      "source": "a/",
      "confidence": "V"
    },
    {
      "id": "S2",
      "name": "Core",
      "purpose": "x",
      "parent": null,
      "source": "a/",
      "confidence": "V"
    }
  ],
  "components": [
    {
      "id": "C1",
      "name": "Front door",
      "subsystem": "S1",
      "purpose": "x",
      "entry_point": "f",
      "depends_on": "C2",
      "source": null,
      "confidence": "",
      "extra": {}
    },
    {
      "id": "C2",
      "name": "Engine",
      "subsystem": "S2",
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
      "verb": "uses",
      "dst": "C2",
      "why": "reach engine",
      "where": "f"
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


def make_card_map() -> str:
    """A grouped map exercising the card generators: S1 has two components wired internally
    (C1->C3), both cross into S2's component C2, and C2 touches a dep D1. Lets the tests assert
    a subsystem card keeps internal wiring + deps, while an edge card keeps ONLY the cross edges."""
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
  "subsystems": [
    {
      "id": "S1",
      "name": "Edge",
      "purpose": "front",
      "parent": null,
      "source": "a/",
      "confidence": "V"
    },
    {
      "id": "S2",
      "name": "Core",
      "purpose": "brains",
      "parent": null,
      "source": "a/",
      "confidence": "V"
    }
  ],
  "components": [
    {
      "id": "C1",
      "name": "Front door",
      "subsystem": "S1",
      "purpose": "x",
      "entry_point": "f",
      "depends_on": "C2",
      "source": null,
      "confidence": "",
      "extra": {}
    },
    {
      "id": "C3",
      "name": "Router",
      "subsystem": "S1",
      "purpose": "x",
      "entry_point": "f",
      "depends_on": "C2",
      "source": null,
      "confidence": "",
      "extra": {}
    },
    {
      "id": "C2",
      "name": "Engine",
      "subsystem": "S2",
      "purpose": "x",
      "entry_point": "f",
      "depends_on": "D1",
      "source": null,
      "confidence": "",
      "extra": {}
    }
  ],
  "deps": [
    {
      "id": "D1",
      "name": "Cache",
      "kind": null,
      "type": "",
      "used_for": "",
      "where_configured": "",
      "confidence": "",
      "deployment_linked": false,
      "extra": {
        "Anchor": "f",
        "Purpose": "speed"
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
      "verb": "calls",
      "dst": "C2",
      "why": "reach engine",
      "where": "f"
    },
    {
      "src": "C1",
      "verb": "routes",
      "dst": "C3",
      "why": "dispatch",
      "where": "f"
    },
    {
      "src": "C3",
      "verb": "calls",
      "dst": "C2",
      "why": "reach engine",
      "where": "f"
    },
    {
      "src": "C2",
      "verb": "reads",
      "dst": "D1",
      "why": "cache",
      "where": "f"
    }
  ],
  "deployment": [],
  "observability": [],
  "security": [],
  "config": [],
  "tests_note": "",
  "tests": [],
  "extras": [
    {
      "heading": "Dependencies",
      "body": ""
    }
  ]
}"""


def make_nested_subsystem_map() -> str:
    """S1 (top) nests S2; S3 is a top-level sibling. C1 is a DIRECT member of S1, C2 a grandchild
    (member of S2), C3 lives in S3. Edges: C1->C2 (member -> child-subsystem box), C2->C3 (grandchild
    -> sibling subsystem). Exercises level-relative drill: S1's card must show S2 as a drillable box
    (not S2's components flattened in), and the C2->C3 crossing must resolve to the S3 box at S1's
    altitude."""
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
  "subsystems": [
    {
      "id": "S1",
      "name": "Platform",
      "purpose": "x",
      "parent": null,
      "source": "a/",
      "confidence": "V"
    },
    {
      "id": "S2",
      "name": "Inner",
      "purpose": "x",
      "parent": "S1",
      "source": "a/",
      "confidence": "V"
    },
    {
      "id": "S3",
      "name": "Other",
      "purpose": "x",
      "parent": null,
      "source": "a/",
      "confidence": "V"
    }
  ],
  "components": [
    {
      "id": "C1",
      "name": "Gate",
      "subsystem": "S1",
      "purpose": "x",
      "entry_point": "f",
      "depends_on": "C2",
      "source": null,
      "confidence": "",
      "extra": {}
    },
    {
      "id": "C2",
      "name": "Worker",
      "subsystem": "S2",
      "purpose": "x",
      "entry_point": "f",
      "depends_on": "C3",
      "source": null,
      "confidence": "",
      "extra": {}
    },
    {
      "id": "C3",
      "name": "Sink",
      "subsystem": "S3",
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
      "verb": "calls",
      "dst": "C2",
      "why": "dispatch",
      "where": "f"
    },
    {
      "src": "C2",
      "verb": "calls",
      "dst": "C3",
      "why": "forward",
      "where": "f"
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


def make_ungrouped_map() -> str:
    """No S table; prose mentions AWS S3/S4 (must not be treated as references)."""
    return """{
  "format": "coyodex-map",
  "title": "X",
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
      "name": "App",
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
  "edges": [],
  "deployment": [],
  "observability": [],
  "security": [],
  "config": [],
  "tests_note": "",
  "tests": [],
  "extras": []
}"""


def make_fenced_node_map() -> str:
    """A real C1 plus a fenced example mentioning C9 — the parser must not graph C9."""
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
  "subsystems": [
    {
      "id": "S1",
      "name": "A",
      "purpose": "x",
      "parent": null,
      "source": "a/",
      "confidence": "V"
    }
  ],
  "components": [
    {
      "id": "C1",
      "name": "Real",
      "subsystem": "S1",
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
  "edges": [],
  "deployment": [],
  "observability": [],
  "security": [],
  "config": [],
  "tests_note": "",
  "tests": [],
  "extras": [
    {
      "heading": "S",
      "body": ""
    },
    {
      "heading": "Example",
      "body": ""
    }
  ]
}"""


_CARDS_EMBEDDED_ENTITY_TYPE = (
    "**E1 — Order** *(s)*\nMEANING: m\nFIELDS: mode:E2 · id:int\nSOURCE: [f](f#L1)\n\n"
    "**E2 — AuthMode**\nMEANING: m\nFIELDS: x:int\nSOURCE: [f](f#L2)\n"
)


_CARDS_COLLECTION_MARKER = (
    "**E1 — Snapshot** *(s)*\nMEANING: m\n"
    "FIELDS: refresh_tokens:E2[] · expires_at:int ? · id:int PK\n"
    "RELATIONS: contains 1→* E2 StoredRefreshToken\nSOURCE: [f](f#L1)\n\n"
    "**E2 — StoredRefreshToken**\nMEANING: m\nFIELDS: token:string\nSOURCE: [f](f#L2)\n"
)


_CARDS_RELATION_LABELS = (
    "**E1 — Org** *(s)*\nMEANING: m\nFIELDS: id:string PK · subscription:E3\n"
    "RELATIONS: has 1→* E2 Membership · contains 1→1 E3 Subscription\nSOURCE: [f](f#L1)\n\n"
    "**E2 — Membership**\nMEANING: m\nFIELDS: org_id:string FK→E1 · email:string\nSOURCE: [f](f#L2)\n\n"
    "**E3 — Subscription**\nMEANING: m\nFIELDS: tier:string\nSOURCE: [f](f#L3)\n"
)


_CARDS_UNGROUNDED_VERB = (
    "**E1 — A** *(s)*\nMEANING: m\nFIELDS: id:int\n"
    "RELATIONS: authorizes *→1 E2\nSOURCE: [f](f#L1)\n\n"
    "**E2 — B**\nMEANING: m\nFIELDS: x:int\nSOURCE: [f](f#L2)\n"
)


_CARDS_FORWARD_FK = (
    "**E1 — Membership** *(s)*\nMEANING: m\nFIELDS: email:string · role:string FK→E2\n"
    "RELATIONS: assignedRole *→1 E2 RoleDefinition\nSOURCE: [f](f#L1)\n\n"
    "**E2 — RoleDefinition**\nMEANING: m\nFIELDS: name:string\nSOURCE: [f](f#L2)\n"
)


_CARDS_BACKING_HOW = (
    "**E1 — Org** *(s)*\nMEANING: m\nFIELDS: id:string PK\n"
    "RELATIONS: contains 1→* E2 Membership · tracks *→1 E3 Token {keyed by (org, upstream)}\n"
    "SOURCE: [f](f#L1)\n\n"
    "**E2 — Membership**\nMEANING: m\nFIELDS: org_id:string FK→E1\nSOURCE: [f](f#L2)\n\n"
    "**E3 — Token**\nMEANING: m\nFIELDS: value:string\nSOURCE: [f](f#L3)\n"
)


def make_domain_map(cards: str | None = None) -> str:
    """A minimal valid map whose T5 is domain CARDS. `cards` overrides the default two-entity body
    (Order contains LineItem; LineItem uses a bullet-list FIELDS)."""
    if cards is None:
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
      "name": "Search",
      "actor": "Shopper",
      "trigger_outcome": "types -> list"
    }
  ],
  "happy_path": [
    {
      "id": "HP1",
      "title": "Search",
      "uc": "UC1",
      "why": null
    }
  ],
  "subsystems": [],
  "components": [],
  "deps": [],
  "run_commands": [],
  "entry_points": [],
  "subdomains": [],
  "entities": [
    {
      "id": "E1",
      "name": "Order",
      "store": "orders collection",
      "meaning": "a purchase",
      "subdomain": null,
      "source": "order.py:12",
      "fields": [
        {
          "name": "id",
          "type": "ObjectId",
          "markers": [
            "PK"
          ]
        },
        {
          "name": "status",
          "type": "string",
          "markers": []
        }
      ],
      "relations": [
        {
          "verb": "contains",
          "target": "E2",
          "src_card": "1",
          "dst_card": "*",
          "display": "LineItem",
          "how": null
        }
      ]
    },
    {
      "id": "E2",
      "name": "LineItem",
      "store": "",
      "meaning": "a line",
      "subdomain": null,
      "source": "order.py:58",
      "fields": [
        {
          "name": "sku",
          "type": "string",
          "markers": []
        },
        {
          "name": "qty",
          "type": "int",
          "markers": []
        }
      ],
      "relations": []
    }
  ],
  "non_entity_types": [],
  "flows": [],
  "edges": [],
  "deployment": [],
  "observability": [],
  "security": [],
  "config": [],
  "tests_note": "",
  "tests": [],
  "extras": []
}"""
    if cards == _CARDS_EMBEDDED_ENTITY_TYPE:
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
      "name": "Search",
      "actor": "Shopper",
      "trigger_outcome": "types -> list"
    }
  ],
  "happy_path": [
    {
      "id": "HP1",
      "title": "Search",
      "uc": "UC1",
      "why": null
    }
  ],
  "subsystems": [],
  "components": [],
  "deps": [],
  "run_commands": [],
  "entry_points": [],
  "subdomains": [],
  "entities": [
    {
      "id": "E1",
      "name": "Order",
      "store": "s",
      "meaning": "m",
      "subdomain": null,
      "source": "f:1",
      "fields": [
        {
          "name": "mode",
          "type": "E2",
          "markers": []
        },
        {
          "name": "id",
          "type": "int",
          "markers": []
        }
      ],
      "relations": []
    },
    {
      "id": "E2",
      "name": "AuthMode",
      "store": "",
      "meaning": "m",
      "subdomain": null,
      "source": "f:2",
      "fields": [
        {
          "name": "x",
          "type": "int",
          "markers": []
        }
      ],
      "relations": []
    }
  ],
  "non_entity_types": [],
  "flows": [],
  "edges": [],
  "deployment": [],
  "observability": [],
  "security": [],
  "config": [],
  "tests_note": "",
  "tests": [],
  "extras": []
}"""
    if cards == _CARDS_COLLECTION_MARKER:
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
      "name": "Search",
      "actor": "Shopper",
      "trigger_outcome": "types -> list"
    }
  ],
  "happy_path": [
    {
      "id": "HP1",
      "title": "Search",
      "uc": "UC1",
      "why": null
    }
  ],
  "subsystems": [],
  "components": [],
  "deps": [],
  "run_commands": [],
  "entry_points": [],
  "subdomains": [],
  "entities": [
    {
      "id": "E1",
      "name": "Snapshot",
      "store": "s",
      "meaning": "m",
      "subdomain": null,
      "source": "f:1",
      "fields": [
        {
          "name": "refresh_tokens",
          "type": "E2",
          "markers": [
            "[]"
          ]
        },
        {
          "name": "expires_at",
          "type": "int",
          "markers": [
            "?"
          ]
        },
        {
          "name": "id",
          "type": "int",
          "markers": [
            "PK"
          ]
        }
      ],
      "relations": [
        {
          "verb": "contains",
          "target": "E2",
          "src_card": "1",
          "dst_card": "*",
          "display": "StoredRefreshToken",
          "how": null
        }
      ]
    },
    {
      "id": "E2",
      "name": "StoredRefreshToken",
      "store": "",
      "meaning": "m",
      "subdomain": null,
      "source": "f:2",
      "fields": [
        {
          "name": "token",
          "type": "string",
          "markers": []
        }
      ],
      "relations": []
    }
  ],
  "non_entity_types": [],
  "flows": [],
  "edges": [],
  "deployment": [],
  "observability": [],
  "security": [],
  "config": [],
  "tests_note": "",
  "tests": [],
  "extras": []
}"""
    if cards == _CARDS_RELATION_LABELS:
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
      "name": "Search",
      "actor": "Shopper",
      "trigger_outcome": "types -> list"
    }
  ],
  "happy_path": [
    {
      "id": "HP1",
      "title": "Search",
      "uc": "UC1",
      "why": null
    }
  ],
  "subsystems": [],
  "components": [],
  "deps": [],
  "run_commands": [],
  "entry_points": [],
  "subdomains": [],
  "entities": [
    {
      "id": "E1",
      "name": "Org",
      "store": "s",
      "meaning": "m",
      "subdomain": null,
      "source": "f:1",
      "fields": [
        {
          "name": "id",
          "type": "string",
          "markers": [
            "PK"
          ]
        },
        {
          "name": "subscription",
          "type": "E3",
          "markers": []
        }
      ],
      "relations": [
        {
          "verb": "has",
          "target": "E2",
          "src_card": "1",
          "dst_card": "*",
          "display": "Membership",
          "how": null
        },
        {
          "verb": "contains",
          "target": "E3",
          "src_card": "1",
          "dst_card": "1",
          "display": "Subscription",
          "how": null
        }
      ]
    },
    {
      "id": "E2",
      "name": "Membership",
      "store": "",
      "meaning": "m",
      "subdomain": null,
      "source": "f:2",
      "fields": [
        {
          "name": "org_id",
          "type": "string",
          "markers": [
            "FK→E1"
          ]
        },
        {
          "name": "email",
          "type": "string",
          "markers": []
        }
      ],
      "relations": []
    },
    {
      "id": "E3",
      "name": "Subscription",
      "store": "",
      "meaning": "m",
      "subdomain": null,
      "source": "f:3",
      "fields": [
        {
          "name": "tier",
          "type": "string",
          "markers": []
        }
      ],
      "relations": []
    }
  ],
  "non_entity_types": [],
  "flows": [],
  "edges": [],
  "deployment": [],
  "observability": [],
  "security": [],
  "config": [],
  "tests_note": "",
  "tests": [],
  "extras": []
}"""
    if cards == _CARDS_UNGROUNDED_VERB:
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
      "name": "Search",
      "actor": "Shopper",
      "trigger_outcome": "types -> list"
    }
  ],
  "happy_path": [
    {
      "id": "HP1",
      "title": "Search",
      "uc": "UC1",
      "why": null
    }
  ],
  "subsystems": [],
  "components": [],
  "deps": [],
  "run_commands": [],
  "entry_points": [],
  "subdomains": [],
  "entities": [
    {
      "id": "E1",
      "name": "A",
      "store": "s",
      "meaning": "m",
      "subdomain": null,
      "source": "f:1",
      "fields": [
        {
          "name": "id",
          "type": "int",
          "markers": []
        }
      ],
      "relations": [
        {
          "verb": "authorizes",
          "target": "E2",
          "src_card": "*",
          "dst_card": "1",
          "display": "",
          "how": null
        }
      ]
    },
    {
      "id": "E2",
      "name": "B",
      "store": "",
      "meaning": "m",
      "subdomain": null,
      "source": "f:2",
      "fields": [
        {
          "name": "x",
          "type": "int",
          "markers": []
        }
      ],
      "relations": []
    }
  ],
  "non_entity_types": [],
  "flows": [],
  "edges": [],
  "deployment": [],
  "observability": [],
  "security": [],
  "config": [],
  "tests_note": "",
  "tests": [],
  "extras": []
}"""
    if cards == _CARDS_FORWARD_FK:
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
      "name": "Search",
      "actor": "Shopper",
      "trigger_outcome": "types -> list"
    }
  ],
  "happy_path": [
    {
      "id": "HP1",
      "title": "Search",
      "uc": "UC1",
      "why": null
    }
  ],
  "subsystems": [],
  "components": [],
  "deps": [],
  "run_commands": [],
  "entry_points": [],
  "subdomains": [],
  "entities": [
    {
      "id": "E1",
      "name": "Membership",
      "store": "s",
      "meaning": "m",
      "subdomain": null,
      "source": "f:1",
      "fields": [
        {
          "name": "email",
          "type": "string",
          "markers": []
        },
        {
          "name": "role",
          "type": "string",
          "markers": [
            "FK→E2"
          ]
        }
      ],
      "relations": [
        {
          "verb": "assignedRole",
          "target": "E2",
          "src_card": "*",
          "dst_card": "1",
          "display": "RoleDefinition",
          "how": null
        }
      ]
    },
    {
      "id": "E2",
      "name": "RoleDefinition",
      "store": "",
      "meaning": "m",
      "subdomain": null,
      "source": "f:2",
      "fields": [
        {
          "name": "name",
          "type": "string",
          "markers": []
        }
      ],
      "relations": []
    }
  ],
  "non_entity_types": [],
  "flows": [],
  "edges": [],
  "deployment": [],
  "observability": [],
  "security": [],
  "config": [],
  "tests_note": "",
  "tests": [],
  "extras": []
}"""
    if cards == _CARDS_BACKING_HOW:
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
      "name": "Search",
      "actor": "Shopper",
      "trigger_outcome": "types -> list"
    }
  ],
  "happy_path": [
    {
      "id": "HP1",
      "title": "Search",
      "uc": "UC1",
      "why": null
    }
  ],
  "subsystems": [],
  "components": [],
  "deps": [],
  "run_commands": [],
  "entry_points": [],
  "subdomains": [],
  "entities": [
    {
      "id": "E1",
      "name": "Org",
      "store": "s",
      "meaning": "m",
      "subdomain": null,
      "source": "f:1",
      "fields": [
        {
          "name": "id",
          "type": "string",
          "markers": [
            "PK"
          ]
        }
      ],
      "relations": [
        {
          "verb": "contains",
          "target": "E2",
          "src_card": "1",
          "dst_card": "*",
          "display": "Membership",
          "how": null
        },
        {
          "verb": "tracks",
          "target": "E3",
          "src_card": "*",
          "dst_card": "1",
          "display": "Token",
          "how": "keyed by (org, upstream)"
        }
      ]
    },
    {
      "id": "E2",
      "name": "Membership",
      "store": "",
      "meaning": "m",
      "subdomain": null,
      "source": "f:2",
      "fields": [
        {
          "name": "org_id",
          "type": "string",
          "markers": [
            "FK→E1"
          ]
        }
      ],
      "relations": []
    },
    {
      "id": "E3",
      "name": "Token",
      "store": "",
      "meaning": "m",
      "subdomain": null,
      "source": "f:3",
      "fields": [
        {
          "name": "value",
          "type": "string",
          "markers": []
        }
      ],
      "relations": []
    }
  ],
  "non_entity_types": [],
  "flows": [],
  "edges": [],
  "deployment": [],
  "observability": [],
  "security": [],
  "config": [],
  "tests_note": "",
  "tests": [],
  "extras": []
}"""
    raise ValueError("make_domain_map: unrecognised `cards` fixture")


def make_gp_map() -> str:
    """A two-step Happy Path (HP1=UC1 actor Andy, HP2=UC2 actor Adam) + the two use-case T6 flows.
    Exercises the GP overview sequence (actors from the UCs) and each use case's flow sequence."""
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
      "name": "Submit",
      "actor": "Andy",
      "trigger_outcome": "submits -> stored"
    },
    {
      "id": "UC2",
      "name": "Approve",
      "actor": "Adam",
      "trigger_outcome": "approves -> done"
    }
  ],
  "happy_path": [
    {
      "id": "HP1",
      "title": "Submit order",
      "uc": "UC1",
      "why": null
    },
    {
      "id": "HP2",
      "title": "Approve order",
      "uc": "UC2",
      "why": "needs the order from HP1"
    }
  ],
  "subsystems": [],
  "components": [
    {
      "id": "C1",
      "name": "Gateway",
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
      "name": "Engine",
      "subsystem": null,
      "purpose": "x",
      "entry_point": "f",
      "depends_on": "D1",
      "source": null,
      "confidence": "",
      "extra": {}
    }
  ],
  "deps": [
    {
      "id": "D1",
      "name": "Cache",
      "kind": null,
      "type": "store",
      "used_for": "speed",
      "where_configured": "env",
      "confidence": "V",
      "deployment_linked": false,
      "extra": {}
    }
  ],
  "run_commands": [],
  "entry_points": [],
  "subdomains": [],
  "entities": [],
  "non_entity_types": [],
  "flows": [
    {
      "uc": "UC1",
      "title": "Submit order",
      "steps": [
        {
          "n": 1,
          "src": "Andy",
          "dst": "C1",
          "phrase": "submits the order",
          "note": ""
        },
        {
          "n": 2,
          "src": "C1",
          "dst": "C2",
          "phrase": "",
          "note": ""
        }
      ]
    },
    {
      "uc": "UC2",
      "title": "Approve order",
      "steps": [
        {
          "n": 1,
          "src": "Adam",
          "dst": "C2",
          "phrase": "approves the order",
          "note": ""
        },
        {
          "n": 2,
          "src": "C2",
          "dst": "D1",
          "phrase": "",
          "note": ""
        }
      ]
    }
  ],
  "edges": [
    {
      "src": "C1",
      "verb": "calls",
      "dst": "C2",
      "why": "reach engine",
      "where": "f"
    },
    {
      "src": "C2",
      "verb": "reads",
      "dst": "D1",
      "why": "cache",
      "where": "f"
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


def make_gp_role_actor_map(flow_actor: str = "Org admin") -> str:
    """A Happy Path step whose use case's actor matches a defined Role, so hp_actors can join the
    lifeline to the Roles table (wants + kind). The T6 flow opens with an actor step; every kept test
    uses the default Role-matching actor (the undefined-actor variant only served the retired
    validator test)."""
    return """{
  "format": "coyodex-map",
  "title": "",
  "goal": "",
  "commit": null,
  "committed": null,
  "built": null,
  "roles": [
    {
      "name": "Org admin",
      "kind": "human",
      "wants": "manage",
      "drives": "UC22"
    }
  ],
  "glossary": [],
  "use_cases": [
    {
      "id": "UC22",
      "name": "Create org",
      "actor": "Org admin",
      "trigger_outcome": "a -> b"
    }
  ],
  "happy_path": [
    {
      "id": "HP1",
      "title": "Admin creates the org",
      "uc": "UC22",
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
      "uc": "UC22",
      "title": "Create org",
      "steps": [
        {
          "n": 1,
          "src": "Org admin",
          "dst": "C1",
          "phrase": "creates the org",
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


def parse_map(json_text: str) -> build_graph.GraphDict:
    """Graph from the scenario map (a JSON model document), through the LIVE pipeline:
    load_model → model_to_graph."""
    return model_to_graph(load_model(json_text))


def test_parser_proper_layout_names_and_parents() -> None:
    g = parse_map(make_grouped_map("proper"))
    comps = {k: v for k, v in g["nodes"].items() if v["kind"] == "component"}
    assert comps["C1"]["name"] == "Front door"
    assert comps["C1"]["parent"] == "S1" and comps["C2"]["parent"] == "S2"


def test_parser_agent_layout_reads_membership_and_falls_back_name() -> None:
    g = parse_map(make_grouped_map("agent"))  # no name col, Subsystem at index 1
    comps = {k: v for k, v in g["nodes"].items() if v["kind"] == "component"}
    assert comps["C1"]["parent"] == "S1"   # membership still read (the bug we fixed)
    assert comps["C1"]["name"] == "C1"     # falls back to id, never the subsystem "S1"


def test_parser_subsystem_nodes_and_edges() -> None:
    g = parse_map(make_grouped_map("agent"))
    assert {k for k, v in g["nodes"].items() if v["kind"] == "subsystem"} == {"S1", "S2"}
    assert any(e["src"] == "C1" and e["dst"] == "C2" for e in g["edges"])


def test_default_subsystem_injected_when_ungrouped() -> None:
    # A map with components but no Subsystem table gets ONE synthetic subsystem named after the project,
    # with every component reparented under it — so the component-level view always sits under a
    # subsystem (the flat Components map is no longer the only home for components).
    g = parse_map(make_ungrouped_map())  # title 'X', one component C1, no S table
    subs = {k: v for k, v in g["nodes"].items() if v["kind"] == "subsystem"}
    assert set(subs) == {build_graph.DEFAULT_SUBSYSTEM_ID}
    assert subs[build_graph.DEFAULT_SUBSYSTEM_ID]["name"] == "X"
    assert g["nodes"]["C1"]["parent"] == build_graph.DEFAULT_SUBSYSTEM_ID
    assert gen_viewer.has_grouping(g) is True


def test_no_default_subsystem_when_already_grouped() -> None:
    # A map that already groups its components is left untouched — no S0, the real subsystems stand.
    g = parse_map(make_grouped_map("proper"))
    assert build_graph.DEFAULT_SUBSYSTEM_ID not in g["nodes"]
    assert {k for k, v in g["nodes"].items() if v["kind"] == "subsystem"} == {"S1", "S2"}


def test_no_default_subsystem_for_pure_domain_map() -> None:
    # No components -> nothing to group -> no synthetic subsystem (a pure domain map stays ungrouped).
    g = parse_map(make_domain_map())
    assert build_graph.DEFAULT_SUBSYSTEM_ID not in g["nodes"]
    assert not any(v["kind"] == "subsystem" for v in g["nodes"].values())


def test_subsystem_card_keeps_internal_wiring_and_deps() -> None:
    # Q1=B: a subsystem card shows the subsystem's own components, their internal edges, and the
    # deps they touch — but never a sibling subsystem's component.
    by_sub = gen_viewer.subsystem_component_mermaids(parse_map(make_card_map()))
    s1 = by_sub["S1"]
    assert "subgraph S1[" in s1                         # the subsystem reads as a labelled frame
    assert "C1" in s1 and "C3" in s1                    # both S1 components present
    assert "C1 -->|routes| C3" in s1                    # internal wiring kept
    assert "class S2 subsystem" in s1                   # the neighbour S2 drawn as a collapsed box
    assert "C1 --> S2" in s1 and "C3 --> S2" in s1      # cross arrows: component -> neighbour box (no label)
    assert "C2" not in s1                               # the sibling's component itself is NOT drawn
    s2 = by_sub["S2"]
    assert "subgraph S2[" in s2
    assert "C2" in s2 and "D1" in s2                    # Q1=B keeps the dep the component touches
    assert "C2 -->|reads| D1" in s2                     # ...with its component->dep edge
    assert "class S1 subsystem" in s2                   # the neighbour S1 box
    assert "S1 --> C2" in s2                            # inbound cross arrow: neighbour box -> member


def test_edge_card_has_both_subsystems_with_cross_and_inner_edges() -> None:
    # Q2=A: an edge card frames BOTH subsystems with ALL their components, draws the A->B
    # component edges AND each subsystem's own internal wiring — but no deps, no other-subsystem
    # edges, and only the A->B direction of the crossing.
    g = parse_map(make_card_map())
    cards = gen_viewer.edge_card_mermaids(g)
    assert set(cards) == {"S1>S2"}                      # only the direction that actually crosses
    card = cards["S1>S2"]
    assert "subgraph S1[" in card and "subgraph S2[" in card
    assert "C1" in card and "C3" in card and "C2" in card   # all components of both (Q2=A)
    assert "C1 -->|calls| C2" in card and "C3 -->|calls| C2" in card  # the cross edges
    assert "C1 -->|routes| C3" in card                  # S1's inner link now kept
    assert "D1" not in card                             # no deps in an edge card


def test_nested_subsystem_has_card_at_every_level() -> None:
    # A card is generated for the NESTED subsystem S2, not only top-level ones — so ⌘-clicking the S2
    # box inside S1's card has a card to open.
    by_sub = gen_viewer.subsystem_component_mermaids(parse_map(make_nested_subsystem_map()))
    assert {"S1", "S2", "S3"} <= set(by_sub)


def test_nested_parent_card_shows_child_subsystem_box_not_flattened() -> None:
    # S1's card shows its DIRECT member C1 and its child subsystem S2 as a drillable box — and does NOT
    # flatten S2's grandchild component C2 into the card (that lives one level down, on S2's card).
    by_sub = gen_viewer.subsystem_component_mermaids(parse_map(make_nested_subsystem_map()))
    s1 = by_sub["S1"]
    assert "subgraph S1[" in s1
    assert "C1" in s1                       # direct member
    assert "class S2 subsystem" in s1       # child subsystem as a (drillable) collapsed box
    assert "C2" not in s1                   # grandchild NOT flattened into the parent card
    assert "C1 --> S2" in s1                # member -> child-subsystem box (aggregated, drills in)


def test_nested_crossing_resolves_at_card_level() -> None:
    # C2 (in S2) -> C3 (in S3): on S1's card this reads as the child box S2 -> the sibling box S3,
    # resolved at S1's altitude (not flattened to top). On S2's own card the grandchild's external link
    # to S3 is drawn directly.
    by_sub = gen_viewer.subsystem_component_mermaids(parse_map(make_nested_subsystem_map()))
    s1 = by_sub["S1"]
    assert "S2 --> S3" in s1
    assert "class S3 subsystem" in s1       # the sibling neighbour box
    s2 = by_sub["S2"]
    assert "C2" in s2 and "C2 --> S3" in s2


def test_container_overview_shows_only_top_level_subsystems() -> None:
    # The Subsystems overview draws only top-level groups (S1, S3); the nested S2 is reachable by
    # drilling S1, not as a top-level box. The nested C2->C3 edge aggregates to the top S1->S3 arrow.
    cont = gen_viewer.gen_container_mermaid(parse_map(make_nested_subsystem_map()))
    assert 'S1["' in cont and 'S3["' in cont
    assert 'S2["' not in cont
    assert "S1 -->|1| S3" in cont


def test_nested_edge_cards_for_disjoint_pairs_only() -> None:
    # The parent->child crossing (C1->C2, the S1>S2 overlap) is NOT an edge card — it's navigated.
    # The disjoint crossing C2->C3 gets a card at every level it is drawn: S2>S3 (nested card) and
    # S1>S3 (overview / S1 card), each framing two non-overlapping subsystems.
    cards = gen_viewer.edge_card_mermaids(parse_map(make_nested_subsystem_map()))
    assert "S1>S2" not in cards
    assert {"S2>S3", "S1>S3"} <= set(cards)
    s2s3 = cards["S2>S3"]
    assert "subgraph S2[" in s2s3 and "subgraph S3[" in s2s3
    assert "C2 -->|calls| C3" in s2s3            # a direct-member crossing stays labelled
    assert "S2 --> C3" in cards["S1>S3"]         # a crossing reaching into child S2 is an aggregated box arrow


def test_nested_container_edges_keyed_per_level() -> None:
    ce = gen_viewer.gen_container_edges(parse_map(make_nested_subsystem_map()))
    assert {"S2>S3", "S1>S3"} <= set(ce)
    assert {(r["src"], r["dst"]) for r in ce["S2>S3"]} == {("C2", "C3")}


def make_nested_bridge_map() -> str:
    """A nested subsystem (S2<-S1) and nested subdomain (SD2<-SD1) joined by a C->E owns edge — so a
    bridge arrow can be drawn on a NESTED subsystem card AND a nested subdomain card (review finding #1)."""
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
  "subsystems": [
    {
      "id": "S1",
      "name": "Outer",
      "purpose": "x",
      "parent": null,
      "source": "a/",
      "confidence": "V"
    },
    {
      "id": "S2",
      "name": "Inner",
      "purpose": "x",
      "parent": "S1",
      "source": "a/",
      "confidence": "V"
    }
  ],
  "components": [
    {
      "id": "C1",
      "name": "Repo",
      "subsystem": "S2",
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
  "subdomains": [
    {
      "id": "SD1",
      "name": "DomOuter",
      "purpose": "x",
      "parent": null,
      "source": "f:1",
      "confidence": "inferred"
    },
    {
      "id": "SD2",
      "name": "DomInner",
      "purpose": "x",
      "parent": "SD1",
      "source": "f:1",
      "confidence": "inferred"
    }
  ],
  "entities": [
    {
      "id": "E1",
      "name": "Order",
      "store": "orders",
      "meaning": "x",
      "subdomain": "SD2",
      "source": "f:1",
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
      "verb": "persists",
      "dst": "E1",
      "why": "store",
      "where": "f"
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


def test_nested_bridge_cards_keyed_per_level() -> None:
    # The JS requests a bridge card for whatever S/SD boxes a card draws: S2>SD1 from the nested
    # subsystem card (top-subdomain box) and S1>SD2 from the nested subdomain card (top-subsystem box).
    # Every (subsystem-ancestor, subdomain-ancestor) pair must be generated so no drill misses its key.
    keys = set(gen_viewer.bridge_card_mermaids(parse_map(make_nested_bridge_map())))
    assert {"S1>SD1", "S2>SD1", "S1>SD2", "S2>SD2"} <= keys


def test_container_edges_list_crossing_component_edges() -> None:
    # Each inter-subsystem arrow 'A>B' carries the underlying component->component edges (endpoints,
    # names, verb, why) so the viewer lists their meanings in the arrow's hover tooltip.
    ce = gen_viewer.gen_container_edges(parse_map(make_card_map()))
    assert set(ce) == {"S1>S2"}                          # only the crossing direction
    rows = ce["S1>S2"]
    assert {(r["src"], r["dst"]) for r in rows} == {("C1", "C2"), ("C3", "C2")}
    assert {r["srcName"] for r in rows} == {"Front door", "Router"}
    assert all(r["verb"] == "calls" and r["why"] == "reach engine" for r in rows)


def test_bundle_carries_edge_card_data() -> None:
    # The served bundle must carry the edge-card diagrams AND the per-arrow component-edge lists so the
    # client opens on click / previews on hover.
    b = bundle_of(make_card_map())
    assert "S1>S2" in b["containerEdges"] and "S1>S2" in b["mermaidEdgeCard"]


def test_parser_ignores_fenced_nodes() -> None:
    # The graph parser must also skip fenced examples — no phantom C9 node from the example.
    g = parse_map(make_fenced_node_map())
    assert "C1" in g["nodes"] and "C9" not in g["nodes"], list(g["nodes"])


def test_shell_pins_libs_and_bundle_carries_node_names() -> None:
    # Chrome lives in the served shell (pinned+SRI CDN libs, inline favicon); the map data lives in the
    # bundle (node names the client renders).
    shell = (VIEWER_DIR / "viewer.html").read_text(encoding="utf-8")
    assert 'integrity="sha384-' in shell and 'rel="icon"' in shell
    b = bundle_of(make_grouped_map("proper"))
    names = {n.get("name") for n in b["graph"]["nodes"].values()}
    assert "Front door" in names


def test_bundle_has_nested_drill_data() -> None:
    # A nested map's bundle carries an edge card for each DISJOINT cross-pair at every level (S2>S3
    # nested, S1>S3 overview) and omits the overlapping parent-child pair (S1>S2, which navigates).
    keys = set(bundle_of(make_nested_subsystem_map())["mermaidEdgeCard"])
    assert "S2>S3" in keys and "S1>S3" in keys and "S1>S2" not in keys


def make_report_map() -> str:
    """A minimal change-impact report: C2 modified, C9 added (C9 is not in the base map). Drives the
    diff overlay — its base→new header + a `change` table are what build_diff parses."""
    return (
        "# Change impact: abc → def\n\n"
        "| Element | Change | Name | Kind | Note |\n"
        "|---|---|---|---|---|\n"
        "| **C2** | modified | Engine | component | tweaked |\n"
        "| **C9** | added | NewWorker | component | new |\n"
    )


def test_shell_has_no_components_tab_but_js_keeps_generators() -> None:
    # The flat Components map is no longer a tab; its generators stay in the frontend so it can be restored.
    shell = (VIEWER_DIR / "viewer.html").read_text(encoding="utf-8")
    js = (VIEWER_DIR / "viewer.js").read_text(encoding="utf-8")
    assert 'data-view="component"' not in shell        # the Components tab button is gone
    assert 'data-view="container"' in shell            # Subsystems remains
    assert "MERMAID_BASE" in js and "bindComponent" in js  # generators kept dormant (restorable)


def test_diff_overlay_bundle_and_landing() -> None:
    # With a change-impact report the diff overlay is armed: the bundle carries hasDiff + diffState, the
    # frontend lands on the Subsystems overview for a diff, and never resurrects the flat Components map.
    with tempfile.TemporaryDirectory() as d:
        report = Path(d) / "report.md"
        report.write_text(make_report_map(), encoding="utf-8")
        b = bundle_of(make_grouped_map("proper"), report)
    assert b["hasDiff"] is True
    assert b["diffState"].get("C2") == "modified" and b["diffState"].get("C9") == "added"
    js = (VIEWER_DIR / "viewer.js").read_text(encoding="utf-8")
    assert "(HAS_DIFF && HAS_GROUPING) ? 'container'" in js  # still lands on Subsystems for a diff
    assert "HAS_HP ? 'hp'" in js                             # otherwise the Happy Path is the landing view
    shell = (VIEWER_DIR / "viewer.html").read_text(encoding="utf-8")
    assert 'data-view="component"' not in shell        # never resurrects the flat map


def test_glued_collection_relation_is_labelled() -> None:
    """An entity-typed collection field written glued (`tokens:E28[]`) must still BACK its relation,
    so the composition arrow renders its real field name as the label (not blank)."""
    cards = """{
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
  "components": [],
  "deps": [],
  "run_commands": [],
  "entry_points": [],
  "subdomains": [],
  "entities": [
    {
      "id": "E1",
      "name": "Snapshot",
      "store": "s",
      "meaning": "m",
      "subdomain": null,
      "source": "f:1",
      "fields": [
        {
          "name": "clients",
          "type": "json",
          "markers": []
        },
        {
          "name": "access_tokens",
          "type": "E28",
          "markers": [
            "[]"
          ]
        }
      ],
      "relations": [
        {
          "verb": "contains",
          "target": "E28",
          "src_card": "1",
          "dst_card": "*",
          "display": "StoredAccessToken",
          "how": null
        }
      ]
    },
    {
      "id": "E28",
      "name": "StoredAccessToken",
      "store": "",
      "meaning": "m",
      "subdomain": null,
      "source": "f:2",
      "fields": [
        {
          "name": "token",
          "type": "string",
          "markers": [
            "PK"
          ]
        }
      ],
      "relations": []
    }
  ],
  "non_entity_types": [],
  "flows": [],
  "edges": [],
  "deployment": [],
  "observability": [],
  "security": [],
  "config": [],
  "tests_note": "",
  "tests": [],
  "extras": []
}"""
    g = parse_map(cards)
    rel = [e for e in g["edges"] if e["src"] == "E1" and e["dst"] == "E28"][0]
    assert rel["fk_fields"] == ["access_tokens"] and rel["fk_side"] == "src"


def test_parser_domain_cards_nodes_attrs_edges() -> None:
    g = parse_map(make_domain_map())
    e1 = g["nodes"]["E1"]
    assert e1["kind"] == "entity" and e1["name"] == "Order"
    assert cast("dict[str, str]", e1["fields"])["Stored"] == "orders collection"
    attrs1 = cast("list[dict[str, str]]", e1["attrs"])
    assert any(a["name"] == "id" and a["type"] == "ObjectId" and a["markers"] == "PK" for a in attrs1)
    attrs2 = cast("list[dict[str, str]]", g["nodes"]["E2"]["attrs"])
    assert {a["name"] for a in attrs2} == {"sku", "qty"}   # bullet-list FIELDS
    rel = [e for e in g["edges"] if e["src"] == "E1" and e["dst"] == "E2"]
    assert rel and rel[0]["verb"] == "contains" and rel[0]["kind"] == "composition"
    assert rel[0]["src_card"] == "1" and rel[0]["dst_card"] == "*"


def test_gen_domain_mermaid_classdiagram() -> None:
    mm = gen_viewer.gen_domain_mermaid(parse_map(make_domain_map()))
    assert mm.startswith("classDiagram")
    assert 'class E1["Order"]' in mm
    assert "ObjectId id" in mm                          # attribute rendered in the box
    assert 'E1 "1" *-- "*" E2' in mm                    # composition arrow + cardinality
    assert ": contains" not in mm                       # redundant structural verb is not drawn as a label


def test_gen_domain_mermaid_resolves_embedded_entity_type() -> None:
    # a field typed by an entity id (`mode:E2`) renders with the entity's NAME, not the raw id.
    mm = gen_viewer.gen_domain_mermaid(parse_map(make_domain_map(_CARDS_EMBEDDED_ENTITY_TYPE)))
    assert "AuthMode mode" in mm and "E2 mode" not in mm


def test_gen_domain_mermaid_shows_collection_marker_in_box() -> None:
    # a `[]` (collection) marker is part of the type SHAPE, so it renders in the box member —
    # `StoredRefreshToken[] refresh_tokens`, not a single-valued-looking `StoredRefreshToken …`.
    # `?`/PK/FK stay out of the box (annotations, panel-only).
    mm = gen_viewer.gen_domain_mermaid(parse_map(make_domain_map(_CARDS_COLLECTION_MARKER)))
    assert "StoredRefreshToken[] refresh_tokens" in mm   # collection shown in the box
    assert "int expires_at" in mm and "int? " not in mm  # nullable marker stays out of the box
    assert "int id" in mm                                # PK stays out of the box


def test_gen_domain_mermaid_relation_labels() -> None:
    # forward field -> plain name; reverse FK (FK→E1) -> "↩ field"; the redundant verb is dropped.
    mm = gen_viewer.gen_domain_mermaid(parse_map(make_domain_map(_CARDS_RELATION_LABELS)))
    assert ": subscription" in mm     # forward: E1.subscription typed E3
    assert ": ↩ org_id" in mm          # reverse: E2.org_id FK→E1
    assert ": has" not in mm           # the redundant aggregation verb is not drawn


def test_gen_domain_mermaid_drops_ungrounded_verb() -> None:
    # an association not backed by any field gets NO label — the verb is interpretive, not grounded.
    mm = gen_viewer.gen_domain_mermaid(parse_map(make_domain_map(_CARDS_UNGROUNDED_VERB)))
    assert "authorizes" not in mm     # ungrounded association verb is not drawn as a label


def test_gen_domain_mermaid_forward_fk_label() -> None:
    # A foreign key on the SOURCE (`role:string FK→E2`) labels the arrow with the field name — the
    # symmetric counterpart of the reverse `↩` case, so a marked FK is represented whichever side
    # authored the relation (the asymmetry that left all but one mcpolis FK arrow blank is gone).
    mm = gen_viewer.gen_domain_mermaid(parse_map(make_domain_map(_CARDS_FORWARD_FK)))
    assert ": role" in mm                  # forward FK -> the plain field name
    assert "↩" not in mm                   # not a back-reference (the field is on the source/tail)
    assert ": assignedRole" not in mm      # the verb itself is never drawn as the label


def test_fk_targets_token_exact() -> None:
    # `FK→E1` must resolve to exactly {E1} — never match inside `E11` (the substring bug class).
    assert grammar.fk_targets("FK→E1") == {"E1"}
    assert grammar.fk_targets(["?", "FK->E5"]) == {"E5"}      # ascii arrow + nullable marker
    assert "E1" not in grammar.fk_targets("FK→E11")


def test_resolve_backing_composite_key_keeps_all_fields() -> None:
    # A composite foreign key — Snapshot's (user_id, page_id) both `FK→TrackedPage` — must resolve to
    # BOTH backing fields, not arbitrarily just the first, so the label shows the whole key.
    snapshot = [("user_id", "string", {"E1"}), ("page_id", "string", {"E1"}),
                ("snapshot_id", "string", set())]
    trackedpage = [("user_id", "string", set()), ("page_id", "string", set())]
    fields, side = grammar.resolve_backing("E2", "E1", snapshot, trackedpage)
    assert fields == ["user_id", "page_id"] and side == "src"


def test_relation_label_composite_key_joins_fields() -> None:
    # The canvas arrow label lists every backing field of a composite key, comma-joined.
    assert gen_viewer._relation_label({"fk_fields": ["user_id", "page_id"], "fk_side": "src"}) \
        == "user_id, page_id"
    # Reverse (FK on the head) keeps the back-reference marker in front of the joined list.
    assert gen_viewer._relation_label({"fk_fields": ["user_id", "page_id"], "fk_side": "dst"}) \
        == "↩ user_id, page_id"


def test_parser_domain_edge_carries_backing_and_how() -> None:
    # The resolved backing (fk_fields/fk_side) and the authored {how} note ride the serialized edge,
    # so the canvas label and the panel's "Implemented by" line come from one resolution.
    g = parse_map(make_domain_map(_CARDS_BACKING_HOW))
    e12 = next(e for e in g["edges"] if e["src"] == "E1" and e["dst"] == "E2")
    assert e12["fk_fields"] == ["org_id"] and e12["fk_side"] == "dst"   # reverse FK on the target
    e13 = next(e for e in g["edges"] if e["src"] == "E1" and e["dst"] == "E3")
    assert e13["fk_fields"] == [] and e13["how"] == "keyed by (org, upstream)"  # indirect -> how-note


def test_class_diagram_inheritance_arrow_labelled_inferred() -> None:
    # Verb principle: the inheritance triangle trusts the authored `isA` verb (never code-verified),
    # so it renders labelled inferred — a derivation, not an asserted fact (verbs prioritize, never gate).
    md = """{
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
  "components": [],
  "deps": [],
  "run_commands": [],
  "entry_points": [],
  "subdomains": [],
  "entities": [
    {
      "id": "E1",
      "name": "Base",
      "store": "s",
      "meaning": "m",
      "subdomain": null,
      "source": "f:1",
      "fields": [
        {
          "name": "id",
          "type": "int",
          "markers": []
        }
      ],
      "relations": []
    },
    {
      "id": "E2",
      "name": "Child",
      "store": "s",
      "meaning": "m",
      "subdomain": null,
      "source": "f:2",
      "fields": [
        {
          "name": "id",
          "type": "int",
          "markers": []
        }
      ],
      "relations": [
        {
          "verb": "isA",
          "target": "E1",
          "src_card": null,
          "dst_card": null,
          "display": "",
          "how": null
        }
      ]
    }
  ],
  "non_entity_types": [],
  "flows": [],
  "edges": [],
  "deployment": [],
  "observability": [],
  "security": [],
  "config": [],
  "tests_note": "",
  "tests": [],
  "extras": []
}"""
    mm = gen_viewer.gen_domain_mermaid(parse_map(md))
    assert "E2 --|> E1 : isA (inferred)" in mm, mm


def make_context_map(cards: str | None = None, contexts: str | None = None) -> str:
    """A domain map with a Subdomains (SD) table + `SUBDOMAIN:` lines on the cards. Default: two contexts
    (SD1 Ordering, SD2 Catalog); E1/E2 live in SD1, E4 in SD2; E1 contains E2 (intra-context) and
    refersTo E4 (the one CROSS-context relation), so the tests exercise membership + a crossing edge."""
    if cards is not None and contexts is not None:
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
      "name": "Search",
      "actor": "Shopper",
      "trigger_outcome": "types -> list"
    }
  ],
  "happy_path": [
    {
      "id": "HP1",
      "title": "Search",
      "uc": "UC1",
      "why": null
    }
  ],
  "subsystems": [],
  "components": [],
  "deps": [],
  "run_commands": [],
  "entry_points": [],
  "subdomains": [
    {
      "id": "SD1",
      "name": "Ordering",
      "purpose": "x",
      "parent": null,
      "source": "[order.py](order.py#L1)",
      "confidence": "inferred"
    },
    {
      "id": "SD2",
      "name": "Inner",
      "purpose": "x",
      "parent": "SD1",
      "source": "[order.py](order.py#L1)",
      "confidence": "inferred"
    },
    {
      "id": "SD3",
      "name": "Catalog",
      "purpose": "x",
      "parent": null,
      "source": "[product.py](product.py#L1)",
      "confidence": "inferred"
    }
  ],
  "entities": [
    {
      "id": "E1",
      "name": "Order",
      "store": "orders",
      "meaning": "a purchase",
      "subdomain": "SD1",
      "source": "order.py:12",
      "fields": [
        {
          "name": "id",
          "type": "ObjectId",
          "markers": [
            "PK"
          ]
        }
      ],
      "relations": [
        {
          "verb": "contains",
          "target": "E2",
          "src_card": "1",
          "dst_card": "*",
          "display": "LineItem",
          "how": null
        }
      ]
    },
    {
      "id": "E2",
      "name": "LineItem",
      "store": "",
      "meaning": "a line",
      "subdomain": "SD2",
      "source": "order.py:58",
      "fields": [
        {
          "name": "sku",
          "type": "string",
          "markers": []
        },
        {
          "name": "prod",
          "type": "E3",
          "markers": []
        }
      ],
      "relations": [
        {
          "verb": "refersTo",
          "target": "E3",
          "src_card": "*",
          "dst_card": "1",
          "display": "Product",
          "how": null
        }
      ]
    },
    {
      "id": "E3",
      "name": "Product",
      "store": "",
      "meaning": "a product",
      "subdomain": "SD3",
      "source": "product.py:9",
      "fields": [
        {
          "name": "name",
          "type": "string",
          "markers": []
        }
      ],
      "relations": []
    }
  ],
  "non_entity_types": [],
  "flows": [],
  "edges": [],
  "deployment": [],
  "observability": [],
  "security": [],
  "config": [],
  "tests_note": "",
  "tests": [],
  "extras": []
}"""
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
      "name": "Search",
      "actor": "Shopper",
      "trigger_outcome": "types -> list"
    }
  ],
  "happy_path": [
    {
      "id": "HP1",
      "title": "Search",
      "uc": "UC1",
      "why": null
    }
  ],
  "subsystems": [],
  "components": [],
  "deps": [],
  "run_commands": [],
  "entry_points": [],
  "subdomains": [
    {
      "id": "SD1",
      "name": "Ordering",
      "purpose": "purchase lifecycle",
      "parent": null,
      "source": "[order.py](order.py#L1)",
      "confidence": "inferred"
    },
    {
      "id": "SD2",
      "name": "Catalog",
      "purpose": "products",
      "parent": null,
      "source": "[product.py](product.py#L1)",
      "confidence": "inferred"
    }
  ],
  "entities": [
    {
      "id": "E1",
      "name": "Order",
      "store": "orders",
      "meaning": "a purchase",
      "subdomain": "SD1",
      "source": "order.py:12",
      "fields": [
        {
          "name": "id",
          "type": "ObjectId",
          "markers": [
            "PK"
          ]
        },
        {
          "name": "product",
          "type": "E4",
          "markers": []
        }
      ],
      "relations": [
        {
          "verb": "contains",
          "target": "E2",
          "src_card": "1",
          "dst_card": "*",
          "display": "LineItem",
          "how": null
        },
        {
          "verb": "refersTo",
          "target": "E4",
          "src_card": "*",
          "dst_card": "1",
          "display": "Product",
          "how": null
        }
      ]
    },
    {
      "id": "E2",
      "name": "LineItem",
      "store": "",
      "meaning": "a line",
      "subdomain": "SD1",
      "source": "order.py:58",
      "fields": [
        {
          "name": "sku",
          "type": "string",
          "markers": []
        }
      ],
      "relations": []
    },
    {
      "id": "E4",
      "name": "Product",
      "store": "",
      "meaning": "a product",
      "subdomain": "SD2",
      "source": "product.py:9",
      "fields": [
        {
          "name": "name",
          "type": "string",
          "markers": []
        }
      ],
      "relations": []
    }
  ],
  "non_entity_types": [],
  "flows": [],
  "edges": [],
  "deployment": [],
  "observability": [],
  "security": [],
  "config": [],
  "tests_note": "",
  "tests": [],
  "extras": []
}"""


def make_nested_subdomain_map() -> str:
    """SD1 (top) nests SD2; SD3 is a top-level sibling. E1 is a DIRECT entity of SD1, E2 a grandchild
    (in SD2), E3 in SD3. E1 contains E2 (direct entity -> child-subdomain box), E2 refersTo E3
    (grandchild -> sibling subdomain). The domain mirror of make_nested_subsystem_map."""
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
      "name": "Search",
      "actor": "Shopper",
      "trigger_outcome": "types -> list"
    }
  ],
  "happy_path": [
    {
      "id": "HP1",
      "title": "Search",
      "uc": "UC1",
      "why": null
    }
  ],
  "subsystems": [],
  "components": [],
  "deps": [],
  "run_commands": [],
  "entry_points": [],
  "subdomains": [
    {
      "id": "SD1",
      "name": "Ordering",
      "purpose": "x",
      "parent": null,
      "source": "[order.py](order.py#L1)",
      "confidence": "inferred"
    },
    {
      "id": "SD2",
      "name": "Inner",
      "purpose": "x",
      "parent": "SD1",
      "source": "[order.py](order.py#L1)",
      "confidence": "inferred"
    },
    {
      "id": "SD3",
      "name": "Catalog",
      "purpose": "x",
      "parent": null,
      "source": "[product.py](product.py#L1)",
      "confidence": "inferred"
    }
  ],
  "entities": [
    {
      "id": "E1",
      "name": "Order",
      "store": "orders",
      "meaning": "a purchase",
      "subdomain": "SD1",
      "source": "order.py:12",
      "fields": [
        {
          "name": "id",
          "type": "ObjectId",
          "markers": [
            "PK"
          ]
        }
      ],
      "relations": [
        {
          "verb": "contains",
          "target": "E2",
          "src_card": "1",
          "dst_card": "*",
          "display": "LineItem",
          "how": null
        }
      ]
    },
    {
      "id": "E2",
      "name": "LineItem",
      "store": "",
      "meaning": "a line",
      "subdomain": "SD2",
      "source": "order.py:58",
      "fields": [
        {
          "name": "sku",
          "type": "string",
          "markers": []
        },
        {
          "name": "prod",
          "type": "E3",
          "markers": []
        }
      ],
      "relations": [
        {
          "verb": "refersTo",
          "target": "E3",
          "src_card": "*",
          "dst_card": "1",
          "display": "Product",
          "how": null
        }
      ]
    },
    {
      "id": "E3",
      "name": "Product",
      "store": "",
      "meaning": "a product",
      "subdomain": "SD3",
      "source": "product.py:9",
      "fields": [
        {
          "name": "name",
          "type": "string",
          "markers": []
        }
      ],
      "relations": []
    }
  ],
  "non_entity_types": [],
  "flows": [],
  "edges": [],
  "deployment": [],
  "observability": [],
  "security": [],
  "config": [],
  "tests_note": "",
  "tests": [],
  "extras": []
}"""


def test_nested_subdomain_has_card_at_every_level() -> None:
    by_sd = gen_viewer.domain_subdomain_mermaids(parse_map(make_nested_subdomain_map()))
    assert {"SD1", "SD2", "SD3"} <= set(by_sd)   # a card for the NESTED subdomain SD2, not only top-level


def test_nested_subdomain_card_shows_child_box_not_flattened() -> None:
    by_sd = gen_viewer.domain_subdomain_mermaids(parse_map(make_nested_subdomain_map()))
    sd1 = by_sd["SD1"]
    assert "namespace SD1[" in sd1
    assert "E1" in sd1                    # direct entity
    assert "class SD2[" in sd1           # child subdomain as a (drillable) collapsed box
    assert "E2" not in sd1               # grandchild entity NOT flattened into the parent card
    assert "E1 --> SD2" in sd1           # direct entity -> child-subdomain box (aggregated)


def test_nested_subdomain_crossing_resolves_at_card_level() -> None:
    by_sd = gen_viewer.domain_subdomain_mermaids(parse_map(make_nested_subdomain_map()))
    sd1 = by_sd["SD1"]
    assert "SD2 --> SD3" in sd1           # E2(in SD2) -> E3(in SD3) shows as child-box -> sibling box
    sd2 = by_sd["SD2"]
    assert "E2" in sd2 and "E2 --> SD3" in sd2


def test_domain_overview_shows_only_top_level_subdomains() -> None:
    cont = gen_viewer.gen_domain_container_mermaid(parse_map(make_nested_subdomain_map()))
    assert 'SD1["' in cont and 'SD3["' in cont
    assert 'SD2["' not in cont
    assert "SD1 -->|1| SD3" in cont       # nested E2->E3 aggregates to the top SD1->SD3 arrow


def test_nested_domain_edge_cards_for_disjoint_pairs_only() -> None:
    # E1->E2 is parent->child (SD1>SD2 overlap) -> navigated, no card. E2->E3 is disjoint and gets a
    # card at every level it is drawn: SD2>SD3 (nested) and SD1>SD3 (overview / SD1 card).
    cards = gen_viewer.domain_edge_card_mermaids(parse_map(make_nested_subdomain_map()))
    assert "SD1>SD2" not in cards
    assert {"SD2>SD3", "SD1>SD3"} <= set(cards)
    ce = gen_viewer.gen_domain_container_edges(parse_map(make_nested_subdomain_map()))
    assert {"SD2>SD3", "SD1>SD3"} <= set(ce)
    assert {(r["src"], r["dst"]) for r in ce["SD2>SD3"]} == {("E2", "E3")}


def test_parser_entity_gets_context_parent_and_context_nodes() -> None:
    g = parse_map(make_context_map())
    assert g["nodes"]["E1"]["parent"] == "SD1" and g["nodes"]["E4"]["parent"] == "SD2"
    ctx = {k: v for k, v in g["nodes"].items() if v["kind"] == "subdomain"}
    assert set(ctx) == {"SD1", "SD2"} and ctx["SD1"]["name"] == "Ordering"


def test_parser_entity_without_context_has_no_parent() -> None:
    # An ungrouped domain model (no Subdomains table, no CONTEXT line) leaves entities parent-less.
    assert parse_map(make_domain_map())["nodes"]["E1"]["parent"] is None


def make_bridge_map() -> str:
    """Subsystems S1/S2 + context SD1 with entity E1; C1 (S1) persists E1, C2 (S2) reads E1. Exercises
    the S→SD bridge: the owning subsystem's card shows an `owns` arrow, the reader's a `reads` arrow."""
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
  "subsystems": [
    {
      "id": "S1",
      "name": "Edge",
      "purpose": "x",
      "parent": null,
      "source": "a/",
      "confidence": "V"
    },
    {
      "id": "S2",
      "name": "Core",
      "purpose": "x",
      "parent": null,
      "source": "a/",
      "confidence": "V"
    }
  ],
  "components": [
    {
      "id": "C1",
      "name": "Writer",
      "subsystem": "S1",
      "purpose": "x",
      "entry_point": "f",
      "depends_on": "",
      "source": null,
      "confidence": "",
      "extra": {}
    },
    {
      "id": "C2",
      "name": "Reader",
      "subsystem": "S2",
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
  "subdomains": [
    {
      "id": "SD1",
      "name": "Ordering",
      "purpose": "x",
      "parent": null,
      "source": "a/",
      "confidence": "V"
    }
  ],
  "entities": [
    {
      "id": "E1",
      "name": "Order",
      "store": "orders",
      "meaning": "m",
      "subdomain": "SD1",
      "source": "f:1",
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
      "verb": "persists",
      "dst": "E1",
      "why": "store",
      "where": "f"
    },
    {
      "src": "C2",
      "verb": "reads",
      "dst": "E1",
      "why": "load",
      "where": "f"
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


def test_has_subdomains() -> None:
    assert gen_viewer.has_subdomains(parse_map(make_context_map())) is True
    assert gen_viewer.has_subdomains(parse_map(make_domain_map())) is False   # domain model, but ungrouped


def test_gen_domain_container_mermaid_boxes_and_crossing_arrow() -> None:
    # The bounded-contexts overview: one box per context labelled by entity count, with a SDa->SDb
    # arrow DERIVED from a crossing E->E relation (E1 in SD1 refersTo E4 in SD2), labelled by count.
    mm = gen_viewer.gen_domain_container_mermaid(parse_map(make_context_map()))
    assert mm.startswith("flowchart")
    assert 'SD1["Ordering (2)"]' in mm and 'SD2["Catalog (1)"]' in mm   # count = #entities in the context
    assert "class SD1 subdomain" in mm
    assert "SD1 -->|1| SD2" in mm                                       # the one crossing relation


def test_gen_domain_container_edges_list_crossing_relations() -> None:
    ce = gen_viewer.gen_domain_container_edges(parse_map(make_context_map()))
    assert set(ce) == {"SD1>SD2"}                                       # only the crossing direction
    rows = ce["SD1>SD2"]
    assert {(r["src"], r["dst"]) for r in rows} == {("E1", "E4")}
    assert rows[0]["srcName"] == "Order" and rows[0]["dstName"] == "Product" and rows[0]["verb"] == "refersTo"


def test_gen_domain_subdomain_card_frames_members_collapses_neighbour_subdomains() -> None:
    # The neighbourhood card: the focal subdomain framed as a `namespace` holding its own entities FULL,
    # every OTHER subdomain it relates to drawn as ONE collapsed box (not its individual entities), and a
    # cross arrow per (focal entity, neighbour subdomain) pair — the entity analog of the subsystem card.
    cards = gen_viewer.domain_subdomain_mermaids(parse_map(make_context_map()))
    assert set(cards) == {"SD1", "SD2"}
    cx1 = cards["SD1"]
    assert cx1.startswith("classDiagram")
    assert 'namespace SD1["Ordering"] {' in cx1                     # focal subdomain is a labelled frame
    assert 'class E1["Order"] {' in cx1 and "ObjectId id" in cx1        # member entity, FULL box
    assert 'class E2["LineItem"] {' in cx1                              # the other member, full
    assert 'class SD2["Catalog (1)"]' in cx1                            # neighbour drawn as ONE collapsed subdomain box
    assert 'class E4["Product"]' not in cx1                             # the neighbour's entity is NOT drawn (collapsed to SD)
    assert 'E1 "1" *-- "*" E2' in cx1                                   # intra-subdomain composition, full
    assert "E1 --> SD2" in cx1                                          # cross arrow to the collapsed neighbour box
    assert ": product" not in cx1                                       # the crossing is aggregated, not a labelled relation here
    # in SD2's card the roles flip: E4 is the framed member, SD1 the collapsed neighbour, arrow inbound
    cx2 = cards["SD2"]
    assert 'namespace SD2["Catalog"] {' in cx2
    assert 'class E4["Product"] {' in cx2 and 'class E1["Order"] {' not in cx2
    assert 'class SD1["Ordering (2)"]' in cx2 and "SD1 --> E4" in cx2   # inbound cross arrow from the neighbour


def test_gen_domain_edge_card_two_namespaces_with_inner_and_crossing() -> None:
    # The subdomain edge card: BOTH subdomains framed as namespaces with ALL their entities full, each
    # subdomain's inner relations, and the crossing relations drawn IN FULL (kind + backing-field label) —
    # the entity analog of the subsystem edge card. Keyed by the crossing direction only.
    g = parse_map(make_context_map())
    cards = gen_viewer.domain_edge_card_mermaids(g)
    assert set(cards) == {"SD1>SD2"}                                   # only the crossing direction (E1 → E4)
    card = cards["SD1>SD2"]
    assert card.startswith("classDiagram")
    assert 'namespace SD1["Ordering"] {' in card and 'namespace SD2["Catalog"] {' in card
    assert 'class E1["Order"] {' in card and 'class E2["LineItem"] {' in card and 'class E4["Product"] {' in card
    assert 'E1 "1" *-- "*" E2' in card                                 # SD1's inner wiring
    assert 'E1 "*" --> "1" E4 : product' in card                       # the crossing relation, drawn in full


def test_subsystem_card_bridges_to_contexts_owns_and_reads() -> None:
    by_sub = gen_viewer.subsystem_component_mermaids(parse_map(make_bridge_map()))
    s1 = by_sub["S1"]
    # The owns/reads split is VERB-DERIVED (persists/writes -> owns), so the label carries the
    # inferred mark — the bridge is presented as a derivation, never asserted (verbs never gate).
    # QUOTED: bare parens are a shape token in a flowchart edge label and fail the Mermaid parse.
    assert "class SD1 subdomain" in s1 and 'C1 -->|"owns (inferred)"| SD1' in s1   # persists -> OWNS (inferred)
    s2 = by_sub["S2"]
    assert "class SD1 subdomain" in s2 and 'C2 -->|"reads (inferred)"| SD1' in s2  # reads -> CONSUMES (inferred)


def test_subdomain_card_bridges_to_subsystems_owns_and_reads() -> None:
    # The reverse of test_subsystem_card_bridges_to_contexts: a subdomain card draws every subsystem
    # whose components own/read its entities as a collapsed (amber) box with an owns/reads arrow INTO
    # the entity — the structure↔domain bridge seen from the domain side.
    sd1 = gen_viewer.domain_subdomain_mermaids(parse_map(make_bridge_map()))["SD1"]
    assert 'namespace SD1[' in sd1 and 'class E1["Order"] {' in sd1
    assert 'class S1["Edge"]' in sd1 and "S1 --> E1 : owns (inferred)" in sd1    # writer OWNS (verb-derived)
    assert 'class S2["Core"]' in sd1 and "S2 --> E1 : reads (inferred)" in sd1   # reader READS (verb-derived)
    assert "style S1 fill:" in sd1                                        # subsystem box styled (amber), distinct from entities


def test_subdomain_card_has_no_subsystem_box_without_bridges() -> None:
    # Regression mirror: a pure domain map (no C->E edges, no subsystems) draws no subsystem box / amber
    # styling in the subdomain card. (Neighbour SUBDOMAIN boxes are still drawn + styled magenta.)
    sd1 = gen_viewer.domain_subdomain_mermaids(parse_map(make_context_map()))["SD1"]
    assert "class S1" not in sd1
    assert gen_viewer.SUBSYSTEM_STYLE not in sd1                # no amber (subsystem) styling
    assert f"style SD2 {gen_viewer.SUBDOMAIN_STYLE}" in sd1     # neighbour subdomain IS styled magenta


def test_subsystem_card_has_no_context_box_without_bridges() -> None:
    # Regression: a map with no C->E edges draws no subdomain box / classDef in the subsystem card.
    s1 = gen_viewer.subsystem_component_mermaids(parse_map(make_card_map()))["S1"]
    assert "subdomain" not in s1


def test_bundle_carries_context_data() -> None:
    # The bundle carries the contexts overview + per-context cards, with hasSubdomains on so the Domain
    # view leads with the overview.
    b = bundle_of(make_context_map())
    assert b["hasSubdomains"] is True
    assert "Ordering (2)" in b["mermaidDomainContainer"]   # the bounded-contexts overview
    assert "SD1>SD2" in b["mermaidDomainEdgeCard"]          # the subdomain edge-card (keyed by crossing pair)


def test_bundle_no_context_data_when_ungrouped() -> None:
    # A domain map with no Subdomains table: hasSubdomains is false and the flat classDiagram still ships.
    b = bundle_of(make_domain_map())
    assert b["hasSubdomains"] is False and b["mermaidDomain"]


def _two_context_map(cards_extra: str = "") -> str:
    """SD1 (Ordering, has E1) + SD2 (Catalog, EMPTY — no card assigned to it). `cards_extra` is unused
    by the surviving (kept) callers, which all take the default — a defined-but-empty SD2."""
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
      "name": "Search",
      "actor": "Shopper",
      "trigger_outcome": "types -> list"
    }
  ],
  "happy_path": [
    {
      "id": "HP1",
      "title": "Search",
      "uc": "UC1",
      "why": null
    }
  ],
  "subsystems": [],
  "components": [],
  "deps": [],
  "run_commands": [],
  "entry_points": [],
  "subdomains": [
    {
      "id": "SD1",
      "name": "Ordering",
      "purpose": "x",
      "parent": null,
      "source": "a/",
      "confidence": "V"
    },
    {
      "id": "SD2",
      "name": "Catalog",
      "purpose": "x",
      "parent": null,
      "source": "a/",
      "confidence": "V"
    }
  ],
  "entities": [
    {
      "id": "E1",
      "name": "Order",
      "store": "s",
      "meaning": "m",
      "subdomain": "SD1",
      "source": "f:1",
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
  "edges": [],
  "deployment": [],
  "observability": [],
  "security": [],
  "config": [],
  "tests_note": "",
  "tests": [],
  "extras": []
}"""


def test_gen_domain_subdomain_card_empty_context_is_valid_mermaid() -> None:
    # A defined-but-empty context must still produce a VALID classDiagram — a body-less `classDiagram`
    # crashes Mermaid on drill (the F1 regression). It carries a self-explaining placeholder instead.
    card = gen_viewer.gen_domain_subdomain_card(parse_map(_two_context_map()), "SD2")
    assert card.startswith("classDiagram") and card.strip() != "classDiagram"   # has a body
    assert "no entities" in card and "Catalog" in card
    # the placeholder id carries no prefix+digits, so the viewer's id bridge skips it (not clickable)
    assert "EmptySubdomain" in card


def make_both_groupings_map() -> str:
    """A map with BOTH groupings + the cross-altitude edges that triggered the leak: S1{C1}, S2{C2};
    SD1{E1,E2}, SD2{E3}; a C1->C2 component edge (S→S crossing), C1 persists E1 + C2 persists E3
    (C→E bridge edges), and E1 refersTo E3 (an E→E relation crossing SD1→SD2). The Subsystems overview
    must show ONLY S→S and never a SD box; the Domain overview ONLY SD→SD and never an S box."""
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
  "subsystems": [
    {
      "id": "S1",
      "name": "Edge",
      "purpose": "x",
      "parent": null,
      "source": "a/",
      "confidence": "V"
    },
    {
      "id": "S2",
      "name": "Core",
      "purpose": "x",
      "parent": null,
      "source": "a/",
      "confidence": "V"
    }
  ],
  "components": [
    {
      "id": "C1",
      "name": "Front",
      "subsystem": "S1",
      "purpose": "x",
      "entry_point": "f",
      "depends_on": "C2",
      "source": null,
      "confidence": "",
      "extra": {}
    },
    {
      "id": "C2",
      "name": "Core",
      "subsystem": "S2",
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
  "subdomains": [
    {
      "id": "SD1",
      "name": "Ordering",
      "purpose": "x",
      "parent": null,
      "source": "a/",
      "confidence": "V"
    },
    {
      "id": "SD2",
      "name": "Catalog",
      "purpose": "x",
      "parent": null,
      "source": "a/",
      "confidence": "V"
    }
  ],
  "entities": [
    {
      "id": "E1",
      "name": "Order",
      "store": "s",
      "meaning": "m",
      "subdomain": "SD1",
      "source": "f:1",
      "fields": [
        {
          "name": "id",
          "type": "int",
          "markers": []
        },
        {
          "name": "product",
          "type": "E3",
          "markers": []
        }
      ],
      "relations": [
        {
          "verb": "contains",
          "target": "E2",
          "src_card": "1",
          "dst_card": "*",
          "display": "Line",
          "how": null
        },
        {
          "verb": "refersTo",
          "target": "E3",
          "src_card": "*",
          "dst_card": "1",
          "display": "Product",
          "how": null
        }
      ]
    },
    {
      "id": "E2",
      "name": "Line",
      "store": "",
      "meaning": "m",
      "subdomain": "SD1",
      "source": "f:2",
      "fields": [
        {
          "name": "x",
          "type": "int",
          "markers": []
        }
      ],
      "relations": []
    },
    {
      "id": "E3",
      "name": "Product",
      "store": "",
      "meaning": "m",
      "subdomain": "SD2",
      "source": "f:3",
      "fields": [
        {
          "name": "y",
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
      "verb": "calls",
      "dst": "C2",
      "why": "reach core",
      "where": "f"
    },
    {
      "src": "C1",
      "verb": "persists",
      "dst": "E1",
      "why": "store order",
      "where": "f"
    },
    {
      "src": "C2",
      "verb": "persists",
      "dst": "E3",
      "why": "store product",
      "where": "f"
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


def test_container_overview_excludes_contexts() -> None:
    # The bug class: with C→E / E→E edges present, the Subsystems overview must NOT pick up entity
    # endpoints (whose top group is a CONTEXT) and invent S→SD / SD→SD arrows that draw bare SD boxes.
    g = parse_map(make_both_groupings_map())
    mm = gen_viewer.gen_container_mermaid(g)
    assert "SD" not in mm                                  # no subdomain box / arrow leaks in
    assert "S1 -->|1| S2" in mm                            # the real S→S crossing (C1->C2), count 1 (not inflated by C→E)
    # the Domain overview is the mirror: contexts only, no subsystem leak
    dmm = gen_viewer.gen_domain_container_mermaid(g)
    assert "SD1 -->|1| SD2" in dmm and "S1" not in dmm and "S2" not in dmm  # SD→SD present, no subsystem box leaks in


def test_container_edges_exclude_contexts() -> None:
    ce = gen_viewer.gen_container_edges(parse_map(make_both_groupings_map()))
    assert set(ce) == {"S1>S2"}                            # only the real subsystem pair, no S>SD keys


def test_edge_cards_exclude_contexts() -> None:
    cards = gen_viewer.edge_card_mermaids(parse_map(make_both_groupings_map()))
    assert set(cards) == {"S1>S2"}                         # no spurious S>SD edge card


def test_domain_edge_card_includes_subsystem_bridges() -> None:
    # The domain edge card draws the reverse structure↔domain bridge too: each subsystem whose
    # components own/read either subdomain's entities, as a collapsed (amber) box with an owns/reads
    # arrow (C1 persists E1 -> S1 owns E1; C2 persists E3 -> S2 owns E3). Mirrors the subdomain card.
    card = gen_viewer.domain_edge_card_mermaids(parse_map(make_both_groupings_map()))["SD1>SD2"]
    assert 'namespace SD1[' in card and 'namespace SD2[' in card
    assert 'class S1["Edge"]' in card and "S1 --> E1 : owns (inferred)" in card
    assert 'class S2["Core"]' in card and "S2 --> E3 : owns (inferred)" in card
    assert "style S1 fill:" in card                        # amber subsystem box, distinct from entities


def test_bridge_card_pairs_subsystem_and_subdomain() -> None:
    # The bridge card frames a subsystem and a subdomain side by side, with the component→entity
    # owns/reads edges between them — the structure↔domain analog of the edge cards. Keyed 'S>SD'.
    cards = gen_viewer.bridge_card_mermaids(parse_map(make_both_groupings_map()))
    assert "S1>SD1" in cards and "S2>SD2" in cards
    card = cards["S1>SD1"]
    assert card.startswith("classDiagram")
    assert 'namespace S1["Edge"] {' in card and 'class C1["Front"]' in card    # subsystem frame + its component box
    assert 'namespace SD1[' in card and 'class E1["Order"] {' in card          # subdomain frame + entity (full, attrs)
    assert "C1 --> E1 : owns (inferred)" in card                               # the C→E bridge edge (verb-derived)
    assert "style C1 fill:" in card                                            # component box styled (indigo)


def test_parser_hp_captures_uc_and_why() -> None:
    g = parse_map(make_gp_map())
    steps = {s["id"]: s for s in g["happy_path"]}
    assert steps["HP1"]["uc"] == "UC1" and steps["HP2"]["uc"] == "UC2"
    assert steps["HP1"]["why"] == "" and steps["HP2"]["why"] == "needs the order from HP1"
    assert "touches" not in steps["HP1"]  # the step no longer carries its own touches/story


def test_parser_captures_use_case_flows() -> None:
    g = parse_map(make_gp_map())
    flows = {cast(str, f["uc"]): f for f in g["flows"]}
    assert set(flows) == {"UC1", "UC2"}
    s1 = cast("list[dict[str, object]]", flows["UC1"]["steps"])
    assert s1[0]["src"] == "Andy" and not s1[0]["src_is_id"] and s1[0]["phrase"] == "submits the order"
    assert s1[1]["src"] == "C1" and s1[1]["dst"] == "C2" and s1[1]["src_is_id"] and s1[1]["dst_is_id"]
    assert all(st["ok"] for st in s1)


def test_gen_hp_mermaid_black_box_sequence() -> None:
    # Level 1: a sequenceDiagram whose lifelines are the actors derived from each step's UC, with one
    # message per step. The label is the step TITLE only — no `HPn` id (the viewer pairs by order).
    mm = gen_viewer.gen_hp_mermaid(parse_map(make_gp_map()))
    assert mm.startswith("sequenceDiagram")
    assert "actor HPA0 as Andy" in mm and "actor HPA1 as Adam" in mm  # one lifeline per distinct actor
    assert "participant HPSYS" in mm
    assert "HPA0->>HPSYS: 1. Submit order" in mm
    assert "HPA1->>HPSYS: 2. Approve order" in mm
    assert "HP1" not in mm and "HP2" not in mm  # step ids no longer leak into the message labels


def test_gen_hp_mermaid_actor_fallback_without_uc() -> None:
    # A GP step with no `*(UCn)*` tag falls back to a generic 'Actor' lifeline (no crash).
    md = """{
  "format": "coyodex-map",
  "title": "",
  "goal": "",
  "commit": null,
  "committed": null,
  "built": null,
  "roles": [],
  "glossary": [],
  "use_cases": [],
  "happy_path": [
    {
      "id": "HP1",
      "title": "Do a thing",
      "uc": null,
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
  "flows": [],
  "edges": [],
  "deployment": [],
  "observability": [],
  "security": [],
  "config": [],
  "tests_note": "",
  "tests": [],
  "extras": []
}"""
    mm = gen_viewer.gen_hp_mermaid(parse_map(md))
    assert "actor HPA0 as Actor" in mm and "HPA0->>HPSYS: 1. Do a thing" in mm


def test_hp_actors_links_roles_and_steps() -> None:
    # hp_actors mirrors the diagram's participant order/ids and joins each actor to its Roles-table
    # entry (wants + kind) and the steps it drives (stepIdx = the message positions to highlight).
    g = parse_map(make_gp_role_actor_map())
    actors = gen_viewer.hp_actors(g)
    assert len(actors) == 1
    a = actors[0]
    assert a["aid"] == "HPA0" and a["name"] == "Org admin"
    assert a["kind"] == "human" and a["wants"] == "manage"   # joined from the Roles table by name
    assert a["stepIdx"] == [0]
    assert a["steps"] == [{"id": "HP1", "title": "Admin creates the org"}]


def test_hp_actors_without_matching_role_has_blank_wants() -> None:
    # An actor derived from a UC with no matching Roles row still appears, just without wants/kind;
    # ids follow first-appearance order and stepIdx points at each actor's messages.
    actors = gen_viewer.hp_actors(parse_map(make_gp_map()))
    by_name = {a["name"]: a for a in actors}
    assert by_name["Andy"]["aid"] == "HPA0" and by_name["Adam"]["aid"] == "HPA1"
    assert by_name["Andy"]["wants"] == "" and by_name["Andy"]["kind"] == ""
    assert by_name["Andy"]["stepIdx"] == [0] and by_name["Adam"]["stepIdx"] == [1]


def test_parser_hp_captures_first_uc_of_multi_tag() -> None:
    # A step tagged with several UCs (`*(UC1, UC2)*`) or trailing text (`*(UC3 follow-on)*`) must
    # resolve to its FIRST UC — not fall back to a generic 'Actor' lifeline (the multi-UC regression).
    md = """{
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
      "actor": "Org admin",
      "trigger_outcome": "a -> b"
    },
    {
      "id": "UC2",
      "name": "Create",
      "actor": "Org admin",
      "trigger_outcome": "a -> b"
    },
    {
      "id": "UC3",
      "name": "Renew",
      "actor": "End user",
      "trigger_outcome": "a -> b"
    }
  ],
  "happy_path": [
    {
      "id": "HP1",
      "title": "Sign in and create",
      "uc": "UC1",
      "why": null
    },
    {
      "id": "HP2",
      "title": "Renewal flow",
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
  "edges": [],
  "deployment": [],
  "observability": [],
  "security": [],
  "config": [],
  "tests_note": "",
  "tests": [],
  "extras": []
}"""
    g = parse_map(md)
    steps = {s["id"]: s for s in g["happy_path"]}
    assert steps["HP1"]["uc"] == "UC1"           # first id of the multi-UC tag
    assert steps["HP2"]["uc"] == "UC3"           # trailing text after the id is ignored
    mm = gen_viewer.gen_hp_mermaid(g)
    assert "actor HPA0 as Org admin" in mm and "actor HPA1 as End user" in mm  # real actors...
    assert "as Actor" not in mm                  # ...not the generic fallback


def test_hp_actor_is_use_case_actor() -> None:
    # A step IS one use case, so its driving actor is that use case's Actor cell (no separate signal).
    g = parse_map(make_gp_role_actor_map())
    assert gen_viewer._hp_actor(g, g["happy_path"][0]) == "Org admin"


def test_flow_mermaid_sequence_from_use_case() -> None:
    # A use case's flow renders as a sequenceDiagram: the actor + the touched elements as lifelines,
    # each step a message whose label is the step's own authored phrase. (make_gp_map's element steps
    # leave the phrase empty, so they exercise the legacy backstop: the edge's descriptive Why.)
    mm = gen_viewer.flow_mermaids(parse_map(make_gp_map()))
    s1 = mm["UC1"]
    assert s1.startswith("sequenceDiagram")
    assert "actor FA0 as Andy" in s1                      # the actor lifeline
    assert "participant C1 as Gateway" in s1 and "participant C2 as Engine" in s1
    # Each arrow is prefixed with its 1-based step number (aligns with the panel narrative + step player).
    assert "FA0->>C1: 1. submits the order" in s1        # step with a phrase -> the authored phrase
    assert "C1->>C2: 2. reach engine" in s1              # phrase-less step -> the edge's Why (backstop)
    s2 = mm["UC2"]
    assert "C2->>D1: 2. cache" in s2


def test_flow_element_step_phrase_wins_on_arrow() -> None:
    # An element↔element step carries its OWN action text now; the arrow shows that phrase, not the
    # shared backbone edge's label (a pair used by several steps can't be described by one edge label).
    md = make_gp_map().replace(
        '"src": "C1",\n          "dst": "C2",\n          "phrase": "",',
        '"src": "C1",\n          "dst": "C2",\n          "phrase": "hands the order to the engine",')
    s1 = gen_viewer.flow_mermaids(parse_map(md))["UC1"]
    assert "C1->>C2: 2. hands the order to the engine" in s1   # the step's own phrase
    assert "reach engine" not in s1                            # not the shared edge Why
    step2 = next(s for s in gen_viewer.flow_narratives(parse_map(md))["UC1"] if s["n"] == 2)
    assert step2["verb"] == "hands the order to the engine" and step2["why"] == ""


def test_flow_narrative_backstop_derives_from_edge() -> None:
    # Legacy backstop only: a phrase-less element step falls back to the backbone edge (verb + why).
    narr = gen_viewer.flow_narratives(parse_map(make_gp_map()))["UC1"]
    step2 = next(s for s in narr if s["n"] == 2)
    assert step2["srcId"] == "C1" and step2["dstId"] == "C2"
    assert step2["verb"] == "calls" and step2["why"] == "reach engine"


def test_flow_arrow_backstop_prefers_why_over_verb() -> None:
    # Backstop for a phrase-less step: the arrow shows the edge's descriptive Why, never the terse verb —
    # for a sharp verb (reads) just as for the catch-all (uses). The step's own phrase is the normal path.
    s2 = gen_viewer.flow_mermaids(parse_map(make_gp_map()))["UC2"]
    assert "C2->>D1: 2. cache" in s2          # sharp verb 'reads' -> still the Why on the arrow
    assert "C2->>D1: 2. reads" not in s2      # the verb never shows when a Why exists


def test_bundle_carries_gp_data() -> None:
    # The bundle carries the GP sequence + step diagrams so the client opens them.
    b = bundle_of(make_gp_map())
    hay = b["mermaidHp"] + " ".join(b["flowsMm"].values())
    assert "sequenceDiagram" in hay and "Submit order" in hay


def make_dep_kinds_map(kind_d1: str = "datastore", with_kind: bool = True) -> str:
    """A map whose T2 exercises dep Kinds: D1 is explicit (param), the rest inferred from Type. D3
    (library) + D4 (framework) are the in-process deps that fold into the Context 'Libraries' box; the
    others are external systems drawn by name. Every kept test uses the default explicit-D1 +
    Kind-column shape (the invalid-Kind and Kind-column-optional variants only served the retired
    validator tests)."""
    return """{
  "format": "coyodex-map",
  "title": "",
  "goal": "",
  "commit": null,
  "committed": null,
  "built": null,
  "roles": [
    {
      "name": "User",
      "kind": "human",
      "wants": "use it",
      "drives": "UC1"
    }
  ],
  "glossary": [],
  "use_cases": [
    {
      "id": "UC1",
      "name": "Use",
      "actor": "User",
      "trigger_outcome": "a -> b"
    }
  ],
  "happy_path": [],
  "subsystems": [],
  "components": [
    {
      "id": "C1",
      "name": "App",
      "subsystem": null,
      "purpose": "x",
      "entry_point": "f",
      "depends_on": "D1",
      "source": null,
      "confidence": "",
      "extra": {}
    }
  ],
  "deps": [
    {
      "id": "D1",
      "name": "PostgreSQL",
      "kind": "datastore",
      "type": "Relational database",
      "used_for": "store",
      "where_configured": "env",
      "confidence": "V",
      "deployment_linked": false,
      "extra": {}
    },
    {
      "id": "D2",
      "name": "RabbitMQ",
      "kind": null,
      "type": "Message broker",
      "used_for": "queue",
      "where_configured": "env",
      "confidence": "V",
      "deployment_linked": false,
      "extra": {}
    },
    {
      "id": "D3",
      "name": "pydantic",
      "kind": null,
      "type": "Validation library",
      "used_for": "validate",
      "where_configured": "dep",
      "confidence": "V",
      "deployment_linked": false,
      "extra": {}
    },
    {
      "id": "D4",
      "name": "React",
      "kind": null,
      "type": "UI framework",
      "used_for": "ui",
      "where_configured": "dep",
      "confidence": "V",
      "deployment_linked": false,
      "extra": {}
    },
    {
      "id": "D5",
      "name": "Stripe",
      "kind": null,
      "type": "Payments API (SaaS)",
      "used_for": "billing",
      "where_configured": "env",
      "confidence": "V",
      "deployment_linked": false,
      "extra": {}
    },
    {
      "id": "D7",
      "name": "Docker",
      "kind": null,
      "type": "Container runtime",
      "used_for": "packaging",
      "where_configured": "dockerfile",
      "confidence": "V",
      "deployment_linked": false,
      "extra": {}
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
      "verb": "uses",
      "dst": "D1",
      "why": "x",
      "where": "f"
    },
    {
      "src": "C1",
      "verb": "uses",
      "dst": "D2",
      "why": "x",
      "where": "f"
    },
    {
      "src": "C1",
      "verb": "uses",
      "dst": "D3",
      "why": "x",
      "where": "f"
    },
    {
      "src": "C1",
      "verb": "uses",
      "dst": "D4",
      "why": "x",
      "where": "f"
    },
    {
      "src": "C1",
      "verb": "uses",
      "dst": "D5",
      "why": "x",
      "where": "f"
    },
    {
      "src": "C1",
      "verb": "uses",
      "dst": "D7",
      "why": "x",
      "where": "f"
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


def test_classify_dep_explicit_wins() -> None:
    # A valid explicit Kind cell overrides whatever the Type text would infer (case/space-insensitive).
    assert grammar.classify_dep("platform", "Relational database") == "platform"
    assert grammar.classify_dep("  Service  ", "a plain library") == "service"


def test_classify_dep_heuristic_per_kind() -> None:
    assert grammar.classify_dep("", "Relational database") == "datastore"
    assert grammar.classify_dep("", "Redis cache") == "datastore"
    assert grammar.classify_dep("", "Message broker") == "messaging"
    assert grammar.classify_dep("", "AWS SQS") == "messaging"          # distinctive beats platform 'aws'
    assert grammar.classify_dep("", "Payments API (SaaS)") == "service"
    assert grammar.classify_dep("", "Observability SaaS") == "service"
    assert grammar.classify_dep("", "Container runtime") == "platform"
    assert grammar.classify_dep("", "UI framework") == "framework"


def test_classify_dep_falls_back_to_library() -> None:
    # An unrecognised Type — and an INVALID explicit Kind — both fall back to 'library' (folds at Context).
    assert grammar.classify_dep("", "some helper utility") == "library"
    assert grammar.classify_dep("db", "totally unknown thing") == "library"


def test_parser_sets_dep_kind() -> None:
    g = parse_map(make_dep_kinds_map())
    deps = {k: v for k, v in g["nodes"].items() if v["kind"] == "dep"}
    assert deps["D1"]["dep_kind"] == "datastore"   # explicit
    assert deps["D2"]["dep_kind"] == "messaging"   # inferred
    assert deps["D3"]["dep_kind"] == "library"     # inferred -> folds
    assert deps["D4"]["dep_kind"] == "framework"   # inferred -> folds


def test_folded_libs_are_in_process_kinds_only() -> None:
    libs = gen_viewer.folded_libs(parse_map(make_dep_kinds_map()))
    assert {d["id"] for d in libs} == {"D3", "D4"}             # framework + library only
    assert {d["name"] for d in libs} == {"pydantic", "React"}


def test_context_folds_libraries_shows_systems_by_name() -> None:
    # The Context view draws external SYSTEMS by name and collapses framework/library into one box.
    mm = gen_viewer.gen_context_mermaid(parse_map(make_dep_kinds_map()))
    for ext in ("PostgreSQL", "RabbitMQ", "Stripe", "Docker"):
        assert ext in mm, ext                                 # external systems shown by name
    assert "Libraries (2)" in mm                              # the two in-process deps fold into one box
    assert "pydantic" not in mm and "React" not in mm         # ...and are NOT drawn individually
    assert "SYS -->|bundles| LIBS" in mm                      # the System bundles the fold box


def test_libs_drill_lists_folded_deps() -> None:
    mm = gen_viewer.gen_libs_mermaid(parse_map(make_dep_kinds_map()))
    assert "pydantic" in mm and "React" in mm                 # the drill-down lists every folded dep
    assert "PostgreSQL" not in mm                             # external systems are not in the Libraries view


def test_context_no_libraries_box_when_none_folded() -> None:
    # All-external deps: no fold box drawn, and the Libraries drill diagram is empty (never reached).
    md = make_dep_kinds_map().replace("Validation library", "Search index").replace("UI framework", "Object storage")
    g = parse_map(md)
    assert gen_viewer.folded_libs(g) == []
    assert "Libraries" not in gen_viewer.gen_context_mermaid(g)
    assert gen_viewer.gen_libs_mermaid(g) == ""


def test_bundle_carries_libs_fold_data() -> None:
    # The bundle carries the Libraries drill diagram + the folded-dep list, so the client can
    # preview/drill the Context fold box.
    b = bundle_of(make_dep_kinds_map())
    folded_names = [x.get("name", "") for x in b["foldedLibs"]]
    assert "pydantic" in b["mermaidLibs"] or "pydantic" in folded_names
    assert "Libraries (2)" in b["mermaidContext"]   # the fold box label in the Context diagram
if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"ok   {fn.__name__}")
        except Exception as e:  # noqa: BLE001 — test runner reports every failure
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
