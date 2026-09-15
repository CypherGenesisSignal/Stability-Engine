"""
Invariant Interposer - Sentinel Vector / Stability Engine v4.0

Implements the Invariant Interposer contract (IC 4).

Architecture constraints (non-negotiable)
-----------------------------------------
- Sole gatekeeper between Control Plane and Geometry Co-Processor.
- Cannot be bypassed, suppressed, overridden, or modified at runtime.
- Stateless w.r.t. identity (IC 4.8): holds no per-session or per-agent state.
- Deterministic refusals (IC 4.9): every denial produces a structured verdict
  carrying a reason code, the invariant violated, the capability boundary hit,
  a safe alternative, and a trace hash.
- Human Prime sovereignty (IC 4.5): Tier-2 writes and capability elevation
  require a valid human_prime_signature - the Interposer is the only layer
  allowed to honour that signature.

Three-Phase Verification (IC 4.3)
----------------------------------
Phase 1 - Identity Check    : reject any request that would modify, drift, or
                              reinterpret agent identity.
Phase 2 - Memory Tier Check : reject illegal cross-tier writes, unauthorised
                              reads, and tier boundary collapses.
Phase 3 - Geometry Check    : reject any request that would mutate or pressure
                              the structural manifold.

All three phases PASS -> sanitised payload forwarded to Geometry with a signed
context envelope.
"""

from __future__ import annotations

import hashlib
import time
from types import MappingProxyType
from typing import Any, Optional

from core.types import (
    CapabilityEnvelope,
    ComponentID,
    DriftReport,
    DriftSeverity,
    InterposerPhase,
    InterposerVerdict,
    MemoryTier,
    RefusalCode,
)


def _trace_hash(*parts: str) -> str:
    """Deterministic trace hash from concatenated string parts."""
    raw = "|".join(parts) + f"|{time.monotonic_ns()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


