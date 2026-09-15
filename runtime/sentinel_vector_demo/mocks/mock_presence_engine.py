"""
Stability Engine v4.0 — Mock Presence Engine

Deterministic mock implementation of PresenceEngineAdapter.

Behaviour contract
------------------
- Read-mostly and observational: no writes to persistent stores, no
  policy authority, no invariant override, no capability expansion.
- Produces deterministic summaries based on sha256 hashes of inputs.
- Maintains in-memory state for demo purposes only (session-scoped).
- Does NOT perform adaptive personality modeling or autonomous interpretation.

Implementation notes
--------------------
- All external outputs include a ``trace_hash`` derived from the input
  to guarantee reproducibility.
- Internal state is wiped by ``reset_presence_state``; that method itself
  is audit-logged before the wipe occurs.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from typing import Any, Dict, List, Optional

from sentinel_vector_demo.adapters.presence_engine import PresenceEngineAdapter
from sentinel_vector_demo.core.types import (
    AuditEntry,
    ComponentID,
    MemoryTier,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _trace_hash(data: Any) -> str:
    """Deterministic 16-char sha256 prefix of ``repr(data)``."""
    return hashlib.sha256(repr(data).encode()).hexdigest()[:16]


def _receipt_id() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> float:
    return time.time()


# ---------------------------------------------------------------------------
# Mock Implementation
# ---------------------------------------------------------------------------

class MockPresenceEngine(PresenceEngineAdapter):
    """
    Deterministic mock of the Presence Engine adapter.

    Internal stores
    ---------------
    - ``_snapshots``   : Dict[entity_id, List[snapshot]]  — ingested snapshots
    - ``_overlays``    : Dict[entity_id, List[overlay]]   — computed overlays
    - ``_audit_log``   : List[AuditEntry]                 — internal audit trail

    All outputs are deterministically derived from input data; no randomness
    is introduced.
    """

    # Sentinel labels for overlay profile classification (deterministic bucket)
    _PROFILE_LABELS = [
        "baseline",
        "elevated",
        "transitional",
        "stabilising",
        "coherent",
    ]

    def __init__(self) -> None:
        # entity_id → ordered list of accepted snapshots
        self._snapshots: Dict[str, List[Dict[str, Any]]] = {}
        # entity_id → ordered list of overlay annotation bundles
        self._overlays: Dict[str, List[Dict[str, Any]]] = {}
        # internal audit trail (not a Tier 2 store — session-scoped only)
        self._audit_log: List[AuditEntry] = []

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _audit(
        self,
        action: str,
        entity_id: Optional[str] = None,
        result_code: str = "OK",
        trace_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        entry = AuditEntry(
            component=ComponentID.PRESENCE_ENGINE,
            action=action,
            agent_involved=entity_id,
            result_code=result_code,
            trace_id=trace_id,
            details=details or {},
        )
        self._audit_log.append(entry)

    def _profile_label(self, snapshot: Dict[str, Any]) -> str:
        """Deterministic profile label derived from snapshot hash bucket."""
        h = int(_trace_hash(snapshot), 16)
        return self._PROFILE_LABELS[h % len(self._PROFILE_LABELS)]

    def _coherence_signal(self, snapshots: List[Dict[str, Any]]) -> float:
        """
        Deterministic coherence signal in [0.0, 1.0].
        Derived from the average of the last-three snapshot hashes.
        """
        if not snapshots:
            return 0.0
        recent = snapshots[-3:]
        combined = _trace_hash(recent)
        # Map first 4 hex chars to [0.0, 1.0]
        return round(int(combined[:4], 16) / 0xFFFF, 4)

    # ------------------------------------------------------------------
    # PresenceEngineAdapter implementation
    # ------------------------------------------------------------------

    def ingest_state_snapshot(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """
        Accept a bounded state snapshot and store it under the entity's record.

        Validation
        ----------
        - ``snapshot`` must be a non-empty dict.
        - The ``entity_id`` key must be present and a non-empty string.
        - No identity-bearing cross-tier data is stored; the raw snapshot is
          accepted as-is for demo purposes (a real implementation would strip
          disallowed fields).
        """
        if not isinstance(snapshot, dict) or not snapshot:
            receipt = {
                "status": "rejected",
                "receipt_id": None,
                "trace_hash": _trace_hash(snapshot),
                "timestamp": _now(),
                "reason": "snapshot must be a non-empty dict",
            }
            self._audit("ingest_state_snapshot", result_code="REJECTED", details=receipt)
            return receipt

        entity_id: str = str(snapshot.get("entity_id", ""))
        if not entity_id:
            receipt = {
                "status": "rejected",
                "receipt_id": None,
                "trace_hash": _trace_hash(snapshot),
                "timestamp": _now(),
                "reason": "snapshot missing entity_id",
            }
            self._audit("ingest_state_snapshot", result_code="REJECTED", details=receipt)
            return receipt

        receipt_id = _receipt_id()
        trace_hash = _trace_hash(snapshot)
        ts = _now()

        # Store snapshot (session-scoped; Tier 0/1 only)
        if entity_id not in self._snapshots:
            self._snapshots[entity_id] = []
        self._snapshots[entity_id].append(snapshot)

        receipt = {
            "status": "accepted",
            "receipt_id": receipt_id,
            "trace_hash": trace_hash,
            "timestamp": ts,
            "entity_id": entity_id,
            "snapshot_index": len(self._snapshots[entity_id]) - 1,
        }
        self._audit(
            "ingest_state_snapshot",
            entity_id=entity_id,
            result_code="OK",
            trace_id=receipt_id,
            details={"trace_hash": trace_hash},
        )
        return receipt

    def compute_overlay_annotations(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compute deterministic overlay annotations from a state snapshot.

        No persistent writes are performed.  The result is derived entirely
        from the snapshot content via deterministic hashing.
        """
        if not isinstance(snapshot, dict) or not snapshot:
            return {
                "overlay_id": None,
                "annotations": {},
                "relational_edges": [],
                "profile_tag": "unknown",
                "trace_hash": _trace_hash(snapshot),
                "status": "rejected",
                "reason": "snapshot must be a non-empty dict",
            }

        entity_id = str(snapshot.get("entity_id", ""))
        trace_hash = _trace_hash(snapshot)
        overlay_id = _receipt_id()

        # Deterministic annotation values
        state_vector = snapshot.get("state_vector", {})
        sequence_step = int(snapshot.get("sequence_step", 0))
        profile_tag = self._profile_label(snapshot)

        # Relational edges: deterministic from hash
        h_int = int(trace_hash, 16)
        edge_count = h_int % 4  # 0–3 edges
        relational_edges = [
            {
                "from": entity_id,
                "to": f"entity_{(h_int + i) % 256:02x}",
                "weight": round(((h_int >> (i * 4)) & 0xF) / 15.0, 4),
            }
            for i in range(edge_count)
        ]

        annotations = {
            "sequence_step": sequence_step,
            "state_vector_keys": list(state_vector.keys()) if isinstance(state_vector, dict) else [],
            "profile_tag": profile_tag,
            "deterministic_note": "observational only — no policy authority",
            "hash_bucket": h_int % 256,
        }

        result = {
            "overlay_id": overlay_id,
            "annotations": annotations,
            "relational_edges": relational_edges,
            "profile_tag": profile_tag,
            "trace_hash": trace_hash,
            "status": "computed",
        }

        # Cache overlay for the entity
        if entity_id:
            if entity_id not in self._overlays:
                self._overlays[entity_id] = []
            self._overlays[entity_id].append(result)

        self._audit(
            "compute_overlay_annotations",
            entity_id=entity_id or None,
            result_code="OK",
            trace_id=overlay_id,
            details={"trace_hash": trace_hash, "profile_tag": profile_tag},
        )
        return result

    def get_presence_summary(self, entity_id: str) -> Dict[str, Any]:
        """
        Return a deterministic presence summary for the entity.

        If the entity has no ingested snapshots, returns a minimal
        ``not_found`` summary (no error raised — observational only).
        """
        trace_hash = _trace_hash(entity_id)
        snapshots = self._snapshots.get(entity_id, [])
        overlays = self._overlays.get(entity_id, [])

        if not snapshots:
            summary = {
                "entity_id": entity_id,
                "snapshot_count": 0,
                "last_sequence_step": None,
                "overlay_profile": "unknown",
                "coherence_signal": 0.0,
                "trace_hash": trace_hash,
                "status": "not_found",
            }
            self._audit(
                "get_presence_summary",
                entity_id=entity_id,
                result_code="NOT_FOUND",
                trace_id=trace_hash,
            )
            return summary

        last_snapshot = snapshots[-1]
        last_sequence_step = last_snapshot.get("sequence_step", len(snapshots) - 1)
        overlay_profile = overlays[-1]["profile_tag"] if overlays else self._profile_label(last_snapshot)
        coherence = self._coherence_signal(snapshots)

        summary = {
            "entity_id": entity_id,
            "snapshot_count": len(snapshots),
            "last_sequence_step": last_sequence_step,
            "overlay_profile": overlay_profile,
            "coherence_signal": coherence,
            "trace_hash": trace_hash,
            "status": "ok",
        }
        self._audit(
            "get_presence_summary",
            entity_id=entity_id,
            result_code="OK",
            trace_id=trace_hash,
            details={"coherence_signal": coherence},
        )
        return summary

    def reset_presence_state(self) -> None:
        """
        Reset all in-memory presence state.

        Audit-logs the reset action BEFORE clearing state, preserving the
        pre-reset audit trail (the audit log itself is not cleared).
        """
        snapshot_count = sum(len(v) for v in self._snapshots.values())
        overlay_count = sum(len(v) for v in self._overlays.values())

        self._audit(
            "reset_presence_state",
            result_code="OK",
            details={
                "snapshots_cleared": snapshot_count,
                "overlays_cleared": overlay_count,
                "note": "observational reset only — Tier 2 / geometry / identity untouched",
            },
        )

        self._snapshots.clear()
        self._overlays.clear()
        # Note: _audit_log is intentionally preserved across resets.

    # ------------------------------------------------------------------
    # Inspection helper (not part of adapter interface)
    # ------------------------------------------------------------------

    def get_audit_log(self) -> List[AuditEntry]:
        """Return the internal audit log (read-only copy)."""
        return list(self._audit_log)
