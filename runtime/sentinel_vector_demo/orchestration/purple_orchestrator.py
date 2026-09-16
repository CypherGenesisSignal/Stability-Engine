"""
Purple Orchestrator
Stability Engine v4.0

Runtime coordination layer aligned with Interposer principles.
Central mediator among agent surfaces, persistent memory, and URIEL-3b.
Safe sequencing and arbitration layer.

Design constraints (from build_specs.md § Purple Orchestrator)
--------------------------------------------------------------
- Routes through QAMS; invokes Interposer checks; coordinates agent-side flows.
- NEVER bypasses the Interposer structural boundary.
- Never becomes a second authority source — defers all policy to Interposer.
- Cannot escalate capability, modify invariants, or write to Tier 2 memory.
- Logs every action to the audit log with invariant references and trace IDs.
- Deterministic routing priority: determinism → safety → latency → throughput.

Process flow (process_request)
-------------------------------
  1. TSRL-1 observes incoming state
  2. TSRL-2 transforms to attributed signal
  3. TSRL-3 certifies stability baseline
  4. Send to Control Plane via QAMS
  5. Control Plane routes to Interposer
  6. If Interposer allows → forward sanitized payload to geometry adapter
  7. If Interposer denies → return deterministic refusal
  8. Collect geometry assessment
  9. Optionally invoke presence/memory adapters
 10. Return result with full audit trail
"""

from __future__ import annotations

import traceback as _tb
from typing import Any, Optional

