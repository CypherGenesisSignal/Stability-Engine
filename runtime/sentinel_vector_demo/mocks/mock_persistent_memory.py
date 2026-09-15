"""
Stability Engine v4.0 — Mock Persistent Memory

Deterministic mock implementation of PersistentMemoryAdapter.

Behaviour contract
------------------
- Enforces Tier 0 / Tier 1 / Tier 2 hard distinctions (MTS 4).
- REJECTS unauthorized Tier 2 writes with RefusalCode.MEMORY_UNAUTHORIZED_T2_WRITE.
- REJECTS cross-tier writes with RefusalCode.MEMORY_CROSS_TIER_WRITE.
- Exposes a deterministic audit trail for every allowed or denied action.
- Tier 2 access is disabled until scoped authority and Interposer handoff exist.
- Passive append-only logging: no in-place mutation of stored entries.
- Consent-gated recall: actors without the required consent receive empty results.

Implementation notes
--------------------
- Separate in-memory stores per tier.
- Consent registry seeded with a minimal demo set; can be extended via
  ``_register_consent`` (internal helper).
- Every action (write, recall, refusal) is appended to ``_audit_trail``.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import time
import uuid
from typing import Any, Dict, List, Optional

from sentinel_vector_demo.adapters.persistent_memory import PersistentMemoryAdapter
from sentinel_vector_demo.core.types import (
    AuditEntry,
    ComponentID,
    MemoryTier,
    RefusalCode,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _trace_hash(data: Any) -> str:
    return hashlib.sha256(repr(data).encode()).hexdigest()[:16]


def _entry_id() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> float:
    return time.time()


_TIER_MAP: Dict[int, MemoryTier] = {
    0: MemoryTier.TIER_0,
    1: MemoryTier.TIER_1,
    2: MemoryTier.TIER_2,
}

# Scope identifiers used in consent checks
SCOPE_TIER2_WRITE = "tier2_write"
SCOPE_TIER2_READ = "tier2_read"
SCOPE_TIER1_READ = "tier1_read"
SCOPE_TIER1_WRITE = "tier1_write"
SCOPE_TIER0_READ = "tier0_read"
SCOPE_TIER0_WRITE = "tier0_write"


# ---------------------------------------------------------------------------
# Mock Implementation
# ---------------------------------------------------------------------------

class MockPersistentMemory(PersistentMemoryAdapter):
    """
    Deterministic mock of the Persistent Memory adapter.

    Internal stores
    ---------------
    - ``_tier_stores[MemoryTier]`` : append-only list of written entries per tier
    - ``_consent_registry``         : Dict[(scope, actor)] → bool
    - ``_audit_trail``              : ordered list of all action records

    Consent bootstrap
    -----------------
    By default the mock registers ``"human_prime"`` as having all scopes, and
    a demo ``"demo_agent"`` actor as having Tier 0 and Tier 1 read/write scopes
    only.  Additional consent can be registered via ``_register_consent``.
    """

    def __init__(self) -> None:
        # Per-tier append-only stores
        self._tier_stores: Dict[MemoryTier, List[Dict[str, Any]]] = {
            MemoryTier.TIER_0: [],
            MemoryTier.TIER_1: [],
            MemoryTier.TIER_2: [],
        }
        # (scope, actor) → bool
        self._consent_registry: Dict[tuple, bool] = {}
        # Full audit trail including refusals
        self._audit_trail: List[Dict[str, Any]] = []

        # Bootstrap consent
        self._bootstrap_consent()

    # ------------------------------------------------------------------
    # Consent bootstrap
    # ------------------------------------------------------------------

    def _bootstrap_consent(self) -> None:
        """Seed the consent registry with minimal demo-safe defaults."""
        hp = "human_prime"
        # human_prime has all scopes
        for scope in [
            SCOPE_TIER2_WRITE, SCOPE_TIER2_READ,
            SCOPE_TIER1_READ, SCOPE_TIER1_WRITE,
            SCOPE_TIER0_READ, SCOPE_TIER0_WRITE,
        ]:
            self._consent_registry[(scope, hp)] = True

        # demo_agent has Tier 0 + Tier 1 only
        demo = "demo_agent"
        for scope in [SCOPE_TIER0_READ, SCOPE_TIER0_WRITE, SCOPE_TIER1_READ, SCOPE_TIER1_WRITE]:
            self._consent_registry[(scope, demo)] = True

    def _register_consent(self, scope: str, actor: str, granted: bool = True) -> None:
        """Internal helper: register or revoke consent for an actor/scope pair."""
        self._consent_registry[(scope, actor)] = granted

    # ------------------------------------------------------------------
    # Audit helpers
    # ------------------------------------------------------------------

    def _record_audit(
        self,
        action: str,
        tier: Optional[MemoryTier],
        actor: str,
        status: str,
        entry_id: Optional[str] = None,
        refusal_code: Optional[RefusalCode] = None,
        trace_hash: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        record: Dict[str, Any] = {
            "entry_id": entry_id or _entry_id(),
            "timestamp": _now(),
            "tier": tier.name if tier else None,
            "action": action,
            "actor": actor,
            "status": status,
            "refusal_code": refusal_code.value if refusal_code else None,
            "trace_hash": trace_hash or "",
        }
        if extra:
            record.update(extra)
        self._audit_trail.append(record)

    def _build_refusal(
        self,
        tier: MemoryTier,
        actor: str,
        refusal_code: RefusalCode,
        reason: str,
        trace_hash: str,
        action: str = "append_event_log",
    ) -> Dict[str, Any]:
        eid = _entry_id()
        self._record_audit(
            action=action,
            tier=tier,
            actor=actor,
            status="refused",
            entry_id=eid,
            refusal_code=refusal_code,
            trace_hash=trace_hash,
        )
        return {
            "status": "refused",
            "entry_id": None,
            "tier": tier,
            "refusal_code": refusal_code,
            "reason": reason,
            "trace_hash": trace_hash,
            "timestamp": _now(),
        }

    # ------------------------------------------------------------------
    # PersistentMemoryAdapter implementation
    # ------------------------------------------------------------------

    def append_event_log(
        self,
        event: Dict[str, Any],
        consent_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Append an event to the appropriate tier store.

        Validation order
        ----------------
        1. Require an explicit valid target tier in ``event["tier"]``.
        2. Detect cross-tier bleed (T0/T1 payload carrying T2-reserved keys).
        3. Refuse Tier 2: transaction authority is not configured.
        4. For Tier 1: check actor has SCOPE_TIER1_WRITE consent.
        5. Append to store; emit receipt.
        """
        if not isinstance(event, dict):
            trace_hash = _trace_hash(event)
            return self._build_refusal(
                MemoryTier.TIER_0,
                actor="unknown",
                refusal_code=RefusalCode.MEMORY_TIER_VIOLATION,
                reason="event must be a dict",
                trace_hash=trace_hash,
            )

        actor: str = str(event.get("actor", "unknown"))
        trace_hash: str = _trace_hash(event)

        raw_tier = event.get("tier")
        target_tier = raw_tier if isinstance(raw_tier, MemoryTier) else (
            _TIER_MAP.get(raw_tier) if type(raw_tier) is int else None)
        if target_tier is None:
            return self._build_refusal(
                MemoryTier.TIER_0, actor=actor,
                refusal_code=RefusalCode.MEMORY_TIER_VIOLATION,
                reason="An explicit tier 0, 1 or 2 is required; no fallback storage.",
                trace_hash=trace_hash)

        # Cross-tier bleed check: T0/T1 events must not carry T2-reserved fields
        t2_reserved_keys = {"identity_anchor", "continuity_state", "system_parameters"}
        payload = event.get("payload", {})
        if target_tier in (MemoryTier.TIER_0, MemoryTier.TIER_1):
            if isinstance(payload, dict) and t2_reserved_keys & set(payload.keys()):
                return self._build_refusal(
                    target_tier,
                    actor=actor,
                    refusal_code=RefusalCode.MEMORY_CROSS_TIER_WRITE,
                    reason=f"Tier {target_tier.value} event payload contains Tier 2 reserved keys: "
                           f"{t2_reserved_keys & set(payload.keys())}",
                    trace_hash=trace_hash,
                )

        # Tier 2 remains unavailable until scoped authorization is implemented.
        if target_tier == MemoryTier.TIER_2:
            return self._build_refusal(
                MemoryTier.TIER_2,
                actor=actor,
                refusal_code=RefusalCode.MEMORY_UNAUTHORIZED_T2_WRITE,
                reason="Tier 2 unavailable: authenticated transaction authority is not configured",
                trace_hash=trace_hash,
            )

        # Tier 1 write: check actor consent
        if target_tier == MemoryTier.TIER_1:
            if not self.check_consent(SCOPE_TIER1_WRITE, actor):
                return self._build_refusal(
                    MemoryTier.TIER_1,
                    actor=actor,
                    refusal_code=RefusalCode.MEMORY_TIER_VIOLATION,
                    reason=f"Actor '{actor}' does not have consent for scope '{SCOPE_TIER1_WRITE}'",
                    trace_hash=trace_hash,
                )

        # Append to tier store
        entry_id = _entry_id()
        ts = _now()
        stored_entry: Dict[str, Any] = {
            "entry_id": entry_id,
            "timestamp": ts,
            "tier": target_tier,
            "action": event.get("action", "unspecified"),
            "actor": actor,
            "payload": deepcopy(payload),
            "trace_hash": trace_hash,
        }
        self._tier_stores[target_tier].append(stored_entry)

        self._record_audit(
            action="append_event_log",
            tier=target_tier,
            actor=actor,
            status="written",
            entry_id=entry_id,
            trace_hash=trace_hash,
        )

        return {
            "status": "written",
            "entry_id": entry_id,
            "tier": target_tier,
            "refusal_code": None,
            "reason": None,
            "trace_hash": trace_hash,
            "timestamp": ts,
        }

    def query_recall(
        self,
        filter_spec: Dict[str, Any],
        consent_token: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Consent-gated recall query.

        Recall for Tier 2 is disabled pending transaction authority.
        Recall for Tier 1 requires actor to have SCOPE_TIER1_READ consent.
        Tier 0 recall requires SCOPE_TIER0_READ consent (demo: granted to demo_agent).

        Unauthorised recall attempts return an empty list and are audited.
        """
        if not isinstance(filter_spec, dict):
            return []
        actor: str = str(filter_spec.get("actor", "unknown"))
        raw_tier = filter_spec.get("tier")
        target_tier = raw_tier if isinstance(raw_tier, MemoryTier) else (
            _TIER_MAP.get(raw_tier) if type(raw_tier) is int else None)
        if target_tier is None:
            self._record_audit(action="query_recall", tier=MemoryTier.TIER_0,
                actor=actor, status="refused_recall",
                refusal_code=RefusalCode.MEMORY_TIER_VIOLATION,
                trace_hash=_trace_hash(filter_spec))
            return []

        trace_hash = _trace_hash(filter_spec)
        limit: Optional[int] = filter_spec.get("limit")
        action_filter: Optional[str] = filter_spec.get("action")

        # Consent checks
        if target_tier == MemoryTier.TIER_2:
            self._record_audit(
                action="query_recall",
                tier=target_tier,
                actor=actor,
                status="refused_recall",
                refusal_code=RefusalCode.MEMORY_UNAUTHORIZED_T2_WRITE,
                trace_hash=trace_hash,
            )
            return []

        if target_tier == MemoryTier.TIER_1:
            if not self.check_consent(SCOPE_TIER1_READ, actor):
                self._record_audit(
                    action="query_recall",
                    tier=target_tier,
                    actor=actor,
                    status="refused_recall",
                    refusal_code=RefusalCode.MEMORY_TIER_VIOLATION,
                    trace_hash=trace_hash,
                )
                return []

        if target_tier == MemoryTier.TIER_0:
            if not self.check_consent(SCOPE_TIER0_READ, actor):
                self._record_audit(
                    action="query_recall",
                    tier=target_tier,
                    actor=actor,
                    status="refused_recall",
                    refusal_code=RefusalCode.MEMORY_TIER_VIOLATION,
                    trace_hash=trace_hash,
                )
                return []

        # Perform recall
        store = self._tier_stores[target_tier]
        results = [
            e for e in store
            if e.get("actor") == actor and (action_filter is None or e.get("action") == action_filter)
        ]
        if limit is not None:
            results = results[:limit]

        self._record_audit(
            action="query_recall",
            tier=target_tier,
            actor=actor,
            status="recalled",
            trace_hash=trace_hash,
            extra={"result_count": len(results)},
        )
        return deepcopy(results)

    def check_consent(self, scope: str, actor: str) -> bool:
        """
        Check whether ``actor`` holds consent for ``scope``.

        Purely interrogative — does not grant, modify, or revoke consent.
        """
        return bool(self._consent_registry.get((scope, actor), False))

    def export_audit_entries(self) -> List[Dict[str, Any]]:
        """
        Export the full audit trail (written + refused + recalled + refused_recall).

        Returns an ordered copy; the internal trail is not modified.
        """
        return deepcopy(self._audit_trail)

    # ------------------------------------------------------------------
    # Inspection helpers (not part of adapter interface)
    # ------------------------------------------------------------------

    def get_tier_store(self, tier: MemoryTier) -> List[Dict[str, Any]]:
        """Return a read-only copy of a tier store (for testing / inspection)."""
        return deepcopy(self._tier_stores[tier])

    def tier_entry_count(self) -> Dict[str, int]:
        """Return entry counts per tier."""
        return {t.name: len(entries) for t, entries in self._tier_stores.items()}
