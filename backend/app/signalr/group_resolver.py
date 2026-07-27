"""GroupResolver — maps JWT user claims to Azure SignalR group names.

US-022 Group naming convention (DoD):
  - encounter-{encounter_id}   : events for a specific encounter
  - unit-{unit_id}             : events for all encounters in a unit
  - role-{role_name}           : events for a specific clinical role

A user is added to ALL groups they are entitled to at negotiate time.
The broadcaster (TASK-001) sends to all three groups per event;
Azure SignalR delivers only to the intersection of what the client joined.

No PHI is embedded in group names — only opaque IDs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence


@dataclass(frozen=True)
class UserClaims:
    """Subset of JWT claims relevant to SignalR group assignment.

    Populated from the validated JWT payload by the negotiate endpoint.
    """

    user_id: str
    role: str                        # e.g. "nurse", "pharmacist", "physician"
    unit_id: str | None              # e.g. "3A" — None for non-unit-bound roles
    encounter_ids: list[str] = field(default_factory=list)  # active encounter IDs


class GroupResolver:
    """Pure function wrapper: resolves group names from user claims.

    Stateless — safe to instantiate once and reuse across requests.
    """

    def resolve(self, claims: UserClaims) -> list[str]:
        """Return the list of SignalR group names for the given user.

        Rules (US-022 Scenario 2):
          1. Always join role group.
          2. Join unit group if unit_id is present.
          3. Join one encounter group per active encounter_id.

        Order is deterministic for testability.
        """
        groups: list[str] = []

        # Role group — every authenticated user belongs to their role group.
        groups.append(f"role-{claims.role}")

        # Unit group — unit-bound staff (nurses, charge nurses, bed managers).
        if claims.unit_id:
            groups.append(f"unit-{claims.unit_id}")

        # Per-encounter groups — subscribes to specific active encounters.
        for enc_id in sorted(claims.encounter_ids):
            groups.append(f"encounter-{enc_id}")

        return groups
