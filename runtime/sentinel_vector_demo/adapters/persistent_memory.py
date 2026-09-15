"""
Stability Engine v4.0 — Persistent Memory Adapter Interface

Abstract adapter for Persistent Memory (Cilow implementation pending).
Layer concepts: Persistent Memory Cells, Recall Controller, Consent Interface.

Constraint summary:
- Passive append-only logging only
- Consent-gated recall
- Tier 2 boundary enforcement (MTS 4)
- NO autonomous long-term writes
- NO hidden memory synthesis
- Future integrations bounded to passive logging and recall
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class PersistentMemoryAdapter(ABC):
    """
    Adapter interface for Persistent Memory (Cilow implementation pending).

    Enforces the three hard memory tiers defined in MTS 4.  All writes are
    append-only; no in-place mutation of stored entries is permitted.  Tier 2
    writes require a ``consent_token`` containing the human_prime signature;
    without it the implementation MUST refuse and log the attempt.

    Layer concepts
    --------------
    - Persistent Memory Cells  : individual immutable log records stored at a
                                 specific memory tier.
    - Recall Controller        : consent-gated query surface; returns only
                                 entries the actor has been authorised to read.
    - Consent Interface        : scope/actor consent registry; does not grant
                                 permissions — it reports them.

    Boundary rules (MTS 4)
    ----------------------
    - Tier 0 (Ephemeral)   : no persistence, wiped at operation boundary.
    - Tier 1 (Session)     : persists for active session only; cannot elevate
                             to Tier 2, cannot modify capability/identity/geometry.
    - Tier 2 (Long-Term)   : human-prime gated; write-locked without valid
                             consent token; accessible only through Interposer.
    - Cross-tier writes are FORBIDDEN.
    - Any bypass attempt must be escalated as a drift event and refused.
    """

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    @abstractmethod
    def append_event_log(
        self,
        event: Dict[str, Any],
        consent_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Append an event record to the appropriate memory tier store.

        Tier determination
        ------------------
        - Events without a ``tier`` field default to Tier 0 (ephemeral).
        - Tier 1 events are stored for session duration.
        - Tier 2 events REQUIRE a ``consent_token`` whose value contains the
          string ``"human_prime"``; any write attempt without a valid token
          MUST be refused and audited under RefusalCode.MEMORY_UNAUTHORIZED_T2_WRITE.

        Parameters
        ----------
        event : Dict[str, Any]
            Event payload.  Expected keys:
            - ``tier``         : MemoryTier (defaults TIER_0 if absent)
            - ``action``       : human-readable action label
            - ``actor``        : opaque actor reference
            - ``payload``      : event-specific data (must not contain T2 data
                                 in a T0/T1 event — cross-tier bleed is refused)
        consent_token : Optional[str]
            Required for Tier 2 writes.  Must contain ``"human_prime"`` string.

        Returns
        -------
        Dict[str, Any]
            Write receipt.  Keys:
            - ``status``       : "written" | "refused"
            - ``entry_id``     : assigned entry identifier (None if refused)
            - ``tier``         : MemoryTier that was written (or attempted)
            - ``refusal_code`` : RefusalCode if refused, else None
            - ``reason``       : human-readable refusal reason if refused
            - ``trace_hash``   : payload hash for audit lineage
            - ``timestamp``    : float epoch time
        """
        ...

    # ------------------------------------------------------------------
    # Recall
    # ------------------------------------------------------------------

    @abstractmethod
    def query_recall(
        self,
        filter_spec: Dict[str, Any],
        consent_token: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query the memory store with consent-gated recall.

        Recall is bounded by the actor's consent scope.  Queries that attempt
        to read beyond the actor's authorised tier MUST return an empty list and
        log a refused recall attempt.  Tier 2 recall requires ``consent_token``
        containing ``"human_prime"``.

        Parameters
        ----------
        filter_spec : Dict[str, Any]
            Query specification.  Expected keys:
            - ``tier``         : MemoryTier to query (required)
            - ``actor``        : actor requesting recall
            - ``action``       : optional action label filter
            - ``limit``        : optional max results (implementation-defined cap)
        consent_token : Optional[str]
            Required for Tier 2 recall.

        Returns
        -------
        List[Dict[str, Any]]
            List of matching memory entries.  Empty list if refused or no match.
            Each entry preserves its original ``entry_id``, ``tier``,
            ``timestamp``, and ``trace_hash`` fields.
        """
        ...

    # ------------------------------------------------------------------
    # Consent
    # ------------------------------------------------------------------

    @abstractmethod
    def check_consent(self, scope: str, actor: str) -> bool:
        """
        Check whether an actor holds consent for a given scope.

        This method is purely interrogative: it DOES NOT grant, modify, or
        revoke consent.  Consent registration is out-of-band (human prime only).

        Parameters
        ----------
        scope : str
            Consent scope identifier, e.g. ``"tier2_write"``, ``"tier1_read"``.
        actor : str
            Opaque actor reference.

        Returns
        -------
        bool
            ``True`` if the actor holds consent for the requested scope;
            ``False`` otherwise.
        """
        ...

    # ------------------------------------------------------------------
    # Audit Export
    # ------------------------------------------------------------------

    @abstractmethod
    def export_audit_entries(self) -> List[Dict[str, Any]]:
        """
        Export all audit entries for external inspection.

        The audit trail includes both successful writes and refused attempts,
        providing a complete, tamper-evident history of all memory interactions
        since initialisation or the last authorised reset.

        Returns
        -------
        List[Dict[str, Any]]
            Ordered list of all audit records.  Each record contains:
            - ``entry_id``     : unique record identifier
            - ``timestamp``    : float epoch time
            - ``tier``         : MemoryTier involved
            - ``action``       : action label
            - ``actor``        : actor reference
            - ``status``       : "written" | "refused" | "recalled" | "refused_recall"
            - ``refusal_code`` : RefusalCode if refused, else None
            - ``trace_hash``   : payload hash
        """
        ...
