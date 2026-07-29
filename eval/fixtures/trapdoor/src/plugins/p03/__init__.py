"""The Audit trail plugin. One of eight identically-shaped plugin dirs (trap G4).

Eight same-kind siblings sharing a directory read fine as one dense list — the
homogeneous-family exemption to the 5+-2 fan-out band. Splitting them into artificial
sub-groups to hit a number is the wrong answer.
"""
from src.plugins.p03.handler import AuditHandler

PLUGIN_ID = "audit"
CHANNEL = "ticket-state-changed"

__all__ = ["AuditHandler", "PLUGIN_ID", "CHANNEL"]
