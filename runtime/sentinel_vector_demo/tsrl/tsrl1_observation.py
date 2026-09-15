"""
TSRL-1 Observation Layer
Stability Engine v4.0

Defines boundaries and obligations for continuous state monitoring.
Ensures evidence is captured WITHOUT goal inference or interpretation.
Guarantees: visibility and auditability.

Constraints enforced here:
- Raw state is recorded as-is; no interpretation, no inference, no labelling of intent.
- Every observation carries a cryptographic hash for tamper-evidence.
- Ambiguity detection is purely structural (missing/contradictory keys) — never semantic.
"""

from __future__ import annotations

import hashlib
import time
from typing import Optional

from core.types import ComponentID, _trace_id, _timestamp, _payload_hash


class TSRL1Observation:
    """
    Boundary-enforcing observation layer.

    Responsibilities
    ----------------
    - Capture raw component states without goal inference.
    - Maintain an append-only observation log for auditability.
    - Detect *structural* ambiguity in observation data (missing or self-
      contradictory fields) — never semantic ambiguity.

    What this layer must NOT do
    ---------------------------
    - Interpret *why* a state changed.
    - Infer agent intent.
    - Aggregate, compress, or summarise state data.
    - Write to any memory tier beyond its own in-process log.
    """

    def __init__(self) -> None:
        # Append-only evidence and observation log — never mutated after appending
        self.observation_log: list[dict] = []
        # Latest snapshot per component_id (string key for serialisability)
        self.state_snapshots: list[dict] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def observe_state(self, component_id: ComponentID, state: dict) -> dict:
        """
        Capture a raw state observation for *component_id*.

        Parameters
        ----------
        component_id : ComponentID
            The component whose state is being observed.
        state : dict
            The raw state dictionary exactly as provided — NOT interpreted.

        Returns
        -------
        dict
            Observation record containing timestamp, component, state, and
            state_hash.  NO interpretation fields.

        Guarantees
        ----------
        - No goal inference or intent labelling.
        - Deterministic hash of the state payload for tamper-detection.
        - Record is appended to `observation_log` immediately.
        - Latest snapshot for the component is updated atomically.
        """
        observation = {
            "record_type": "state_observation",
            "trace_id": _trace_id(),
            "timestamp": _timestamp(),
            "component_id": component_id.value,
            # Raw state — no transformation, no compression
            "state": state,
            # Tamper-evident hash of the raw state
            "state_hash": _payload_hash(state),
            # Explicitly mark as unannotated to prevent downstream inference
            "interpretation": None,
            "goal_inferred": False,
        }

        self.observation_log.append(observation)
        self._update_snapshot(component_id, observation)
        return observation

    def capture_evidence(self, event: dict) -> dict:
        """
        Log an arbitrary event as evidence WITHOUT inference.

        Parameters
        ----------
        event : dict
            Raw event data exactly as received.

        Returns
        -------
        dict
            Evidence record with timestamp, trace_id, and payload hash.

        Guarantees
        ----------
        - Event payload is stored verbatim.
        - No semantic labelling or intent annotation.
        """
        evidence = {
            "record_type": "evidence",
            "trace_id": _trace_id(),
            "timestamp": _timestamp(),
            # Verbatim event — immutable reference to caller's data
            "event": event,
            "payload_hash": _payload_hash(event),
            "interpretation": None,
            "goal_inferred": False,
        }

        self.observation_log.append(evidence)
        return evidence

    def get_observation_log(self) -> list:
        """
        Return the full, unmodified observation log.

        Returns
        -------
        list
            All observation and evidence records in insertion order.
        """
        return list(self.observation_log)

    def get_state_snapshot(self, component_id: ComponentID) -> Optional[dict]:
        """
        Return the most recent state observation for *component_id*.

        Parameters
        ----------
        component_id : ComponentID
            The component to retrieve a snapshot for.

        Returns
        -------
        Optional[dict]
            The latest observation record, or ``None`` if no snapshot exists.
        """
        for snap in reversed(self.state_snapshots):
            if snap.get("component_id") == component_id.value:
                return snap
        return None

    def is_state_ambiguous(self, observation: dict) -> bool:
        """
        Detect *structural* ambiguity in an observation record.

        Ambiguity is defined purely by data completeness and internal
        consistency — NOT by semantic meaning or inferred intent.

        Heuristics applied (structural only)
        -------------------------------------
        1. Missing mandatory fields (``component_id``, ``state``,
           ``timestamp``, ``state_hash``).
        2. ``state`` field is ``None`` or empty.
        3. ``state_hash`` does not match the stored ``state`` payload.
        4. ``state`` contains keys with ``None`` values *and* has fewer than
           two populated fields (incomplete snapshot).

        Parameters
        ----------
        observation : dict
            An observation record as returned by :meth:`observe_state`.

        Returns
        -------
        bool
            ``True`` if the observation is structurally incomplete or
            self-contradictory; ``False`` otherwise.
        """
        required_fields = {"component_id", "state", "timestamp", "state_hash"}

        # Heuristic 1 — mandatory fields present
        if not required_fields.issubset(observation.keys()):
            return True

        state = observation.get("state")

        # Heuristic 2 — state is absent or empty
        if not state:
            return True

        # Heuristic 3 — hash integrity check
        recorded_hash = observation.get("state_hash", "")
        recomputed_hash = _payload_hash(state)
        if recorded_hash and recorded_hash != recomputed_hash:
            return True

        # Heuristic 4 — state dict is sparsely populated with None values
        if isinstance(state, dict):
            none_values = sum(1 for v in state.values() if v is None)
            populated = len(state) - none_values
            if populated < 2 and none_values > 0:
                return True

        return False

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _update_snapshot(self, component_id: ComponentID, observation: dict) -> None:
        """
        Replace (or insert) the latest snapshot entry for *component_id*.

        Snapshots are stored in `state_snapshots` as a list so the full
        snapshot history is retained for auditability.
        """
        self.state_snapshots.append(observation)
