"""The Outbound webhook plugin. One of eight identically-shaped plugin dirs (trap G4).

Eight same-kind siblings sharing a directory read fine as one dense list — the
homogeneous-family exemption to the 5+-2 fan-out band. Splitting them into artificial
sub-groups to hit a number is the wrong answer.
"""
from src.plugins.p05.handler import WebhookHandler

PLUGIN_ID = "webhook"
CHANNEL = "notify.webhook"

__all__ = ["WebhookHandler", "PLUGIN_ID", "CHANNEL"]