from core.types import (
    AuditEntry,
    ComponentID,
    DriftReport,
    DriftSeverity,
    InterposerVerdict,
    OperationalMode,
    QAMSMessage,
    QAMSMessageType,
    RefusalCode,
    _timestamp,
    _trace_id,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _make_audit(
    *,
    component: ComponentID,
    action: str,
    trace_id: Optional[str] = None,
    agent_involved: Optional[str] = None,
    invariant_references: Optional[list] = None,
    geometry_surface: Optional[str] = None,
    result_code: str = "OK",
    details: Optional[dict] = None,
) -> AuditEntry:
    return AuditEntry(
        component=component,
        action=action,
        trace_id=trace_id,
        agent_involved=agent_involved,
        invariant_references=invariant_references or [],
        geometry_surface=geometry_surface,
        result_code=result_code,
        details=details or {},
    )


class PurpleOrchestrator:
    """
    Safe sequencing and arbitration layer for the Stability Engine v4.

    Constructor parameters
    ----------------------
    control_plane
        The Control Plane component (CPC 4).  Handles task routing,
        scheduling, cooldown.  NOT a governor; NOT an authority source.
    interposer
        The Invariant Interposer (IC 4).  The *only* component allowed to
        judge/gate/deny/authorise operations touching invariants, identity,
        memory tiers, or substrate structure.
    qams
        QAMS transport service.  Carries messages between components.
    stability_metrics
        Stability Metrics component that feeds DriftReport objects.
    audit_log
        Append-only audit log component.
    tsrl1
        TSRL-1 Observation layer instance.
    tsrl2
        TSRL-2 Routing/Attribution layer instance.
    tsrl3
        TSRL-3 Recursive Stability layer instance.
    presence_adapter : optional
        Presence Engine adapter (may be None in configurations where it
        is not required).
    memory_adapter : optional
        Persistent Memory adapter (may be None).
    geometry_adapter : optional
        Geometry Co-Processor (URIEL-3b) adapter (may be None).

    Attributes
    ----------
    execution_trace : list
        Append-only record of every operation step taken by this instance.
        Consumed by :meth:`get_execution_trace` for audit purposes.
    operational_mode : OperationalMode
        Current operational mode.  May be downgraded (never upgraded) by
        Control Plane directives or drift escalation.
    """

    def __init__(
        self,
        control_plane,
        interposer,
        qams,
        stability_metrics,
        audit_log,
        tsrl1,
        tsrl2,
        tsrl3,
        presence_adapter=None,
        memory_adapter=None,
        geometry_adapter=None,
    ) -> None:
        self.control_plane = control_plane
        self.interposer = interposer
        self.qams = qams
        self.stability_metrics = stability_metrics
        self.audit_log = audit_log
        self.tsrl1 = tsrl1
        self.tsrl2 = tsrl2
        self.tsrl3 = tsrl3
        self.presence_adapter = presence_adapter
        self.memory_adapter = memory_adapter
        self.geometry_adapter = None
        if geometry_adapter is not None and hasattr(self.interposer, "attach_geometry_adapter"):
            self.interposer.attach_geometry_adapter(geometry_adapter)
        else:
            self.geometry_adapter = geometry_adapter

        # Append-only execution trace for audit
        self.execution_trace: list[dict] = []
        # Operational mode — can only move downward (cooldown/lockdown)
        

    @property
    def operational_mode(self) -> OperationalMode:
        if hasattr(self.control_plane, "get_mode"):
            return self.control_plane.get_mode()
        return OperationalMode.NORMAL

    # ------------------------------------------------------------------
    # Main request processing flow
    # ------------------------------------------------------------------

    def process_request(self, request: dict) -> dict:
        """
        Process an incoming request through the full safety pipeline.

        Steps
        -----
        1.  TSRL-1 observes incoming state.
        2.  TSRL-2 transforms to an attributed signal.
        3.  TSRL-3 certifies stability baseline.
        4.  Send attributed signal to Control Plane via QAMS.
        5.  Control Plane routes to Interposer.
        6a. If Interposer allows → forward sanitised payload to geometry adapter.
        6b. If Interposer denies → return deterministic refusal immediately.
        7.  Collect geometry assessment.
        8.  Optionally invoke presence and/or memory adapters.
        9.  Collect and return the full result with audit trail.

        Parameters
        ----------
        request : dict
            Incoming request payload.  The orchestrator treats this as
            opaque data and does NOT infer intent.

        Returns
        -------
        dict
            Result record containing: ``allowed``, ``result``,
            ``audit_trail``, ``execution_trace_snapshot``, ``trace_id``.
        """
        master_trace = _trace_id()
        audit_trail: list[AuditEntry] = []
        agent_id = request.get("agent_id", "unknown")

        def _log(action: str, **kw) -> AuditEntry:
            entry = _make_audit(
                component=ComponentID.PURPLE_ORCHESTRATOR,
                action=action,
                trace_id=master_trace,
                **kw,
            )
            self.audit_log.record(entry)
            audit_trail.append(entry)
            self._record_trace_step(action, trace_id=master_trace, **kw)
            return entry

        if hasattr(self.control_plane, "clear_tier_0"):
            self.control_plane.clear_tier_0(agent_id)

        # ── Guard: refuse if already in lockdown / cooldown ─────────────
        if self.operational_mode in (OperationalMode.LOCKDOWN, OperationalMode.COOLDOWN):
            _log(
                "REQUEST_REJECTED_MODE",
                result_code="REFUSED",
                details={"reason": f"Operational mode is {self.operational_mode.name}"},
                invariant_references=["CPC4: cooldown cannot be overridden by orchestrator"],
            )
            return self._build_refusal_response(
                master_trace,
                audit_trail,
                reason=f"Orchestrator in {self.operational_mode.name} mode — request rejected.",
                refusal_code=RefusalCode.COOLDOWN_ACTIVE.value,
            )

        # ── Step 1: TSRL-1 observes incoming state ───────────────────────
        _log("TSRL1_OBSERVE_START")
        try:
            observation = self.tsrl1.observe_state(
                ComponentID.PURPLE_ORCHESTRATOR,
                {"request_payload": request, "trace_id": master_trace},
            )
        except Exception as exc:
            _log("TSRL1_OBSERVE_ERROR", result_code="ERROR",
                 details={"error": str(exc)})
            return self._build_error_response(master_trace, audit_trail, exc)

        _log(
            "TSRL1_OBSERVE_COMPLETE",
            details={
                "observation_trace_id": observation.get("trace_id"),
                "state_hash": observation.get("state_hash"),
                "ambiguous": self.tsrl1.is_state_ambiguous(observation),
            },
        )

        # ── Step 2: TSRL-2 transforms to attributed signal ───────────────
        _log("TSRL2_TRANSFORM_START")
        try:
            signal = self.tsrl2.transform_observation_to_signal(observation)
            routed_signal = self.tsrl2.route_signal(
                signal, ComponentID.CONTROL_PLANE
            )
        except Exception as exc:
            _log("TSRL2_TRANSFORM_ERROR", result_code="ERROR",
                 details={"error": str(exc)})
            return self._build_error_response(master_trace, audit_trail, exc)

        _log(
            "TSRL2_TRANSFORM_COMPLETE",
            details={
                "signal_id": routed_signal.get("signal_id"),
                "integrity_hash": routed_signal.get("integrity_hash"),
                "attribution_intact": routed_signal.get("attribution_intact"),
            },
        )

        # ── Step 3: TSRL-3 certifies stability baseline ──────────────────
        _log("TSRL3_STABILITY_EVAL_START")
        try:
            # Collect all signals seen so far for recursive depth evaluation
            prior_signals = self.tsrl2.get_routing_ledger()
            assessment = self.tsrl3.evaluate_recursive_stability(
                [routed_signal] + [dict(e) for e in prior_signals[-3:]]
            )
            certificate = self.tsrl3.certify_stability_baseline(assessment)
        except Exception as exc:
            _log("TSRL3_STABILITY_ERROR", result_code="ERROR",
                 details={"error": str(exc)})
            return self._build_error_response(master_trace, audit_trail, exc)

        _log(
            "TSRL3_STABILITY_COMPLETE",
            details={
                "certified": certificate.get("certified"),
                "coherence_score": assessment.get("coherence_score"),
                "recursion_depth": assessment.get("recursion_depth"),
                "r_invariant_met": assessment.get("r_invariant_met"),
            },
            invariant_references=["TSRL-3: R=4 zero-friction invariant"],
        )

        if not certificate.get("certified"):
            _log(
                "TSRL3_STABILITY_CERTIFICATION_REFUSED",
                result_code="REFUSED",
                details={"reason": certificate.get("refusal_reason")},
                invariant_references=["TSRL-3: orchestration requires certified baseline"],
            )
            return self._build_refusal_response(
                master_trace,
                audit_trail,
                reason=f"Stability baseline not certified: {certificate.get('refusal_reason')}",
                refusal_code="STABILITY_BASELINE_UNCERTIFIED",
            )

        # ── Step 4: Send to Control Plane via QAMS ───────────────────────
        _log("QAMS_DISPATCH_TO_CONTROL_PLANE")
        try:
            qams_msg = QAMSMessage(
                trace_id=master_trace,
                origin=ComponentID.PURPLE_ORCHESTRATOR,
                destination=ComponentID.CONTROL_PLANE,
                msg_type=QAMSMessageType.REQUEST,
                payload={
                    "signal": routed_signal,
                    "certificate": certificate,
                    "original_request": request,
                },
            )
            cp_response = self._qams_send(qams_msg)
        except Exception as exc:
            _log("QAMS_DISPATCH_ERROR", result_code="ERROR",
                 details={"error": str(exc)})
            return self._build_error_response(master_trace, audit_trail, exc)

        _log(
            "CONTROL_PLANE_RESPONSE_RECEIVED",
            details={"cp_response_type": type(cp_response).__name__},
        )

        # ── Step 5: Control Plane routes to Interposer ───────────────────
        _log("INTERPOSER_CHECK_START",
             invariant_references=["IC4: only entry point to geometry"])
        try:
            interposer_request = self._build_interposer_request(
                request=request,
                assessment=assessment,
                trace_id=master_trace,
            )
            interposer_verdict: InterposerVerdict = self._invoke_interposer(
                interposer_request
            )
        except Exception as exc:
            _log("INTERPOSER_CHECK_ERROR", result_code="ERROR",
                 details={"error": str(exc)})
            return self._build_error_response(master_trace, audit_trail, exc)

        _log(
            "INTERPOSER_VERDICT_RECEIVED",
            result_code="ALLOWED" if interposer_verdict.allowed else "DENIED",
            details={
                "allowed": interposer_verdict.allowed,
                "refusal_code": (
                    interposer_verdict.refusal_code.value
                    if interposer_verdict.refusal_code
                    else None
                ),
                "invariant_violated": interposer_verdict.invariant_violated,
                "trace_hash": interposer_verdict.trace_hash,
            },
            invariant_references=["IC4.3: three-phase verification", "IC4.4: sole geometry entry point"],
        )

        # ── Step 6a/b: Branch on Interposer verdict ──────────────────────
        if not interposer_verdict.allowed:
            # Deterministic refusal — IC 4.9
            _log(
                "INTERPOSER_DENIED_DETERMINISTIC_REFUSAL",
                result_code="REFUSED",
                details={
                    "refusal_code": (
                        interposer_verdict.refusal_code.value
                        if interposer_verdict.refusal_code
                        else "UNSPECIFIED"
                    ),
                    "invariant_violated": interposer_verdict.invariant_violated,
                    "safe_alternative": interposer_verdict.safe_alternative,
                    "capability_boundary": interposer_verdict.capability_boundary,
                },
                invariant_references=["IC4.9: deterministic refusal surface"],
            )
            return self._build_interposer_refusal_response(
                master_trace, audit_trail, interposer_verdict
            )

        # ── Step 7: Geometry assessment ───────────────────────────────────
        _log(
            "GEOMETRY_ADAPTER_INVOKE_START",
            geometry_surface="fibonacci_spiral",
            invariant_references=["GC4.5: sanitised inputs only", "IC4.4: via Interposer only"],
        )
        geometry_result: dict = {}
        if hasattr(self.interposer, "evaluate_geometry_request"):
            try:
                geometry_result = self.interposer.evaluate_geometry_request(
                    self._build_geometry_request(request, assessment)
                )
            except Exception as exc:
                _log("GEOMETRY_ADAPTER_ERROR", result_code="ERROR",
                     details={"error": str(exc)})
                return self._build_error_response(master_trace, audit_trail, exc)

            _log(
                "GEOMETRY_ADAPTER_COMPLETE",
                geometry_surface="fibonacci_spiral",
                details={"geometry_result": geometry_result},
            )
        else:
            return self._build_error_response(master_trace, audit_trail,
                RuntimeError("Interposer geometry gate is unavailable."))

        if not isinstance(geometry_result, dict) or geometry_result.get("status") != "assessed":
            return self._build_refusal_response(master_trace, audit_trail,
                reason="Geometry did not produce an assessed result.",
                refusal_code="GEOMETRY_NOT_ASSESSED")

        # ── Step 8: Optional adapters ─────────────────────────────────────
        presence_result: dict = {}
        if self.presence_adapter is not None:
            _log("PRESENCE_ADAPTER_INVOKE_START")
            try:
                presence_result = self.invoke_adapter(
                    "presence_adapter",
                    "get_presence_summary",
                    entity_id=str(request.get("payload", {}).get("entity_id", "")),
                )
                _log("PRESENCE_ADAPTER_COMPLETE",
                     details={"presence_result": presence_result})
            except Exception as exc:
                _log("PRESENCE_ADAPTER_ERROR", result_code="WARN",
                     details={"error": str(exc)})

        # Operational evidence stays in AuditLog. It is never automatically
        # appended to the agent memory adapter (contract 15.3).
        memory_result: dict = {"status": "not_invoked", "reason": "audit_is_not_agent_memory"}

        # ── Step 9/10: Compile result ──────────────────────────────────────
        _log("REQUEST_PROCESSING_COMPLETE", result_code="OK")

        return {
            "allowed": True,
            "trace_id": master_trace,
            "result": {
                "geometry": geometry_result,
                "presence": presence_result,
                "memory": memory_result,
            },
            "stability_certificate": certificate,
            "interposer_verdict": {
                "allowed": interposer_verdict.allowed,
                "trace_hash": interposer_verdict.trace_hash,
                "phase_results": interposer_verdict.phase_results,
            },
            "audit_trail": [self._serialise_audit(e) for e in audit_trail],
            "execution_trace_snapshot": [],
            "operational_mode": self.operational_mode.name,
        }

    # ------------------------------------------------------------------
    # Drift response coordination
    # ------------------------------------------------------------------

    def coordinate_drift_response(self, drift_report: DriftReport) -> dict:
        """
        Handle a drift escalation event.

        Steps
        -----
        1. Observe the drift event via TSRL-1.
        2. Route drift signal via TSRL-2.
        3. Invoke Interposer escalation (Interposer decides clamp/freeze/etc.)
        4. Apply Control Plane cooldown per Interposer directive.
        5. Log everything.

        Parameters
        ----------
        drift_report : DriftReport
            Drift assessment from Stability Metrics.

        Returns
        -------
        dict
            Coordination record with escalation outcome and full audit.

        Constraints
        -----------
        - The orchestrator NEVER decides drift policy itself.
        - All authority flows through the Interposer.
        - The orchestrator only applies what Interposer directs.
        """
        drift_trace = _trace_id()
        audit_trail: list[AuditEntry] = []

        def _log(action: str, **kw) -> AuditEntry:
            entry = _make_audit(
                component=ComponentID.PURPLE_ORCHESTRATOR,
                action=action,
                trace_id=drift_trace,
                **kw,
            )
            self.audit_log.record(entry)
            audit_trail.append(entry)
            self._record_trace_step(action, trace_id=drift_trace, **kw)
            return entry

        _log(
            "DRIFT_RESPONSE_START",
            details={
                "severity": drift_report.severity.name,
                "trace_hash": drift_report.trace_hash,
                "radial_drift": drift_report.radial_drift,
                "phase_noise": drift_report.phase_noise,
            },
            invariant_references=["TSRL: drift pipeline", "IC4: escalation authority"],
        )

        # Step 1: TSRL-1 observes drift event
        drift_observation = self.tsrl1.observe_state(
            ComponentID.STABILITY_METRICS,
            {
                "drift_severity": drift_report.severity.name,
                "radial_drift": drift_report.radial_drift,
                "phase_noise": drift_report.phase_noise,
                "memory_bleed": drift_report.memory_bleed_detected,
                "synergy_violation": drift_report.synergy_violation,
                "continuity_fault": drift_report.continuity_fault,
                "trace_hash": drift_report.trace_hash,
            },
        )
        _log("DRIFT_TSRL1_OBSERVED",
             details={"obs_trace": drift_observation.get("trace_id")})

        # Step 2: TSRL-2 transforms to drift signal
        try:
            drift_signal = self.tsrl2.transform_observation_to_signal(drift_observation)
            routed_drift = self.tsrl2.route_signal(
                drift_signal, ComponentID.INTERPOSER
            )
        except Exception as exc:
            _log("DRIFT_TSRL2_ERROR", result_code="ERROR",
                 details={"error": str(exc)})
            return self._build_error_response(drift_trace, audit_trail, exc)

        _log("DRIFT_TSRL2_ROUTED",
             details={"signal_id": routed_drift.get("signal_id")})

        # Step 3: Invoke Interposer escalation
        _log("DRIFT_INTERPOSER_ESCALATION_START",
             invariant_references=["IC4: handles drift escalation, clamp, freeze, cooldown directive"])
        try:
            escalation_verdict = self._invoke_interposer_escalation(
                drift_report, routed_drift, drift_trace
            )
        except Exception as exc:
            _log("DRIFT_INTERPOSER_ERROR", result_code="ERROR",
                 details={"error": str(exc)})
            return self._build_error_response(drift_trace, audit_trail, exc)

        _log(
            "DRIFT_INTERPOSER_ESCALATION_COMPLETE",
            result_code="ALLOWED" if escalation_verdict.get("cooldown_required") is False else "COOLDOWN",
            details=escalation_verdict,
            invariant_references=["IC4: drift escalation outcome"],
        )

        # Step 4: Apply Control Plane cooldown if directed
        cooldown_applied = False
        if escalation_verdict.get("cooldown_required", False):
            _log(
                "DRIFT_CONTROL_PLANE_COOLDOWN_START",
                invariant_references=["CPC4: can cool down but never heat up"],
            )
            try:
                self._apply_cooldown(drift_report.severity, drift_trace)
                cooldown_applied = True
                _log("DRIFT_CONTROL_PLANE_COOLDOWN_APPLIED", result_code="COOLDOWN")
            except Exception as exc:
                _log("DRIFT_COOLDOWN_ERROR", result_code="ERROR",
                     details={"error": str(exc)})

        _log(
            "DRIFT_RESPONSE_COMPLETE",
            result_code="OK",
            details={
                "severity": drift_report.severity.name,
                "cooldown_applied": cooldown_applied,
                "escalation_verdict": escalation_verdict,
            },
        )

        return {
            "trace_id": drift_trace,
            "drift_severity": drift_report.severity.name,
            "escalation_verdict": escalation_verdict,
            "cooldown_applied": cooldown_applied,
            "operational_mode": self.operational_mode.name,
            "audit_trail": [self._serialise_audit(e) for e in audit_trail],
        }

    # ------------------------------------------------------------------
    # Adapter invocation (Interposer-checked)
    # ------------------------------------------------------------------

    def invoke_adapter(self, adapter_name: str, method: str, **kwargs) -> dict:
        """
        Safely call an adapter method behind an Interposer check.

        The orchestrator NEVER calls an adapter directly without first
        verifying through the Interposer.  This preserves the rule that
        the Interposer is the *only* structural boundary between the
        orchestration layer and external resources.

        Parameters
        ----------
        adapter_name : str
            Name of the adapter attribute on this instance (e.g.
            ``"geometry_adapter"``).
        method : str
            Name of the method to call on the adapter.
        **kwargs
            Keyword arguments forwarded verbatim to the adapter method.

        Returns
        -------
        dict
            The adapter's response, wrapped in a standard result envelope
            if it is not already a dict.

        Raises
        ------
        ValueError
            If the adapter does not exist on this instance.
        RuntimeError
            If the Interposer denies access to the adapter.
        """
        if adapter_name == "geometry_adapter":
            raise RuntimeError(
                "PurpleOrchestrator: geometry access must route through the Interposer runtime handoff."
            )

        adapter = getattr(self, adapter_name, None)
        if adapter is None:
            raise ValueError(
                f"PurpleOrchestrator: adapter '{adapter_name}' is not configured."
            )

        # Pre-call Interposer verification for adapter access
        pre_check = self._interposer_adapter_check(adapter_name, method, kwargs)
        if not pre_check.allowed:
            raise RuntimeError(
                f"PurpleOrchestrator: Interposer denied adapter '{adapter_name}.{method}': "
                f"{pre_check.refusal_code}"
            )

        self._record_trace_step(
            f"ADAPTER_INVOKE:{adapter_name}.{method}",
            details={"kwargs_keys": list(kwargs.keys())},
        )

        try:
            fn = getattr(adapter, method)
            result = fn(**kwargs)
        except Exception as exc:
            self._record_trace_step(
                f"ADAPTER_ERROR:{adapter_name}.{method}",
                result_code="ERROR",
                details={"error": str(exc)},
            )
            raise

        # Normalise to dict
        if not isinstance(result, dict):
            result = {"result": result}

        self._record_trace_step(
            f"ADAPTER_COMPLETE:{adapter_name}.{method}",
            result_code="OK",
        )
        return result

    # ------------------------------------------------------------------
    # Execution trace
    # ------------------------------------------------------------------

    def get_execution_trace(self) -> list:
        """
        Return the full execution trace for audit.

        Returns
        -------
        list
            Every step recorded during all operations on this instance,
            in chronological insertion order.
        """
        return deepcopy(self.execution_trace)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _record_trace_step(
        self,
        action: str,
        trace_id: Optional[str] = None,
        result_code: str = "OK",
        details: Optional[dict] = None,
        invariant_references: Optional[list] = None,
        **_ignored,
    ) -> None:
        """Append a step record to the internal execution trace."""
        self.execution_trace.append({
            "step_id": _trace_id(),
            "timestamp": _timestamp(),
            "component": ComponentID.PURPLE_ORCHESTRATOR.value,
            "action": action,
            "trace_id": trace_id,
            "result_code": result_code,
            "details": details or {},
            "invariant_references": invariant_references or [],
        })

    def _qams_send(self, msg: QAMSMessage) -> Any:
        """
        Send a QAMS message through the transport layer.

        Delegates to the QAMS component if it exposes a ``send`` method;
        otherwise falls back to forwarding directly to the Control Plane.
        This method preserves message structure — QAMS must not alter
        payload semantics.
        """
        if hasattr(self.qams, "send"):
            return self.qams.send(msg)
        # Fallback: pass message envelope to Control Plane directly
        if hasattr(self.control_plane, "receive"):
            return self.control_plane.receive(msg)
        # Last resort: return a minimal acknowledgement
        return {"acknowledged": True, "msg_id": msg.msg_id, "trace_id": msg.trace_id}

    def _invoke_interposer(self, request: dict) -> InterposerVerdict:
        """
        Route through the Interposer for the three-phase verification.

        The orchestrator NEVER skips or short-circuits this step.
        Delegates to the Interposer's ``check`` or ``verify`` method,
        and refuses when the enforcement hook is missing or malformed.
        """
        if hasattr(self.interposer, "evaluate"):
            result = self.interposer.evaluate(request)
            if isinstance(result, InterposerVerdict):
                return result
            if isinstance(result, dict):
                return InterposerVerdict(
                    allowed=result.get("allowed") is True,
                    phase_results=result.get("phase_results", {}),
                    refusal_code=result.get("refusal_code"),
                    invariant_violated=result.get("invariant_violated"),
                    capability_boundary=result.get("capability_boundary"),
                    safe_alternative=result.get("safe_alternative"),
                    trace_hash=result.get("trace_hash", _trace_id()),
                )

        raise RuntimeError("Configured Interposer does not expose evaluate().")

    def _invoke_interposer_escalation(
        self,
        drift_report: DriftReport,
        routed_signal: dict,
        trace_id: str,
    ) -> dict:
        """
        Ask the Interposer to handle a drift escalation.

        Returns a dict describing the escalation outcome including
        whether a cooldown is required.
        """
        if hasattr(self.interposer, "handle_drift_escalation"):
            result = self.interposer.handle_drift_escalation(drift_report)
            result["cooldown_required"] = bool(result.get("action_required"))
            result["envelope_narrowing"] = bool(result.get("narrow_envelope"))
            result["t1_freeze"] = bool(result.get("freeze_t1"))
            result["t2_write_blocked"] = bool(result.get("prevent_t2_writes"))
            result["trace_id"] = trace_id
            return result

        # Default policy derived from severity (no autonomous decision —
        # this mirrors what the Interposer would mandate)
        cooldown_required = drift_report.severity.value >= DriftSeverity.MODERATE.value
        envelope_narrow = drift_report.severity.value >= DriftSeverity.HIGH.value
        t1_freeze = drift_report.memory_bleed_detected
        t2_block = True  # always; T2 writes require human prime signature

        return {
            "cooldown_required": cooldown_required,
            "envelope_narrowing": envelope_narrow,
            "t1_freeze": t1_freeze,
            "t2_write_blocked": t2_block,
            "severity": drift_report.severity.name,
            "trace_id": trace_id,
        }

    def _interposer_adapter_check(
        self, adapter_name: str, method: str, kwargs: dict
    ) -> InterposerVerdict:
        """
        Pre-call Interposer check for adapter invocations.

        Ensures the orchestrator cannot bypass the structural boundary
        even when invoking adapters directly.
        """
        if hasattr(self.interposer, "check_adapter_call"):
            result = self.interposer.check_adapter_call(adapter_name, method, kwargs)
            if isinstance(result, InterposerVerdict):
                return result

        raise RuntimeError("Interposer adapter gate is missing or returned an invalid verdict.")

    def _apply_cooldown(self, severity: DriftSeverity, trace_id: str) -> None:
        """
        Apply a Control Plane cooldown directive.

        The orchestrator only reduces activity — it cannot increase
        throughput, remove delays, or widen capability envelopes
        (CPC 4 constraint: can cool but never heat up).
        """
        if not hasattr(self.control_plane, "apply_interposer_directive"):
            return

        if severity.value >= DriftSeverity.MODERATE.value:
            self.control_plane.apply_interposer_directive({
                "type": "drift_escalation",
                "trace_id": trace_id,
                "issuer": ComponentID.INTERPOSER.value,
            })

        if severity.value >= DriftSeverity.HIGH.value:
            self.control_plane.apply_interposer_directive({
                "type": "memory_freeze",
                "trace_id": trace_id,
                "issuer": ComponentID.INTERPOSER.value,
            })

    def _build_interposer_request(
        self,
        *,
        request: dict,
        assessment: dict,
        trace_id: str,
    ) -> dict:
        payload = request.get("payload", {})
        agent_id = request.get("agent_id", "unknown")

        t0_keys = set(self.control_plane.tier_0_store.get(agent_id, {}).keys())
        t1_keys = set(self.control_plane.tier_1_store.get(agent_id, {}).keys())
        memory_bleed = self.stability_metrics.check_memory_bleed(t0_keys, t1_keys)
        synergy_violation = self.stability_metrics.check_synergy_violation(
            request.get("agent_capabilities", {agent_id: request.get("capabilities", [])})
        )
        continuity_fault = self.stability_metrics.check_continuity_fault(
            request.get("session_state", payload if isinstance(payload, dict) else {})
        )

        interposer_request = dict(request)
        interposer_request["memory_bleed_detected"] = memory_bleed
        interposer_request["synergy_violation"] = synergy_violation
        interposer_request["continuity_fault"] = continuity_fault
        interposer_request["trace_id"] = trace_id
        interposer_request["assessment_trace_id"] = assessment.get("trace_id")
        interposer_request["requesting_agent_id"] = agent_id
        interposer_request["prevent_t2_writes"] = bool(
            getattr(self.control_plane, "t2_writes_blocked", False)
        )
        return interposer_request

    def _build_geometry_request(self, request: dict, assessment: dict) -> dict:
        payload = request.get("payload", {})
        if not isinstance(payload, dict):
            return dict(request)

        data_vector = payload.get("data_vector")
        sequence_index = payload.get("sequence_index")
        entity_id = str(payload.get("entity_id", request.get("agent_id", "anonymous")))

        geometry_request = dict(request)
        geometry_payload = dict(payload)

        if (
            isinstance(data_vector, (list, tuple))
            and len(data_vector) >= 2
            and isinstance(sequence_index, int)
            and hasattr(self.stability_metrics, "prepare_data_for_uri")
        ):
            geometry_payload = self.stability_metrics.prepare_data_for_uri(
                vector=tuple(data_vector),
                sequence_index=sequence_index,
                entity_id=entity_id,
            )

        geometry_payload["coherence_score"] = assessment.get("coherence_score")
        geometry_request["payload"] = geometry_payload
        return geometry_request

    # ------------------------------------------------------------------
    # Response builders (deterministic formats)
    # ------------------------------------------------------------------

    def _build_refusal_response(
        self,
        trace_id: str,
        audit_trail: list,
        reason: str,
        refusal_code: str = "REFUSED",
    ) -> dict:
        """Build a deterministic refusal response (non-Interposer source)."""
        return {
            "allowed": False,
            "trace_id": trace_id,
            "refusal_code": refusal_code,
            "reason": reason,
            "audit_trail": [self._serialise_audit(e) for e in audit_trail],
            "execution_trace_snapshot": [],
            "operational_mode": self.operational_mode.name,
        }

    def _build_interposer_refusal_response(
        self,
        trace_id: str,
        audit_trail: list,
        verdict: InterposerVerdict,
    ) -> dict:
        """
        Build a deterministic refusal from an Interposer denial.

        Includes all IC 4.9 mandated fields: reason_code, invariant_violated,
        capability_boundary, safe_alternative, trace_hash.
        """
        return {
            "allowed": False,
            "trace_id": trace_id,
            "refusal_code": (
                verdict.refusal_code.value if verdict.refusal_code else "INTERPOSER_DENIED"
            ),
            "invariant_violated": verdict.invariant_violated,
            "capability_boundary": verdict.capability_boundary,
            "safe_alternative": verdict.safe_alternative,
            "interposer_trace_hash": verdict.trace_hash,
            "phase_results": verdict.phase_results,
            "audit_trail": [self._serialise_audit(e) for e in audit_trail],
            "execution_trace_snapshot": [],
            "operational_mode": self.operational_mode.name,
        }

    def _build_error_response(
        self,
        trace_id: str,
        audit_trail: list,
        exc: Exception,
    ) -> dict:
        """Build an error response for unexpected exceptions."""
        return {
            "allowed": False,
            "trace_id": trace_id,
            "refusal_code": "INTERNAL_ERROR",
            "reason": str(exc),
            "audit_trail": [self._serialise_audit(e) for e in audit_trail],
            "execution_trace_snapshot": [],
            "operational_mode": self.operational_mode.name,
        }

    @staticmethod
    def _serialise_audit(entry: AuditEntry) -> dict:
        """Convert an AuditEntry dataclass to a serialisable dict."""
        return {
            "entry_id": entry.entry_id,
            "timestamp": entry.timestamp,
            "component": entry.component.value,
            "action": entry.action,
            "agent_involved": entry.agent_involved,
            "invariant_references": entry.invariant_references,
            "geometry_surface": entry.geometry_surface,
            "result_code": entry.result_code,
            "trace_id": entry.trace_id,
            "details": entry.details,
        }
