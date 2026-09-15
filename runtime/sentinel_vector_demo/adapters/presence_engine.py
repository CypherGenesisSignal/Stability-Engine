"""
Stability Engine v4.0 — Presence Engine Adapter Interface

Abstract adapter for the Presence Engine (collaborator-owned, not yet available).
Layer concepts: State Kernel, Relational State Matrix, Overlay Profiles.

Constraint summary:
- NO policy authority
- NO invariant override
- NO capability expansion
- Read-mostly / observational surface only
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class PresenceEngineAdapter(ABC):
    """
    Adapter interface for Presence Engine.

    Accepts bounded state snapshots from the orchestrator/core and returns
    overlay/state annotations.  The Presence Engine is a passive observer:
    it has no authority over invariants, identity, or capability envelopes.

    Layer concepts
    --------------
    - State Kernel          : atomic snapshot of an entity's current operational
                              state, owned by the orchestrator.
    - Relational State Matrix: read-only adjacency of inter-entity state
                              relationships; never mutated through this adapter.
    - Overlay Profiles      : lightweight, ephemeral annotation layers that
                              augment state snapshots for downstream consumers.

    Boundary rules
    --------------
    - Adapter MUST NOT write to Tier 2 memory.
    - Adapter MUST NOT modify geometry, identity, or capability envelopes.
    - Adapter MUST NOT initiate autonomous actions or emit control signals.
    - All outputs are observational/annotational only.
    """

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    @abstractmethod
    def ingest_state_snapshot(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """
        Accept a bounded state snapshot from the orchestrator or core.

        The snapshot MUST NOT contain identity markers (per MTS 4 / Tier 0
        cross-agent rules).  Implementations must validate and receipt the
        ingestion without storing personally identifying data.

        Parameters
        ----------
        snapshot : Dict[str, Any]
            Bounded state snapshot.  Expected keys include:
            - ``entity_id``    : opaque entity reference (no PII)
            - ``state_vector`` : current state signal values
            - ``sequence_step``: monotonic cycle counter
            - ``tier``         : MemoryTier of originating context

        Returns
        -------
        Dict[str, Any]
            Ingestion receipt with at minimum:
            - ``status``       : "accepted" | "rejected"
            - ``receipt_id``   : unique receipt identifier
            - ``trace_hash``   : payload hash for audit lineage
            - ``timestamp``    : float epoch time
        """
        ...

    # ------------------------------------------------------------------
    # Overlay Computation
    # ------------------------------------------------------------------

    @abstractmethod
    def compute_overlay_annotations(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compute bounded overlay annotations from a state snapshot.

        Annotations are read-only and observational; they describe the
        snapshot without altering system state.  Implementations MUST NOT
        perform any writes to persistent stores during this call.

        Parameters
        ----------
        snapshot : Dict[str, Any]
            The same bounded snapshot format accepted by ``ingest_state_snapshot``.

        Returns
        -------
        Dict[str, Any]
            Overlay annotation bundle.  Expected keys:
            - ``overlay_id``        : unique annotation identifier
            - ``annotations``       : Dict[str, Any] of labeled observations
            - ``relational_edges``  : List of observed relational state edges
            - ``profile_tag``       : overlay profile classification label
            - ``trace_hash``        : hash linking annotation to source snapshot
        """
        ...

    # ------------------------------------------------------------------
    # Presence Summary
    # ------------------------------------------------------------------

    @abstractmethod
    def get_presence_summary(self, entity_id: str) -> Dict[str, Any]:
        """
        Return the presence summary for a given entity.

        The summary is derived solely from previously ingested snapshots and
        carries no policy authority.  Callers MUST NOT use the summary output
        to make capability, identity, or invariant decisions without routing
        through the Interposer.

        Parameters
        ----------
        entity_id : str
            Opaque entity reference.  MUST match the ``entity_id`` field from
            a previously accepted ``ingest_state_snapshot`` call.

        Returns
        -------
        Dict[str, Any]
            Presence summary.  Expected keys:
            - ``entity_id``         : echoed entity reference
            - ``snapshot_count``    : number of ingested snapshots for entity
            - ``last_sequence_step``: most recent sequence step seen
            - ``overlay_profile``   : latest overlay profile tag
            - ``coherence_signal``  : float [0.0, 1.0] observational coherence
            - ``trace_hash``        : hash for audit lineage
        """
        ...

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    @abstractmethod
    def reset_presence_state(self) -> None:
        """
        Reset all in-memory presence state.

        This is an **observational reset only**: it clears ephemeral tracking
        data accumulated during the session.  It MUST NOT touch Tier 2 memory,
        geometry structures, identity anchors, or capability envelopes.

        Implementations must log the reset action to their internal audit
        surface before clearing state.
        """
        ...