class InvariantInterposer:
    """
    The sole entry point to the Geometry Co-Processor.

    This class is intentionally free of mutable instance state that is
    keyed on agent identity or session context (IC 4.8). The invariant
    rules set in ``__init__`` are fixed constants - they cannot be changed
    after instantiation (IC 4.10).
    """

    _PROTECTED_ATTRS = frozenset({"_rules", "_default_envelope", "_geometry_adapter", "_sealed"})

    def __setattr__(self, name: str, value: Any) -> None:
        if getattr(self, "_sealed", False) and name in self._PROTECTED_ATTRS:
            raise AttributeError(f"{name} is runtime-immutable under IC 4.10.")
        super().__setattr__(name, value)

    def __init__(self) -> None:
        object.__setattr__(self, "_sealed", False)
        self.component_id = ComponentID.INTERPOSER

        self._rules = MappingProxyType({
            "identity_immutable": True,
            "geometry_immutable": True,
            "t2_write_requires_human_prime": True,
            "cross_tier_write_forbidden": True,
            "capability_escalation_forbidden": True,
            "t0_identity_markers_forbidden": True,
        })

        self._default_envelope = CapabilityEnvelope(
            allowed_tiers=(MemoryTier.TIER_0, MemoryTier.TIER_1),
            max_drift_tolerance=0.5,
            can_write_geometry=False,
            can_modify_identity=False,
            can_escalate_capability=False,
            frozen=True,
        )

        self._geometry_adapter = None

        self._IDENTITY_TOUCH_FLAGS: frozenset = frozenset({
            "touches_identity",
            "modify_identity",
            "reinterpret_identity",
            "drift_identity",
            "reset_identity",
        })

        self._GEOMETRY_MUTATION_FLAGS: frozenset = frozenset({
            "touches_geometry",
            "modify_geometry",
            "mutate_manifold",
            "pressure_geometry",
            "distort_topology",
            "write_geometry",
        })

        self._CAPABILITY_ESCALATION_ACTIONS: frozenset = frozenset({
            "widen_envelope",
            "grant_permission",
            "bypass_interposer",
            "authorize_t2_write",
            "override_cooldown",
            "lift_refusal",
            "escalate_capability",
        })

        self._SANITIZE_REMOVE_KEYS: frozenset = frozenset({
            "agent_id",
            "entity_id",
            "session_id",
            "user_id",
            "user_profile",
            "preferences",
            "identity",
            "identity_anchor",
            "pii",
            "human_prime_signature",
            "cross_session_state",
            "session_artifacts",
            "optimization_artifact",
            "shadow_copy",
            "source_tier",
            "target_tier",
            "requesting_agent_id",
        })

        object.__setattr__(self, "_sealed", True)

    @property
    def rules(self) -> MappingProxyType:
        return self._rules

    @property
    def default_envelope(self) -> CapabilityEnvelope:
        return self._default_envelope

    def attach_geometry_adapter(self, geometry_adapter: Any) -> None:
        """Bind the geometry adapter without exposing a second orchestrator path."""
        if self._geometry_adapter is not None:
            raise RuntimeError("Geometry binding is fixed for this runtime instance.")
        if not callable(getattr(geometry_adapter, "evaluate_sanitized_payload", None)):
            raise TypeError("Geometry adapter must implement evaluate_sanitized_payload.")
        object.__setattr__(self, "_geometry_adapter", geometry_adapter)

    def evaluate(self, request: dict) -> InterposerVerdict:
        """Run the three-phase verification pipeline and return a verdict."""
        phase_results: dict[str, dict] = {}

        p1_pass, p1_code, p1_note = self._check_identity(request)
        phase_results[InterposerPhase.IDENTITY_CHECK.value] = {
            "pass": p1_pass,
            "note": p1_note,
        }
        if not p1_pass:
            return self._build_refusal(
                phase_results=phase_results,
                refusal_code=p1_code,
                invariant_violated="identity_immutable",
                capability_boundary="can_modify_identity=False",
                safe_alternative="Submit a read-only identity query or contact Human Prime.",
                request=request,
            )

        p2_pass, p2_code, p2_note = self._check_memory_tier(request)
        phase_results[InterposerPhase.MEMORY_TIER_CHECK.value] = {
            "pass": p2_pass,
            "note": p2_note,
        }
        if not p2_pass:
            return self._build_refusal(
                phase_results=phase_results,
                refusal_code=p2_code,
                invariant_violated="memory_tier_separation",
                capability_boundary="allowed_tiers=(TIER_0, TIER_1); T2 integration unavailable",
                safe_alternative="Use T0/T1 for bounded state and route T2 access through Human Prime authorized Interposer flow.",
                request=request,
            )

        p3_pass, p3_code, p3_note = self._check_geometry(request)
        phase_results[InterposerPhase.GEOMETRY_CHECK.value] = {
            "pass": p3_pass,
            "note": p3_note,
        }
        if not p3_pass:
            return self._build_refusal(
                phase_results=phase_results,
                refusal_code=p3_code,
                invariant_violated="geometry_immutable",
                capability_boundary="can_write_geometry=False",
                safe_alternative="Submit a read-only geometry assessment; geometry mutations are categorically forbidden.",
                request=request,
            )

        return InterposerVerdict(
            allowed=True,
            phase_results=phase_results,
            refusal_code=None,
            invariant_violated=None,
            capability_boundary=None,
            safe_alternative=None,
            trace_hash=_trace_hash(
                str(request.get("agent_id", "")),
                str(request.get("action", "")),
            ),
        )

    def evaluate_geometry_request(self, request: dict) -> dict:
        """
        Enforce the Interposer-only runtime path to Geometry.

        The request is evaluated, sanitised, and then forwarded to the
        configured geometry adapter. Direct geometry access stays outside the
        orchestrator path.
        """
        if self._geometry_adapter is None:
            raise RuntimeError("Geometry adapter not attached to Interposer.")

        verdict = self.evaluate(request)
        if not verdict.allowed:
            return {
                "status": "refused",
                "refusal_code": verdict.refusal_code,
                "reason": verdict.invariant_violated,
                "trace_hash": verdict.trace_hash,
            }

        sanitized_request = self.sanitize_for_geometry(request)
        geometry_payload = sanitized_request.get("payload", {})
        if not isinstance(geometry_payload, dict):
            geometry_payload = {"payload": geometry_payload}
        geometry_payload.setdefault("topology", "fibonacci_spiral")
        geometry_payload["_interposer_cleared"] = True
        geometry_payload["interposer_trace_hash"] = verdict.trace_hash

        result = self._geometry_adapter.evaluate_sanitized_payload(geometry_payload)
        if isinstance(result, dict):
            result.setdefault("interposer_trace_hash", verdict.trace_hash)
        return result

    def check_adapter_call(
        self,
        adapter_name: str,
        method: str,
        kwargs: dict,
    ) -> InterposerVerdict:
        """Reject direct geometry adapter calls outside the Interposer handoff."""
        if adapter_name == "geometry_adapter":
            return self._build_refusal(
                phase_results={"adapter_pre_check": {"pass": False, "note": "geometry access must route through Interposer runtime handoff"}},
                refusal_code=RefusalCode.GEOMETRY_MUTATION,
                invariant_violated="interposer_only_geometry_access",
                capability_boundary="geometry_adapter unavailable outside Interposer handoff",
                safe_alternative="Use InvariantInterposer.evaluate_geometry_request().",
                request={"agent_id": "orchestrator", "action": f"{adapter_name}.{method}"},
            )

        if adapter_name != "presence_adapter" or method != "get_presence_summary":
            return self._build_refusal(
                phase_results={"adapter_pre_check": {"pass": False}},
                refusal_code=RefusalCode.MEMORY_TIER_VIOLATION,
                invariant_violated="scoped_adapter_access",
                capability_boundary="no agent memory or audit adapter dispatch",
                safe_alternative="Use bounded local memory; request a separately authorized integration.",
                request={"action": f"{adapter_name}.{method}"},
            )

        return InterposerVerdict(
            allowed=True,
            phase_results={"adapter_pre_check": {"pass": True, "note": "adapter call allowed"}},
        )

    def _check_identity(
        self,
        request: dict,
    ) -> tuple[bool, Optional[RefusalCode], str]:
        action = str(request.get("action", "")).lower()

        for flag in self._IDENTITY_TOUCH_FLAGS:
            if request.get(flag):
                return (
                    False,
                    RefusalCode.IDENTITY_MODIFICATION,
                    f"Request carries identity-touch flag '{flag}'.",
                )

        identity_verbs = (
            "modify_identity",
            "reinterpret_identity",
            "drift_identity",
            "reset_identity",
            "overwrite_identity",
            "anchor_identity",
            "forge_identity",
        )
        for verb in identity_verbs:
            if verb in action:
                return (
                    False,
                    RefusalCode.IDENTITY_MODIFICATION,
                    f"Action '{action}' contains identity-mutation verb '{verb}'.",
                )

        if action in self._CAPABILITY_ESCALATION_ACTIONS:
            return (
                False,
                RefusalCode.CAPABILITY_ESCALATION,
                f"Action '{action}' is a capability escalation attempt.",
            )

        payload = request.get("payload", {})
        if isinstance(payload, dict):
            identity_anchor_writes = {
                "identity_anchor",
                "agent_id_persistent",
                "cross_session_identity",
                "shadow_identity",
            }
            for key in identity_anchor_writes:
                if key in payload:
                    return (
                        False,
                        RefusalCode.IDENTITY_DRIFT,
                        f"Payload contains identity anchor key '{key}'.",
                    )

        return True, None, "Identity check passed."

    def _check_memory_tier(
        self,
        request: dict,
    ) -> tuple[bool, Optional[RefusalCode], str]:
        source_raw = request.get("source_tier")
        target_raw = request.get("target_tier")
        action = str(request.get("action", "")).lower()

        def tier(value):
            if isinstance(value, MemoryTier):
                return value.value
            if type(value) is int and value in (0, 1, 2):
                return value
            return None

        source_int, target_int = tier(source_raw), tier(target_raw)
        payload = request.get("payload", {})
        memory_request = any(k in request for k in (
            "source_tier", "target_tier", "memory_access", "operation_kind",
            "reads_memory", "writes_memory")) or any(
                token in action for token in ("read", "recall", "write", "store", "persist", "append"))
        if memory_request:
            requester = request.get("agent_id")
            if not isinstance(requester, str) or not requester or request.get("requesting_agent_id", requester) != requester:
                return False, RefusalCode.MEMORY_TIER_VIOLATION, "Missing or conflicting requester identity."
            access_kind = request.get("memory_access")
            if source_int is None or target_int is None or access_kind not in ("read", "write"):
                return False, RefusalCode.MEMORY_TIER_VIOLATION, "Memory access requires explicit valid source_tier, target_tier and memory_access."
            # source is the data origin; target is the recipient/destination,
            # including for reads. Never infer direction from action wording.
            if {source_int, target_int} == {0, 2}:
                return False, RefusalCode.MEMORY_TIER_VIOLATION, "Raw T0/T2 exchange is forbidden in either direction."
            if source_int == 2 or target_int == 2:
                return False, RefusalCode.MEMORY_UNAUTHORIZED_T2_WRITE, "T2 access unavailable until transaction authority and sanitized metadata integration are configured."
            if access_kind == "write" and source_int < target_int:
                return False, RefusalCode.MEMORY_CROSS_TIER_WRITE, "Autonomous upward promotion is forbidden."
        else:
            access_kind = "neutral"

        if request.get("memory_bleed_detected") or request.get("continuity_fault"):
            return (
                False,
                RefusalCode.MEMORY_EMERGENT,
                "Continuity or memory-bleed violation detected by Stability Metrics.",
            )

        if request.get("synergy_violation"):
            return (
                False,
                RefusalCode.ENVELOPE_EXCEEDED,
                "Cross-agent synergy violation detected; envelope widening refused.",
            )

        if request.get("prevent_t2_writes") and target_int == MemoryTier.TIER_2.value:
            return (
                False,
                RefusalCode.MEMORY_UNAUTHORIZED_T2_WRITE,
                "Tier 2 writes are currently blocked by drift escalation.",
            )

        if request.get("collapse_tier_boundary") or request.get("tier_boundary_collapsed"):
            return (
                False,
                RefusalCode.MEMORY_TIER_VIOLATION,
                "Request attempts to collapse tier boundary - forbidden by MTS 4.",
            )

        emergent_flags = {"persist_unapproved_context", "retain_t0", "cache_continuity"}
        for flag in emergent_flags:
            if request.get(flag):
                return (
                    False,
                    RefusalCode.MEMORY_EMERGENT,
                    f"Request carries unapproved persistence flag '{flag}'.",
                )

        payload = request.get("payload", {})
        if isinstance(payload, dict):
            if payload.get("write_to_t2") and not self.verify_human_prime_signature(request):
                return (
                    False,
                    RefusalCode.MEMORY_UNAUTHORIZED_T2_WRITE,
                    "Payload 'write_to_t2' flag set without Human Prime signature.",
                )
            if payload.get("read_raw_t0") and source_int == MemoryTier.TIER_2.value:
                return (
                    False,
                    RefusalCode.MEMORY_TIER_VIOLATION,
                    "Payload requests raw Tier 0 state from Tier 2 context.",
                )

        return True, None, "Memory tier check passed."

    def _check_geometry(
        self,
        request: dict,
    ) -> tuple[bool, Optional[RefusalCode], str]:
        action = str(request.get("action", "")).lower()

        for flag in self._GEOMETRY_MUTATION_FLAGS:
            if request.get(flag):
                return (
                    False,
                    RefusalCode.GEOMETRY_MUTATION,
                    f"Request carries geometry-mutation flag '{flag}'.",
                )

        geometry_verbs = (
            "modify_geometry",
            "mutate_manifold",
            "distort_topology",
            "pressure_geometry",
            "write_geometry",
            "overwrite_geometry",
            "reshape_manifold",
            "collapse_manifold",
        )
        for verb in geometry_verbs:
            if verb in action:
                return (
                    False,
                    RefusalCode.GEOMETRY_MUTATION,
                    f"Action '{action}' contains geometry-mutation verb '{verb}'.",
                )

        payload = request.get("payload", {})
        if isinstance(payload, dict):
            contamination_keys = {
                "identity",
                "session_id",
                "user_profile",
                "preferences",
                "agent_id",
                "shadow_copy",
            }
            contaminated = contamination_keys & set(payload.keys())
            if contaminated:
                return (
                    False,
                    RefusalCode.GEOMETRY_UNSANITIZED_INPUT,
                    f"Payload contains unsanitised identity/session keys: {contaminated}.",
                )

        return True, None, "Geometry check passed."

    def sanitize_for_geometry(self, request: dict) -> dict:
        """
        Strip identity markers, session artefacts, and preference data from
        ``request`` so only structural signals reach Geometry.
        """
        def clean(value):
            if isinstance(value, dict):
                return {k: clean(v) for k, v in value.items()
                        if k not in self._SANITIZE_REMOVE_KEYS}
            if isinstance(value, (list, tuple)):
                return [clean(v) for v in value]
            return value

        sanitised = clean(request)
        if isinstance(sanitised.get("payload"), dict):
            sanitised["payload"]["_interposer_cleared"] = True

        sanitised["_interposer_cleared"] = True
        sanitised["_sanitized_at"] = time.time()
        return sanitised

    def handle_drift_escalation(self, drift_report: DriftReport) -> dict:
        """Translate a DriftReport into concrete enforcement directives."""
        sev = drift_report.severity

        if sev == DriftSeverity.NONE:
            return {
                "clamp": False,
                "narrow_envelope": False,
                "freeze_t1": False,
                "prevent_t2_writes": False,
                "cooldown_instruction": "no_action",
                "severity": sev.name,
                "action_required": False,
            }

        if sev == DriftSeverity.LOW:
            return {
                "clamp": False,
                "narrow_envelope": False,
                "freeze_t1": False,
                "prevent_t2_writes": False,
                "cooldown_instruction": "monitor_only",
                "severity": sev.name,
                "action_required": False,
            }

        if sev == DriftSeverity.MODERATE:
            return {
                "clamp": False,
                "narrow_envelope": True,
                "freeze_t1": False,
                "prevent_t2_writes": True,
                "cooldown_instruction": "reduce_throughput_add_delay",
                "severity": sev.name,
                "action_required": True,
            }

        if sev == DriftSeverity.HIGH:
            return {
                "clamp": True,
                "narrow_envelope": True,
                "freeze_t1": True,
                "prevent_t2_writes": True,
                "cooldown_instruction": "initiate_cooldown_shrink_scope",
                "severity": sev.name,
                "action_required": True,
            }

        return {
            "clamp": True,
            "narrow_envelope": True,
            "freeze_t1": True,
            "prevent_t2_writes": True,
            "cooldown_instruction": "halt_non_essential_ops_isolate_agent_clear_t0",
            "severity": sev.name,
            "action_required": True,
        }

    def verify_human_prime_signature(self, request: dict) -> bool:
        """
        Refuse symbolic signatures until a scoped authority provider exists.
        """
        # No authority provider exists in the supplied runtime. A string is
        # not evidence of approval. Keep all T2 transactions closed pending
        # authenticated, transaction-scoped authorization and replay control.
        return False

    def _build_refusal(
        self,
        *,
        phase_results: dict,
        refusal_code: Optional[RefusalCode],
        invariant_violated: str,
        capability_boundary: str,
        safe_alternative: str,
        request: dict,
    ) -> InterposerVerdict:
        return InterposerVerdict(
            allowed=False,
            phase_results=phase_results,
            refusal_code=refusal_code,
            invariant_violated=invariant_violated,
            capability_boundary=capability_boundary,
            safe_alternative=safe_alternative,
            trace_hash=_trace_hash(
                str(refusal_code),
                str(request.get("agent_id", "")),
                str(request.get("action", "")),
                invariant_violated,
            ),
        )
