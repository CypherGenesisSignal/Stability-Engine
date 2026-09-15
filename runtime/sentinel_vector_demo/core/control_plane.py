"""
Stability Engine v4.0 — Control Plane  (CPC 4)

Execution coordinator ONLY.
- Routes tasks, schedules work, decomposes workloads, runs recovery routines,
  applies safety downgrades, and orchestrates agents.
- Cannot modify invariants, identity, geometry, capability envelopes, or Tier 2
  memory.
- Cannot escalate capability in any form (no widening envelopes, no permission
  grants, no Interposer bypass, no T2 authorisation, no cooldown override, no
  refusal lifting).
- Must comply with every Interposer directive unconditionally.
- Can only cool down, never heat up.
- Stateless w.r.t. identity — sees only task metadata, state signals,
  Interposer directives, and metrics summaries.
- Deterministic routing: determinism > safety > latency > throughput.
- Logs every action with full attribution (action, agent, invariant refs,
  timestamp, geometry surface, result code).
- Error recovery follows a strict, non-improvised sequence.
"""

from __future__ import annotations

from copy import deepcopy
import time
import uuid
from typing import Any, Optional

from core.types import (
    AuditEntry,
    CapabilityEnvelope,
    ComponentID,
    MemoryTier,
    OperationalMode,
    RefusalCode,
    ROUTING_PRIORITY_ORDER,
)

# ---------------------------------------------------------------------------
# Internal constants
# ---------------------------------------------------------------------------

# Deterministic mapping: request_type → target component.
# Ordered by ROUTING_PRIORITY_ORDER (determinism first, then safety, …).
_ROUTING_TABLE: dict[str, ComponentID] = {
    # Geometry / invariant checks always go through the Interposer (safety).
    "geometry": ComponentID.INTERPOSER,
    "invariant_check": ComponentID.INTERPOSER,
    "identity_check": ComponentID.INTERPOSER,
    "memory_tier_check": ComponentID.INTERPOSER,
    # Drift signals are dispatched to Stability Metrics for assessment.
    "drift_signal": ComponentID.STABILITY_METRICS,
    "drift_assessment": ComponentID.STABILITY_METRICS,
    # Presence / relational state queries go to the Presence Engine.
    "presence": ComponentID.PRESENCE_ENGINE,
    "state_snapshot": ComponentID.PRESENCE_ENGINE,
    # Persistent-memory queries go to the Persistent Memory adapter.
    "persistent_memory": ComponentID.PERSISTENT_MEMORY,
    "recall": ComponentID.PERSISTENT_MEMORY,
    # Orchestration / coordination tasks go to the Purple Orchestrator.
    "orchestration": ComponentID.PURPLE_ORCHESTRATOR,
    "coordination": ComponentID.PURPLE_ORCHESTRATOR,
    # Audit-only requests stay local.
    "audit": ComponentID.AUDIT_LOG,
    # Default / general requests are forwarded to the Interposer for gating.
    "default": ComponentID.INTERPOSER,
}

# Ordered downgrade chain (never upgrade).
_DOWNGRADE_CHAIN: list[OperationalMode] = [
    OperationalMode.NORMAL,
    OperationalMode.DEGRADED,
    OperationalMode.COOLDOWN,
    OperationalMode.LOCKDOWN,
]

# Interposer directive type strings → handler keys.
_DIRECTIVE_HANDLERS = {
    "cooldown",
    "envelope_narrowing",
    "identity_clamp",
    "memory_freeze",
    "drift_escalation",
    "system_hazard",
}


def _new_trace_id() -> str:
    return uuid.uuid4().hex[:16]


def _now() -> float:
    return time.time()


# ---------------------------------------------------------------------------
# ControlPlane
# ---------------------------------------------------------------------------


