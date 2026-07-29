"""The Microsoft Teams plugin. One of eight identically-shaped plugin dirs (trap G4).

Eight same-kind siblings sharing a directory read fine as one dense list — the
homogeneous-family exemption to the 5+-2 fan-out band. Splitting them into artificial
sub-groups to hit a number is the wrong answer.
"""
from src.plugins.p02.handler import TeamsHandler

PLUGIN_ID = "teams"
CHANNEL = "notify.teams"

__all__ = ["TeamsHandler", "PLUGIN_ID", "CHANNEL"]
