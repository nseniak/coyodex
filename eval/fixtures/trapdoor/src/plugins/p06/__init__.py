"""The Pager rota plugin. One of eight identically-shaped plugin dirs (trap G4).

Eight same-kind siblings sharing a directory read fine as one dense list — the
homogeneous-family exemption to the 5+-2 fan-out band. Splitting them into artificial
sub-groups to hit a number is the wrong answer.
"""
from src.plugins.p06.handler import PagerHandler

PLUGIN_ID = "pager"
CHANNEL = "notify.pager"

__all__ = ["PagerHandler", "PLUGIN_ID", "CHANNEL"]