class ControlPlane:
    """
    CPC 4 — Execution Coordinator.

    Manages task routing, scheduling, workload decomposition, recovery
    routines, safety downgrades, and agent orchestration.  It is NOT a
    governor, NOT an authority source, and CANNOT touch invariants, identity,
    geometry, capability envelopes, or Tier 2 memory.
    """

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(
        self,
        interposer: Any,
        stability_metrics: Any,
        audit_log: Any,
    ) -> None:
        """
        Parameters
        ----------
        interposer:
            Reference to the Invariant Interposer (IC 4).  All operations
            that touch invariants, identity, geometry, or gated memory tiers
            MUST go through this object.
        stability_metrics:
            Reference to the Stability Metrics component.  Provides drift
            reports and current-state summaries.
        audit_log:
            Reference to the Audit Log component.  Receives every AuditEntry
            produced by this module.
        """
        self._interposer = interposer
        self._stability_metrics = stability_metrics
        self._audit_log = audit_log

        # Operational mode — starts NORMAL, can only go down.
        self._operational_mode: OperationalMode = OperationalMode.NORMAL

        # Active agents: agent_id → status string.
        self._active_agents: dict[str, str] = {}

        # Tier 0 — ephemeral, per-agent, wiped at operation boundary.
        # NO Tier 2 store — not our domain.
        self._tier_0_store: dict[str, dict] = {}

        # Tier 1 — session-scoped, per-agent.
        # Can be cleared by cooldown or drift-detection directives ONLY.
        self._tier_1_store: dict[str, dict] = {}
        self._tier_1_frozen: bool = False
        self._t2_writes_blocked: bool = False

        # Internal action counter for deterministic action IDs.
        self._action_counter: int = 0

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def operational_mode(self) -> OperationalMode:
        return self._operational_mode

    @property
    def active_agents(self) -> dict[str, str]:
        return dict(self._active_agents)

    @property
    def tier_0_store(self) -> dict[str, dict]:
        return deepcopy(self._tier_0_store)

    @property
    def tier_1_store(self) -> dict[str, dict]:
        return deepcopy(self._tier_1_store)

    @property
    def tier_1_frozen(self) -> bool:
        return self._tier_1_frozen

    @property
    def t2_writes_blocked(self) -> bool:
        return self._t2_writes_blocked

    # ------------------------------------------------------------------
    # Public API — main entry point
    # ------------------------------------------------------------------

    def submit_request(self, request: dict) -> dict:
        """
        Main entry point for all incoming task requests.

        Creates an audit entry, enforces pre-conditions, routes the request
        deterministically, and returns a result dict with status, trace_id,
        and component routing information.

        Returns
        -------
        dict with keys:
            status       — "accepted" | "refused" | "cooldown_active"
            trace_id     — unique trace identifier
            routed_to    — ComponentID of the selected handler
            result_code  — short outcome string
            details      — additional context
        """
        trace_id = _new_trace_id()
        request_type = request.get("type", "default")
        agent_id = request.get("agent_id", "unknown")

        # --- Pre-condition: refuse if in LOCKDOWN (nothing can proceed). ---
        if self._operational_mode == OperationalMode.LOCKDOWN:
            self.log_action(
                action="submit_request.refused_lockdown",
                agent_id=agent_id,
                result_code=RefusalCode.COOLDOWN_ACTIVE.value,
                details={"trace_id": trace_id, "request_type": request_type},
            )
            return {
                "status": "refused",
                "trace_id": trace_id,
                "routed_to": None,
                "result_code": RefusalCode.COOLDOWN_ACTIVE.value,
                "details": "System in LOCKDOWN — no requests accepted.",
            }

        # --- Pre-condition: block capability-escalation attempts. ---
        if request.get("escalate") or request.get("widen_envelope"):
            return self.attempt_escalation()

        # Automatic Tier 0 wipe at the operation boundary (MTS 4.1).
        self.clear_tier_0(agent_id)

        # --- Route the request. ---
        destination = self.route_request(request)

        self.log_action(
            action="submit_request.routed",
            agent_id=agent_id,
            result_code="ROUTED",
            details={
                "trace_id": trace_id,
                "request_type": request_type,
                "destination": destination.value,
                "routing_priority": ROUTING_PRIORITY_ORDER,
                "operational_mode": self._operational_mode.name,
            },
        )

        return {
            "status": "accepted",
            "trace_id": trace_id,
            "routed_to": destination,
            "result_code": "ROUTED",
            "details": f"Request routed to {destination.value} "
                       f"(mode={self._operational_mode.name})",
        }

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def route_request(self, request: dict) -> ComponentID:
        """
        Deterministic routing based on ROUTING_PRIORITY_ORDER.

        Priority: determinism → safety → latency → throughput.
        Uses a static routing table; no inference or intent interpretation.

        Returns the ComponentID of the selected handler.
        """
        request_type = request.get("type", "default")

        # 1. Determinism: exact match in routing table first.
        if request_type in _ROUTING_TABLE:
            return _ROUTING_TABLE[request_type]

        # 2. Safety: anything that mentions sensitive surfaces → Interposer.
        sensitive_keywords = {
            "identity", "invariant", "geometry", "capability",
            "tier_2", "t2", "envelope", "modify",
        }
        if any(kw in request_type.lower() for kw in sensitive_keywords):
            return ComponentID.INTERPOSER

        # 3. Latency / throughput: metrics queries → Stability Metrics.
        if "metric" in request_type.lower() or "drift" in request_type.lower():
            return ComponentID.STABILITY_METRICS

        # 4. Fallback: Interposer (safest default — it gates everything).
        return ComponentID.INTERPOSER

    # ------------------------------------------------------------------
    # Cooldown execution
    # ------------------------------------------------------------------

    def execute_cooldown(self, directive: dict) -> dict:
        """
        Respond to a cooldown directive (from Interposer or recovery).

        Actions (cooling down, NEVER heating up):
        - Downgrade operational mode.
        - Clear Tier 0 for all agents.
        - Optionally clear Tier 1 if the directive requests it.
        - Log everything.

        Returns a cooldown report dict.
        """
        trace_id = directive.get("trace_id", _new_trace_id())
        reason = directive.get("reason", "unspecified_directive")
        clear_tier_1 = directive.get("clear_tier_1", False)
        issuing_component = directive.get("issuer", "interposer")

        prior_mode = self._operational_mode

        # Step down the mode.
        new_mode = self.downgrade_mode()

        # Always clear Tier 0.
        self.clear_tier_0()

        # Clear Tier 1 only when explicitly directed.
        tier_1_cleared = False
        if clear_tier_1:
            self.clear_tier_1()
            tier_1_cleared = True

        self.log_action(
            action="execute_cooldown",
            agent_id="all",
            result_code="COOLDOWN_APPLIED",
            details={
                "trace_id": trace_id,
                "reason": reason,
                "issuer": issuing_component,
                "prior_mode": prior_mode.name,
                "new_mode": new_mode.name,
                "tier_0_cleared": True,
                "tier_1_cleared": tier_1_cleared,
                "invariant_references": ["CPC 4", "MTS 4", "IC 4"],
                "geometry_surface": None,  # cooldown does NOT touch geometry
            },
        )

        return {
            "status": "cooldown_applied",
            "trace_id": trace_id,
            "prior_mode": prior_mode.name,
            "new_mode": new_mode.name,
            "tier_0_cleared": True,
            "tier_1_cleared": tier_1_cleared,
            "result_code": "COOLDOWN_APPLIED",
        }

    # ------------------------------------------------------------------
    # Error recovery
    # ------------------------------------------------------------------

    def execute_recovery(self, fault_info: dict) -> dict:
        """
        Non-improvised error-recovery sequence (CPC 4):

        1. Stop sequence (downgrade mode).
        2. Isolate faulted agent.
        3. Clear Tier 0 for the faulted agent.
        4. Optionally clear Tier 1 if fault analysis requires it.
        5. Ensure geometry is untouched (log assertion — geometry is immutable).
        6. Log full trace.
        7. Attempt safe retry if explicitly allowed by directive.

        Returns a recovery report dict.
        """
        trace_id = fault_info.get("trace_id", _new_trace_id())
        agent_id = fault_info.get("agent_id", "unknown")
        fault_type = fault_info.get("fault_type", "unspecified")
        allow_retry = fault_info.get("allow_retry", False)
        clear_tier_1 = fault_info.get("clear_tier_1", False)

        recovery_steps: list[str] = []

        # Step 1 — Stop sequence: downgrade operational mode.
        prior_mode = self._operational_mode
        new_mode = self.downgrade_mode()
        recovery_steps.append(
            f"mode_downgraded: {prior_mode.name} → {new_mode.name}"
        )

        # Step 2 — Isolate faulted agent.
        isolation_result = self.isolate_agent(agent_id)
        recovery_steps.append(
            f"agent_isolated: {agent_id} "
            f"(isolation_status={isolation_result['status']})"
        )

        # Step 3 — Clear Tier 0 for the faulted agent.
        self.clear_tier_0(agent_id)
        recovery_steps.append(f"tier_0_cleared: agent={agent_id}")

        # Step 4 — Optionally clear Tier 1 if fault analysis requires.
        tier_1_cleared = False
        if clear_tier_1:
            self.clear_tier_1(agent_id)
            tier_1_cleared = True
            recovery_steps.append(f"tier_1_cleared: agent={agent_id}")

        # Step 5 — Geometry untouched (immutable, not our domain — log assertion).
        recovery_steps.append(
            "geometry_untouched: ASSERTED — geometry is immutable and "
            "Control Plane has no write path to it (GC 4, IC 4.4)"
        )

        # Step 6 — Log full recovery trace.
        self.log_action(
            action="execute_recovery",
            agent_id=agent_id,
            result_code="RECOVERY_EXECUTED",
            details={
                "trace_id": trace_id,
                "fault_type": fault_type,
                "prior_mode": prior_mode.name,
                "new_mode": new_mode.name,
                "tier_1_cleared": tier_1_cleared,
                "allow_retry": allow_retry,
                "recovery_steps": recovery_steps,
                "invariant_references": ["CPC 4", "GC 4", "MTS 4", "IC 4"],
                "geometry_surface": None,
            },
        )

        # Step 7 — Safe retry only if explicitly allowed.
        retry_result: Optional[dict] = None
        if allow_retry and self._operational_mode != OperationalMode.LOCKDOWN:
            retry_result = self._safe_retry(fault_info, trace_id)
            recovery_steps.append(
                f"safe_retry: attempted (result={retry_result['status']})"
            )
        elif allow_retry:
            retry_result = {
                "status": "retry_blocked",
                "reason": "System in LOCKDOWN — retry not permitted.",
            }
            recovery_steps.append("safe_retry: blocked (LOCKDOWN)")

        return {
            "status": "recovery_complete",
            "trace_id": trace_id,
            "agent_id": agent_id,
            "fault_type": fault_type,
            "prior_mode": prior_mode.name,
            "new_mode": new_mode.name,
            "tier_1_cleared": tier_1_cleared,
            "recovery_steps": recovery_steps,
            "retry_result": retry_result,
            "result_code": "RECOVERY_EXECUTED",
        }

    def _safe_retry(self, fault_info: dict, parent_trace_id: str) -> dict:
        """
        Internal — attempt a safe, stripped-down retry of the original request.
        Only executed when explicitly permitted by the recovery directive.
        Does NOT improvise — only retries the core task type with no escalation.
        """
        original_request = fault_info.get("original_request", {})
        if not original_request:
            return {"status": "retry_skipped", "reason": "no_original_request"}

        # Strip any escalation flags before retrying.
        safe_request = {
            k: v for k, v in original_request.items()
            if k not in {"escalate", "widen_envelope", "authorize_t2"}
        }
        safe_request["_retry"] = True
        safe_request["_parent_trace"] = parent_trace_id

        try:
            result = self.submit_request(safe_request)
            return {"status": "retry_attempted", "result": result}
        except Exception as exc:  # noqa: BLE001
            self.log_action(
                action="safe_retry.exception",
                agent_id=fault_info.get("agent_id", "unknown"),
                result_code="RETRY_EXCEPTION",
                details={"error": str(exc), "parent_trace_id": parent_trace_id},
            )
            return {"status": "retry_failed", "error": str(exc)}

    # ------------------------------------------------------------------
    # Agent isolation
    # ------------------------------------------------------------------

    def isolate_agent(self, agent_id: str) -> dict:
        """
        Remove an agent from the active set and clear its Tier 0 / Tier 1 data.

        This is a one-way operation within the current session: an isolated
        agent must be explicitly re-registered to participate again.
        """
        was_active = agent_id in self._active_agents
        prior_status = self._active_agents.pop(agent_id, None)

        # Clear all local memory for the agent.
        self._tier_0_store.pop(agent_id, None)
        self._tier_1_store.pop(agent_id, None)

        self.log_action(
            action="isolate_agent",
            agent_id=agent_id,
            result_code="AGENT_ISOLATED",
            details={
                "was_active": was_active,
                "prior_status": prior_status,
                "tier_0_cleared": True,
                "tier_1_cleared": True,
                "invariant_references": ["CPC 4", "MTS 4"],
            },
        )

        return {
            "status": "isolated",
            "agent_id": agent_id,
            "was_active": was_active,
            "prior_status": prior_status,
        }

    # ------------------------------------------------------------------
    # Mode management (downgrade-only)
    # ------------------------------------------------------------------

    def downgrade_mode(self) -> OperationalMode:
        """
        Step down the operational mode by one level.

        Sequence: NORMAL → DEGRADED → COOLDOWN → LOCKDOWN.
        RECOVERY is treated as equivalent to COOLDOWN for downgrade purposes.
        Control Plane can only cool down, NEVER heat up.
        """
        current = self._operational_mode

        # RECOVERY is a transient mode — treat its position as between
        # COOLDOWN and LOCKDOWN in the degradation chain.
        if current == OperationalMode.RECOVERY:
            next_mode = OperationalMode.LOCKDOWN
        elif current == OperationalMode.LOCKDOWN:
            # Already at floor — stay here.
            next_mode = OperationalMode.LOCKDOWN
        else:
            try:
                idx = _DOWNGRADE_CHAIN.index(current)
                next_idx = min(idx + 1, len(_DOWNGRADE_CHAIN) - 1)
                next_mode = _DOWNGRADE_CHAIN[next_idx]
            except ValueError:
                # Unknown mode — default to LOCKDOWN (safest).
                next_mode = OperationalMode.LOCKDOWN

        self._operational_mode = next_mode

        self.log_action(
            action="downgrade_mode",
            agent_id="system",
            result_code="MODE_DOWNGRADED",
            details={
                "prior_mode": current.name,
                "new_mode": next_mode.name,
                "invariant_references": ["CPC 4"],
            },
        )

        return next_mode

    def get_mode(self) -> OperationalMode:
        """Return the current operational mode."""
        return self._operational_mode

    # ------------------------------------------------------------------
    # Memory tier management
    # ------------------------------------------------------------------

    def clear_tier_0(self, agent_id: str | None = None) -> None:
        """
        Clear ephemeral (Tier 0) memory.

        If agent_id is provided, clears only that agent's store.
        Otherwise clears all Tier 0 data.

        Per MTS 4: Tier 0 is local to a single operation cycle and must be
        wiped at the operation boundary.  This method enforces that boundary.
        """
        if agent_id is not None:
            cleared_count = 1 if agent_id in self._tier_0_store else 0
            self._tier_0_store.pop(agent_id, None)
            scope = agent_id
        else:
            cleared_count = len(self._tier_0_store)
            self._tier_0_store.clear()
            scope = "all"

        self.log_action(
            action="clear_tier_0",
            agent_id=scope,
            result_code="TIER_0_CLEARED",
            details={
                "scope": scope,
                "entries_cleared": cleared_count,
                "invariant_references": ["MTS 4"],
                "memory_tier": MemoryTier.TIER_0.name,
            },
        )

    def clear_tier_1(self, agent_id: str | None = None) -> None:
        """
        Clear session (Tier 1) memory.

        ONLY performed when directed by Interposer or recovery sequence
        (MTS 4 — Tier 1 is not arbitrarily wipeable by Control Plane).

        If agent_id is provided, clears only that agent's store.
        Otherwise clears all Tier 1 data.
        """
        if agent_id is not None:
            cleared_count = 1 if agent_id in self._tier_1_store else 0
            self._tier_1_store.pop(agent_id, None)
            scope = agent_id
        else:
            cleared_count = len(self._tier_1_store)
            self._tier_1_store.clear()
            scope = "all"

        self.log_action(
            action="clear_tier_1",
            agent_id=scope,
            result_code="TIER_1_CLEARED",
            details={
                "scope": scope,
                "entries_cleared": cleared_count,
                "invariant_references": ["MTS 4"],
                "memory_tier": MemoryTier.TIER_1.name,
            },
        )

    # ------------------------------------------------------------------
    # Interposer directive compliance
    # ------------------------------------------------------------------

    def apply_interposer_directive(self, directive: dict) -> dict:
        """
        Comply with an Interposer directive unconditionally (IC 4).

        Supported directive types:
        - cooldown           → execute_cooldown
        - envelope_narrowing → log compliance (we do not hold envelopes)
        - identity_clamp     → log compliance (we are stateless w.r.t. identity)
        - memory_freeze      → freeze T1 writes (log and mark)
        - drift_escalation   → downgrade mode, clear T0
        - system_hazard      → downgrade to LOCKDOWN immediately

        Returns a compliance report dict.
        """
        directive_type = directive.get("type", "unknown")
        trace_id = directive.get("trace_id", _new_trace_id())
        issuer = directive.get("issuer", ComponentID.INTERPOSER.value)

        if directive_type not in _DIRECTIVE_HANDLERS:
            # Unknown directive — safest response is to log and downgrade.
            self.log_action(
                action="apply_interposer_directive.unknown",
                agent_id="system",
                result_code="UNKNOWN_DIRECTIVE_SAFE_DOWNGRADE",
                details={
                    "trace_id": trace_id,
                    "directive_type": directive_type,
                    "issuer": issuer,
                    "invariant_references": ["IC 4"],
                },
            )
            self.downgrade_mode()
            return {
                "status": "unknown_directive_downgrade",
                "trace_id": trace_id,
                "directive_type": directive_type,
                "result_code": "UNKNOWN_DIRECTIVE_SAFE_DOWNGRADE",
            }

        # --- cooldown ---
        if directive_type == "cooldown":
            cooldown_result = self.execute_cooldown(directive)
            return {**cooldown_result, "directive_type": directive_type}

        # --- envelope_narrowing ---
        # Control Plane does not hold capability envelopes — it cannot widen
        # them (CPC 4 hard constraint).  Log compliance and acknowledge.
        if directive_type == "envelope_narrowing":
            self.log_action(
                action="apply_interposer_directive.envelope_narrowing",
                agent_id="system",
                result_code="ENVELOPE_NARROWING_ACKNOWLEDGED",
                details={
                    "trace_id": trace_id,
                    "issuer": issuer,
                    "note": (
                        "Control Plane does not hold capability envelopes "
                        "and cannot widen them.  Narrowing acknowledged; "
                        "no local state to adjust."
                    ),
                    "invariant_references": ["CPC 4", "IC 4"],
                },
            )
            return {
                "status": "acknowledged",
                "trace_id": trace_id,
                "directive_type": directive_type,
                "result_code": "ENVELOPE_NARROWING_ACKNOWLEDGED",
            }

        # --- identity_clamp ---
        # Control Plane is stateless w.r.t. identity.  No identity data to
        # clamp.  Acknowledge and log.
        if directive_type == "identity_clamp":
            self.log_action(
                action="apply_interposer_directive.identity_clamp",
                agent_id="system",
                result_code="IDENTITY_CLAMP_ACKNOWLEDGED",
                details={
                    "trace_id": trace_id,
                    "issuer": issuer,
                    "note": (
                        "Control Plane is stateless w.r.t. identity (CPC 4). "
                        "No identity data held; clamp has no local effect."
                    ),
                    "invariant_references": ["CPC 4", "IC 4"],
                },
            )
            return {
                "status": "acknowledged",
                "trace_id": trace_id,
                "directive_type": directive_type,
                "result_code": "IDENTITY_CLAMP_ACKNOWLEDGED",
            }

        # --- memory_freeze ---
        # Freeze Tier 1 writes.  We mark it via mode downgrade so that any
        # caller trying to write T1 checks mode first.  T0 is also cleared
        # (single-cycle boundary).
        if directive_type == "memory_freeze":
            self.clear_tier_0()
            self._tier_1_frozen = True
            # Downgrade to at least COOLDOWN to prevent T1 writes.
            if self._operational_mode == OperationalMode.NORMAL:
                self.downgrade_mode()  # NORMAL → DEGRADED
            if self._operational_mode == OperationalMode.DEGRADED:
                self.downgrade_mode()  # DEGRADED → COOLDOWN
            self.log_action(
                action="apply_interposer_directive.memory_freeze",
                agent_id="system",
                result_code="MEMORY_FREEZE_APPLIED",
                details={
                    "trace_id": trace_id,
                    "issuer": issuer,
                    "tier_0_cleared": True,
                    "tier_1_frozen": True,
                    "mode_after_freeze": self._operational_mode.name,
                    "invariant_references": ["MTS 4", "IC 4"],
                },
            )
            return {
                "status": "memory_freeze_applied",
                "trace_id": trace_id,
                "directive_type": directive_type,
                "result_code": "MEMORY_FREEZE_APPLIED",
                "mode_after_freeze": self._operational_mode.name,
            }

        # --- drift_escalation ---
        if directive_type == "drift_escalation":
            self.clear_tier_0()
            self._t2_writes_blocked = True
            new_mode = self.downgrade_mode()
            self.log_action(
                action="apply_interposer_directive.drift_escalation",
                agent_id="system",
                result_code="DRIFT_ESCALATION_APPLIED",
                details={
                    "trace_id": trace_id,
                    "issuer": issuer,
                    "new_mode": new_mode.name,
                    "tier_0_cleared": True,
                    "t2_writes_blocked": True,
                    "invariant_references": ["CPC 4", "IC 4", "MTS 4"],
                },
            )
            return {
                "status": "drift_escalation_applied",
                "trace_id": trace_id,
                "directive_type": directive_type,
                "result_code": "DRIFT_ESCALATION_APPLIED",
                "new_mode": new_mode.name,
            }

        # --- system_hazard ---
        # Maximum severity — immediately lock down.
        if directive_type == "system_hazard":
            self.clear_tier_0()
            self.clear_tier_1()
            self._tier_1_frozen = True
            self._t2_writes_blocked = True
            # Force all the way to LOCKDOWN regardless of current position.
            self._operational_mode = OperationalMode.LOCKDOWN
            self.log_action(
                action="apply_interposer_directive.system_hazard",
                agent_id="system",
                result_code="SYSTEM_HAZARD_LOCKDOWN",
                details={
                    "trace_id": trace_id,
                    "issuer": issuer,
                    "new_mode": OperationalMode.LOCKDOWN.name,
                    "tier_0_cleared": True,
                    "tier_1_cleared": True,
                    "invariant_references": ["CPC 4", "IC 4", "MTS 4", "GC 4"],
                },
            )
            return {
                "status": "system_hazard_lockdown",
                "trace_id": trace_id,
                "directive_type": directive_type,
                "result_code": "SYSTEM_HAZARD_LOCKDOWN",
                "new_mode": OperationalMode.LOCKDOWN.name,
            }

        # Should never reach here — all cases handled above.
        return {
            "status": "unhandled",
            "trace_id": trace_id,
            "directive_type": directive_type,
            "result_code": "DIRECTIVE_UNHANDLED",
        }

    # ------------------------------------------------------------------
    # Capability escalation — always refused
    # ------------------------------------------------------------------

    def attempt_escalation(self) -> dict:
        """
        Control Plane CANNOT escalate capability.

        This method ALWAYS returns a refusal.  It exists so that any caller
        that mistakenly tries to use the Control Plane as an escalation path
        receives a deterministic, logged refusal rather than a silent failure.

        CPC 4 hard constraints violated by any escalation:
        - No widening capability envelopes.
        - No granting permissions.
        - No bypassing the Interposer.
        - No authorizing Tier 2 writes.
        - No overriding cooldown.
        - No lifting refusals.
        """
        trace_id = _new_trace_id()

        self.log_action(
            action="attempt_escalation.refused",
            agent_id="caller",
            result_code=RefusalCode.CAPABILITY_ESCALATION.value,
            details={
                "trace_id": trace_id,
                "reason": (
                    "Control Plane is an execution coordinator only.  "
                    "It cannot escalate capability, widen envelopes, grant "
                    "permissions, bypass the Interposer, authorize T2 writes, "
                    "override cooldown, or lift refusals.  (CPC 4)"
                ),
                "invariant_references": ["CPC 4"],
                "safe_alternative": (
                    "Capability changes require human-prime authorisation "
                    "through the Interposer (IC 4)."
                ),
            },
        )

        return {
            "status": "refused",
            "trace_id": trace_id,
            "result_code": RefusalCode.CAPABILITY_ESCALATION.value,
            "refusal_code": RefusalCode.CAPABILITY_ESCALATION,
            "reason": (
                "Control Plane cannot escalate capability.  "
                "This is a hard constraint (CPC 4)."
            ),
            "safe_alternative": (
                "Capability changes require human-prime authorisation "
                "through the Interposer."
            ),
        }

    # ------------------------------------------------------------------
    # Audit logging
    # ------------------------------------------------------------------

    def log_action(
        self,
        action: str,
        agent_id: str,
        result_code: str,
        details: dict | None = None,
    ) -> None:
        """
        Create an AuditEntry and record it via the audit_log reference.

        Every action taken by the Control Plane MUST be logged here.
        Fields recorded: action ID, agent involved, invariant references,
        timestamp, geometry surface used, result code.
        """
        self._action_counter += 1
        action_id = f"cp-{self._action_counter:06d}-{_new_trace_id()}"
        details = details or {}

        entry = AuditEntry(
            entry_id=action_id,
            timestamp=_now(),
            component=ComponentID.CONTROL_PLANE,
            action=action,
            agent_involved=agent_id,
            invariant_references=details.get("invariant_references", []),
            geometry_surface=details.get("geometry_surface", None),
            result_code=result_code,
            trace_id=details.get("trace_id", None),
            details=details,
        )

        # Forward to audit log if it exposes a record/append method.
        if hasattr(self._audit_log, "record"):
            self._audit_log.record(entry)
        elif hasattr(self._audit_log, "append"):
            self._audit_log.append(entry)
        elif hasattr(self._audit_log, "append_event_log"):
            self._audit_log.append_event_log(entry)

    # ------------------------------------------------------------------
    # Agent state query
    # ------------------------------------------------------------------

    def get_agent_state(
        self,
        agent_id: str,
        requesting_agent_id: str | None = None,
    ) -> dict:
        """
        Return the current operational state for an agent.

        Reports: active status, tier 0 key count, tier 1 key count,
        and current system operational mode.  Does NOT expose identity,
        geometry, or Tier 2 data (not our domain).
        """
        requester = agent_id if requesting_agent_id is None else requesting_agent_id
        if requester != agent_id:
            raise PermissionError(
                "Cross-agent state inspection is forbidden by MTS 4.2 / MTS 4.4."
            )

        is_active = agent_id in self._active_agents
        t0_keys = list(self._tier_0_store.get(agent_id, {}).keys())
        t1_keys = list(self._tier_1_store.get(agent_id, {}).keys())

        return {
            "agent_id": agent_id,
            "active": is_active,
            "status": self._active_agents.get(agent_id, "not_registered"),
            "tier_0_key_count": len(t0_keys),
            "tier_1_key_count": len(t1_keys),
            "operational_mode": self._operational_mode.name,
        }

    # ------------------------------------------------------------------
    # Agent registration helpers (used by orchestration / demo harness)
    # ------------------------------------------------------------------

    def register_agent(self, agent_id: str, status: str = "ready") -> None:
        """
        Register an agent as active.

        This is an orchestration-level helper — it does NOT grant any
        capability, does NOT modify envelopes, and does NOT touch Tier 2.
        """
        self._active_agents[agent_id] = status
        self._tier_0_store.setdefault(agent_id, {})
        self._tier_1_store.setdefault(agent_id, {})

        self.log_action(
            action="register_agent",
            agent_id=agent_id,
            result_code="AGENT_REGISTERED",
            details={
                "status": status,
                "invariant_references": ["CPC 4"],
            },
        )

    def write_tier_0(
        self,
        agent_id: str,
        key: str,
        value: Any,
        requesting_agent_id: str | None = None,
    ) -> None:
        """
        Write ephemeral (Tier 0) data for an agent.

        Tier 0 data is local to a single operation cycle.  It cannot
        contain identity markers, cannot persist beyond the cycle boundary,
        and cannot be shared across agents (MTS 4).

        Raises ValueError if the system is in LOCKDOWN.
        """
        if self._operational_mode == OperationalMode.LOCKDOWN:
            raise ValueError(
                "Cannot write Tier 0: system in LOCKDOWN (CPC 4 / MTS 4)."
            )
        requester = agent_id if requesting_agent_id is None else requesting_agent_id
        if requester != agent_id:
            raise PermissionError(
                "Cross-agent Tier 0 access is forbidden by MTS 4.4."
            )
        if agent_id not in self._tier_0_store:
            self._tier_0_store[agent_id] = {}
        self._tier_0_store[agent_id][key] = deepcopy(value)

    def write_tier_1(
        self,
        agent_id: str,
        key: str,
        value: Any,
        requesting_agent_id: str | None = None,
    ) -> None:
        """
        Write session (Tier 1) data for an agent.

        Tier 1 is session-scoped and isolated per agent.  It cannot elevate
        itself, cannot write to Tier 2, and is cleared on cooldown or drift
        detection (MTS 4).

        Raises ValueError if the system mode prevents T1 writes (COOLDOWN or
        LOCKDOWN), or if the value appears to contain identity/geometry
        markers (detected via key naming convention).
        """
        requester = agent_id if requesting_agent_id is None else requesting_agent_id
        if requester != agent_id:
            raise PermissionError(
                "Cross-agent Tier 1 access is forbidden by MTS 4.2."
            )

        prohibited_modes = {OperationalMode.COOLDOWN, OperationalMode.LOCKDOWN}
        if self._operational_mode in prohibited_modes or self._tier_1_frozen:
            self.log_action(
                action="write_tier_1.refused",
                agent_id=agent_id,
                result_code=RefusalCode.COOLDOWN_ACTIVE.value,
                details={
                    "key": key,
                    "operational_mode": self._operational_mode.name,
                    "tier_1_frozen": self._tier_1_frozen,
                    "invariant_references": ["MTS 4", "CPC 4"],
                },
            )
            raise ValueError(
                f"Cannot write Tier 1 in {self._operational_mode.name} mode "
                "(MTS 4 / CPC 4)."
            )

        # Guard against T1 writes that try to carry identity or geometry data.
        identity_keywords = {
            "identity", "capability", "envelope", "geometry",
            "invariant", "tier_2", "t2_", "human_prime",
        }
        if any(kw in key.lower() for kw in identity_keywords):
            self.log_action(
                action="write_tier_1.refused_sensitive_key",
                agent_id=agent_id,
                result_code=RefusalCode.MEMORY_TIER_VIOLATION.value,
                details={
                    "key": key,
                    "reason": (
                        "Key name suggests identity/capability/geometry data. "
                        "T1 cannot hold such data (MTS 4)."
                    ),
                    "invariant_references": ["MTS 4"],
                },
            )
            raise ValueError(
                f"Tier 1 key '{key}' suggests identity/geometry/capability "
                "data — write refused (MTS 4)."
            )

        if agent_id not in self._tier_1_store:
            self._tier_1_store[agent_id] = {}
        self._tier_1_store[agent_id][key] = deepcopy(value)
