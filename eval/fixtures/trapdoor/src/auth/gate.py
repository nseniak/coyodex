"""Request authorisation for the ticket API.

TRAP A1 — the enforcing statement sits far below the `def` header. A map that anchors
`security[].source` (or an `enforces` edge `where`) at the header is drifted: the header
cannot act. `validate --check-sources` / `anchor-drift` (shape-only) must flag it.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.lifecycle.states import TicketState


class AuthError(Exception):
    """Raised when a caller may not perform the requested operation."""


@dataclass(frozen=True)
class Principal:
    """Who is asking. `scopes` is the flat permission list carried on the session."""

    subject: str
    scopes: tuple[str, ...]
    tenant: str


# The scope every write path demands. Kept as a module constant so the enforcing line below
# reads as one statement rather than an inline literal.
WRITE_SCOPE = "tickets:write"
ADMIN_SCOPE = "tickets:admin"
CLOSED_STATES = (TicketState.RESOLVED, TicketState.ARCHIVED)


def require_write(principal: Principal, tenant: str, state: TicketState) -> None:
    # Everything between this header and the `raise` below is preparation, not enforcement.
    # An anchor on the `def` line above (line 34) is the classic drift: it describes where the
    # check LIVES, not where it FIRES. The operative statement is the `raise` at the bottom.
    #
    # The preparation deliberately runs long so header-anchoring and operative-line anchoring
    # are far apart and a tolerance window cannot accidentally close the gap.
    if not principal.subject:
        # An anonymous principal never reaches the scope test; it is rejected as malformed
        # input rather than as an authorisation failure, so it is not the enforcement point.
        raise ValueError("principal has no subject")

    scopes = set(principal.scopes)
    if ADMIN_SCOPE in scopes:
        # Admins bypass the tenant and state gates entirely. This early return is a bypass,
        # not an enforcement — anchoring here would claim the check happens for admins.
        return

    same_tenant = principal.tenant == tenant
    state_allows_write = state not in CLOSED_STATES

    # A trace agent reading only the top of the function sees the scope constant and stops.
    # The decision is not made until the composed predicate below.
    has_scope = WRITE_SCOPE in scopes

    permitted = has_scope and same_tenant and state_allows_write

    if not permitted:
        raise AuthError(
            f"{principal.subject} may not write tickets in {tenant} while {state.value}"
        )


def require_read(principal: Principal, tenant: str) -> None:
    """Read access is tenant-scoped only. The enforcing line here IS close to the header,
    so a map anchoring this one at its `raise` is correct and must NOT be flagged — the
    fixture needs a negative control as well as a trap."""
    if principal.tenant != tenant:
        raise AuthError(f"{principal.subject} may not read {tenant}")
