"""The Cold archive plugin. One of eight identically-shaped plugin dirs (trap G4).

Eight same-kind siblings sharing a directory read fine as one dense list — the
homogeneous-family exemption to the 5+-2 fan-out band. Splitting them into artificial
sub-groups to hit a number is the wrong answer.
"""
from src.plugins.p08.handler import ArchiveHandler

PLUGIN_ID = "archive"
CHANNEL = "notify.archive"

__all__ = ["ArchiveHandler", "PLUGIN_ID", "CHANNEL"]
