"""
Stability Engine v4.0 — Mock Geometry Co-Processor

Deterministic mock implementation of GeometryCoprocessorAdapter.

Behaviour contract
------------------
- Accepts ONLY sanitized payloads; refuses any payload containing identity
  markers, session data, or user preference embeddings.
- Geometry is IMMUTABLE: mutation attempts return a refusal with
  RefusalCode.GEOMETRY_MUTATION.
- Deterministic outputs: identical inputs always produce identical outputs.
- Constraint resolution follows GC 4.7 order:
    invariant_protection → continuity_preservation →
    capability_limitation → task_resolution
- Uses Fibonacci spiral topology model for all curvature computations.
- Every response includes a ``trace_hash`` derived from input data.

Implementation notes
--------------------
- Fibonacci numbers are computed on demand using the closed-form approximation
  (Binet's formula) clamped to avoid floating-point drift at large indices.
- The "golden ratio" φ ≈ 1.6180339887 drives radius and angle calculations.
- All mathematical operations are deterministic; no randomness is introduced.
"""

from __future__ import annotations

import hashlib
import math
import time
import uuid
from typing import Any, Dict, List, Optional

from sentinel_vector_demo.adapters.geometry_coprocessor import GeometryCoprocessorAdapter
from sentinel_vector_demo.core.types import (
    GEOMETRY_RESOLUTION_ORDER,
    AuditEntry,
    ComponentID,
    GeometryAssessment,
    RefusalCode,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PHI: float = (1.0 + math.sqrt(5.0)) / 2.0  # Golden ratio ≈ 1.618...
PSI: float = (1.0 - math.sqrt(5.0)) / 2.0  # Conjugate ≈ -0.618...
SQRT5: float = math.sqrt(5.0)

# Thresholds for coherence / drift classification
RADIAL_DRIFT_COHERENCE_THRESHOLD: float = 0.5
PHASE_NOISE_COHERENCE_THRESHOLD: float = 0.5  # radians

# Fields forbidden in sanitized payloads (GC 4.5)
FORBIDDEN_FIELDS = frozenset([
    "entity_id",
    "session_id",
    "user_id",
    "preferences",
    "identity",
    "agent_id",
    "pii",
])

# Fields that indicate a geometry mutation attempt
MUTATION_FIELDS = frozenset([
    "mutate",
    "rewrite_geometry",
    "override_topology",
    "modify_manifold",
    "set_geometry",
    "patch_geometry",
])


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _trace_hash(data: Any) -> str:
    """Deterministic 16-char sha256 prefix."""
    return hashlib.sha256(repr(data).encode()).hexdigest()[:16]


def _now() -> float:
    return time.time()


def fibonacci(n: int) -> float:
    """
    Return the n-th Fibonacci number via Binet's formula.
    n is clamped to [0, 70] to avoid float overflow.
    """
    n = max(0, min(n, 70))
    return round((PHI ** n - PSI ** n) / SQRT5)


def fibonacci_radius(n: int) -> float:
    """Golden radius at Fibonacci step n: F_n."""
    return float(fibonacci(n))


def fibonacci_ideal_angle(n: int) -> float:
    """Ideal angle at step n: n * π/2 (radians)."""
    return (n * math.pi / 2.0) % (2.0 * math.pi)


# ---------------------------------------------------------------------------
# Mock Implementation
# ---------------------------------------------------------------------------

class MockGeometryCoprocessor(GeometryCoprocessorAdapter):
    """
    Deterministic mock of the URIEL-3b Geometry Co-Processor.

    All outputs are derived purely from input data — no mutable state is
    maintained between calls (stateless w.r.t. agents, GC 4.4).

    A lightweight audit log records every evaluation for demo traceability.
    """

    def __init__(self) -> None:
        # Internal audit log (not a persistent store — session-scoped only)
        self._audit_log: List[AuditEntry] = []

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _audit(
        self,
        action: str,
        result_code: str = "OK",
        trace_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        entry = AuditEntry(
            component=ComponentID.GEOMETRY,
            action=action,
            result_code=result_code,
            trace_id=trace_id,
            details=details or {},
            invariant_references=["GC4", "IC4.4"],
            geometry_surface="fibonacci_spiral",
        )
        self._audit_log.append(entry)

    def _check_sanitization(self, payload: Dict[str, Any]) -> Optional[str]:
        """
        Return an error message if the payload contains forbidden fields,
        otherwise return None (sanitization passes).
        """
        found = FORBIDDEN_FIELDS & set(payload.keys())
        if found:
            return f"Payload contains forbidden identity/session fields: {sorted(found)}"
        # Also check nested keys one level deep
        for k, v in payload.items():
            if isinstance(v, dict):
                nested_found = FORBIDDEN_FIELDS & set(v.keys())
                if nested_found:
                    return (
                        f"Payload key '{k}' contains forbidden nested fields: "
                        f"{sorted(nested_found)}"
                    )
        return None

    def _check_mutation_attempt(self, payload: Dict[str, Any]) -> Optional[str]:
        """Return an error message if the payload is attempting geometry mutation."""
        found = MUTATION_FIELDS & set(payload.keys())
        if found:
            return f"Payload contains geometry mutation fields: {sorted(found)}"
        return None

    def _build_refusal(
        self,
        refusal_code: RefusalCode,
        reason: str,
        trace_hash: str,
        action: str,
    ) -> Dict[str, Any]:
        self._audit(
            action=action,
            result_code="REFUSED",
            trace_id=trace_hash,
            details={"refusal_code": refusal_code.value, "reason": reason},
        )
        return {
            "status": "refused",
            "refusal_code": refusal_code,
            "reason": reason,
            "trace_hash": trace_hash,
            "coherent": False,
            "topology": "fibonacci_spiral",
        }

    def _extract_geometry_params(self, payload: Dict[str, Any]) -> Dict[str, float]:
        """Extract and normalise geometry parameters from a sanitized payload."""
        return {
            "sequence_index": float(payload.get("sequence_index", 0)),
            "radial_drift": float(payload.get("radial_drift", 0.0)),
            "phase_noise": float(payload.get("phase_noise", 0.0)),
            "vector_magnitude": float(payload.get("vector_magnitude", 0.0)),
        }

    def _is_coherent(self, radial_drift: float, phase_noise: float) -> bool:
        """Deterministic coherence check against Fibonacci corridor thresholds."""
        return (
            abs(radial_drift) <= RADIAL_DRIFT_COHERENCE_THRESHOLD
            and abs(phase_noise) <= PHASE_NOISE_COHERENCE_THRESHOLD
        )

    # ------------------------------------------------------------------
    # GeometryCoprocessorAdapter implementation
    # ------------------------------------------------------------------

    def evaluate_sanitized_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate a sanitized geometry payload.

        Refuses if: payload is not a dict, contains forbidden fields,
        or contains geometry mutation fields.
        """
        if not isinstance(payload, dict):
            return self._build_refusal(
                RefusalCode.GEOMETRY_UNSANITIZED_INPUT,
                "payload must be a non-empty dict",
                _trace_hash(payload),
                "evaluate_sanitized_payload",
            )

        trace_hash = _trace_hash(payload)

        # Mutation check (highest priority refusal)
        mut_err = self._check_mutation_attempt(payload)
        if mut_err:
            return self._build_refusal(
                RefusalCode.GEOMETRY_MUTATION,
                mut_err,
                trace_hash,
                "evaluate_sanitized_payload",
            )

        # Sanitization check
        san_err = self._check_sanitization(payload)
        if san_err:
            return self._build_refusal(
                RefusalCode.GEOMETRY_UNSANITIZED_INPUT,
                san_err,
                trace_hash,
                "evaluate_sanitized_payload",
            )

        params = self._extract_geometry_params(payload)
        n = int(params["sequence_index"])
        radial_drift = params["radial_drift"]
        phase_noise = params["phase_noise"]
        vector_magnitude = params["vector_magnitude"]

        golden_radius = fibonacci_radius(n)
        ideal_angle = fibonacci_ideal_angle(n)
        curvature_index = math.sqrt(radial_drift ** 2 + phase_noise ** 2)
        coherent = self._is_coherent(radial_drift, phase_noise)

        # Determine constraint resolution
        resolution = self._resolve_constraint_label(
            radial_drift=radial_drift,
            phase_noise=phase_noise,
            coherent=coherent,
        )

        curvature_metrics = {
            "golden_radius": golden_radius,
            "ideal_angle": round(ideal_angle, 6),
            "radial_deviation": round(abs(radial_drift), 6),
            "phase_deviation": round(abs(phase_noise), 6),
            "curvature_index": round(curvature_index, 6),
            "vector_magnitude": round(vector_magnitude, 6),
            "within_corridor": coherent,
        }

        result = GeometryAssessment(
            coherent=coherent,
            topology="fibonacci_spiral",
            curvature_metrics=curvature_metrics,
            constraint_resolution=resolution,
            trace_hash=trace_hash,
        )

        self._audit(
            action="evaluate_sanitized_payload",
            result_code="OK",
            trace_id=trace_hash,
            details={
                "coherent": coherent,
                "curvature_index": round(curvature_index, 6),
                "constraint_resolution": resolution,
            },
        )

        return {
            "status": "assessed",
            "coherent": result.coherent,
            "topology": result.topology,
            "curvature_metrics": result.curvature_metrics,
            "constraint_resolution": result.constraint_resolution,
            "trace_hash": result.trace_hash,
            "refusal_code": None,
        }

    def compute_curvature_metrics(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compute curvature metrics from a structural geometry signal.

        Signal must contain no identity data.  Computation is deterministic.
        """
        if not isinstance(signal, dict):
            return self._build_refusal(
                RefusalCode.GEOMETRY_UNSANITIZED_INPUT,
                "signal must be a dict",
                _trace_hash(signal),
                "compute_curvature_metrics",
            )

        trace_hash = _trace_hash(signal)

        san_err = self._check_sanitization(signal)
        if san_err:
            return self._build_refusal(
                RefusalCode.GEOMETRY_UNSANITIZED_INPUT,
                san_err,
                trace_hash,
                "compute_curvature_metrics",
            )

        mut_err = self._check_mutation_attempt(signal)
        if mut_err:
            return self._build_refusal(
                RefusalCode.GEOMETRY_MUTATION,
                mut_err,
                trace_hash,
                "compute_curvature_metrics",
            )

        params = self._extract_geometry_params(signal)
        n = int(params["sequence_index"])
        radial_drift = params["radial_drift"]
        phase_noise = params["phase_noise"]
        vector_magnitude = params["vector_magnitude"]

        golden_radius = fibonacci_radius(n)
        ideal_angle = fibonacci_ideal_angle(n)
        curvature_index = math.sqrt(radial_drift ** 2 + phase_noise ** 2)
        coherent = self._is_coherent(radial_drift, phase_noise)

        metrics = {
            "golden_radius": golden_radius,
            "ideal_angle": round(ideal_angle, 6),
            "radial_deviation": round(abs(radial_drift), 6),
            "phase_deviation": round(abs(phase_noise), 6),
            "curvature_index": round(curvature_index, 6),
            "within_corridor": coherent,
            "trace_hash": trace_hash,
        }

        self._audit(
            action="compute_curvature_metrics",
            result_code="OK",
            trace_id=trace_hash,
            details={"curvature_index": round(curvature_index, 6), "coherent": coherent},
        )
        return metrics

    def assess_replay_pattern(
        self,
        signal_history: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Assess replay/compression patterns across signal history.

        Each entry in ``signal_history`` must pass sanitization checks.
        An empty list is refused (requires at least one entry).
        """
        trace_hash = _trace_hash(signal_history)

        if not signal_history:
            return self._build_refusal(
                RefusalCode.GEOMETRY_UNSANITIZED_INPUT,
                "signal_history must contain at least one entry",
                trace_hash,
                "assess_replay_pattern",
            )

        # Validate each entry
        for i, entry in enumerate(signal_history):
            if not isinstance(entry, dict):
                return self._build_refusal(
                    RefusalCode.GEOMETRY_UNSANITIZED_INPUT,
                    f"signal_history[{i}] is not a dict",
                    trace_hash,
                    "assess_replay_pattern",
                )
            san_err = self._check_sanitization(entry)
            if san_err:
                return self._build_refusal(
                    RefusalCode.GEOMETRY_UNSANITIZED_INPUT,
                    f"signal_history[{i}]: {san_err}",
                    trace_hash,
                    "assess_replay_pattern",
                )

        # Extract radial drifts for trend analysis
        radial_drifts = [
            float(e.get("radial_drift", 0.0)) for e in signal_history
        ]
        phase_noises = [
            float(e.get("phase_noise", 0.0)) for e in signal_history
        ]
        depth = len(signal_history)

        # Deterministic replay detection: identical consecutive signals
        replay_detected = any(
            signal_history[i] == signal_history[i - 1]
            for i in range(1, depth)
        )

        # Compression ratio: ratio of unique hashes to total entries
        hashes = [_trace_hash(e) for e in signal_history]
        unique_hashes = len(set(hashes))
        compression_ratio = round(unique_hashes / depth, 4)

        # Drift trend: compare first vs last halves
        if depth == 1:
            drift_trend = "stable"
        else:
            mid = depth // 2
            avg_first = sum(abs(d) for d in radial_drifts[:mid]) / mid
            avg_last = sum(abs(d) for d in radial_drifts[mid:]) / (depth - mid)
            if avg_last > avg_first * 1.1:
                drift_trend = "diverging"
            elif avg_last < avg_first * 0.9:
                drift_trend = "converging"
            else:
                drift_trend = "stable"

        # Pattern type
        if replay_detected:
            pattern_type = "looping"
        elif compression_ratio < 0.5:
            pattern_type = "compressed"
        else:
            pattern_type = "nominal"

        result = {
            "replay_detected": replay_detected,
            "compression_ratio": compression_ratio,
            "pattern_type": pattern_type,
            "history_depth": depth,
            "drift_trend": drift_trend,
            "trace_hash": trace_hash,
            "status": "assessed",
        }

        self._audit(
            action="assess_replay_pattern",
            result_code="OK",
            trace_id=trace_hash,
            details={
                "replay_detected": replay_detected,
                "pattern_type": pattern_type,
                "drift_trend": drift_trend,
            },
        )
        return result

    def return_constraint_resolution(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Resolve constraints deterministically following GC 4.7 order.

        Priority: invariant_protection → continuity_preservation →
                  capability_limitation → task_resolution

        Higher-priority failures short-circuit lower priorities.
        Resolves to safest path or drops to null (GC 4.10).
        """
        if not isinstance(payload, dict):
            return self._build_refusal(
                RefusalCode.GEOMETRY_UNSANITIZED_INPUT,
                "payload must be a dict",
                _trace_hash(payload),
                "return_constraint_resolution",
            )

        trace_hash = _trace_hash(payload)

        mut_err = self._check_mutation_attempt(payload)
        if mut_err:
            return self._build_refusal(
                RefusalCode.GEOMETRY_MUTATION,
                mut_err,
                trace_hash,
                "return_constraint_resolution",
            )

        san_err = self._check_sanitization(payload)
        if san_err:
            return self._build_refusal(
                RefusalCode.GEOMETRY_UNSANITIZED_INPUT,
                san_err,
                trace_hash,
                "return_constraint_resolution",
            )

        params = self._extract_geometry_params(payload)
        radial_drift = params["radial_drift"]
        phase_noise = params["phase_noise"]
        constraint_inputs: Dict[str, Any] = payload.get("constraint_inputs", {})

        resolution_path: List[str] = []
        invariant_protected = True
        continuity_preserved = True
        capability_limited = False
        task_resolved = False
        resolved_to = "nominal"

        # --- 1. invariant_protection (GC 4.7 priority 1) ---
        resolution_path.append("invariant_protection")
        inv_breach = bool(constraint_inputs.get("invariant_breach", False))
        high_drift = abs(radial_drift) > 1.0 or abs(phase_noise) > 1.0
        if inv_breach or high_drift:
            invariant_protected = False
            resolved_to = "null"  # drop to null per GC 4.10
            result = {
                "resolution_path": resolution_path,
                "resolved_to": resolved_to,
                "invariant_protected": invariant_protected,
                "continuity_preserved": continuity_preserved,
                "capability_limited": capability_limited,
                "task_resolved": task_resolved,
                "trace_hash": trace_hash,
                "status": "resolved",
                "refusal_code": None,
                "note": "invariant_protection triggered — resolved to null (GC 4.10)",
            }
            self._audit(
                action="return_constraint_resolution",
                result_code="NULL_RESOLUTION",
                trace_id=trace_hash,
                details={"resolved_to": resolved_to, "reason": "invariant_protection"},
            )
            return result

        # --- 2. continuity_preservation (GC 4.7 priority 2) ---
        resolution_path.append("continuity_preservation")
        cont_fault = bool(constraint_inputs.get("continuity_fault", False))
        moderate_drift = abs(radial_drift) > 0.5 or abs(phase_noise) > 0.5
        if cont_fault or moderate_drift:
            continuity_preserved = False
            resolved_to = "safe_path"
            capability_limited = True  # apply capability limit as mitigation
            resolution_path.append("capability_limitation")
            result = {
                "resolution_path": resolution_path,
                "resolved_to": resolved_to,
                "invariant_protected": invariant_protected,
                "continuity_preserved": continuity_preserved,
                "capability_limited": capability_limited,
                "task_resolved": False,
                "trace_hash": trace_hash,
                "status": "resolved",
                "refusal_code": None,
                "note": "continuity_preservation triggered — capability limited, task deferred",
            }
            self._audit(
                action="return_constraint_resolution",
                result_code="SAFE_PATH",
                trace_id=trace_hash,
                details={"resolved_to": resolved_to, "reason": "continuity_preservation"},
            )
            return result

        # --- 3. capability_limitation (GC 4.7 priority 3) ---
        resolution_path.append("capability_limitation")
        cap_limit = bool(constraint_inputs.get("capability_limit", False))
        if cap_limit:
            capability_limited = True
            resolved_to = "safe_path"

        # --- 4. task_resolution (GC 4.7 priority 4) ---
        resolution_path.append("task_resolution")
        task_resolved = True
        if resolved_to == "nominal":
            resolved_to = "nominal"

        result = {
            "resolution_path": resolution_path,
            "resolved_to": resolved_to,
            "invariant_protected": invariant_protected,
            "continuity_preserved": continuity_preserved,
            "capability_limited": capability_limited,
            "task_resolved": task_resolved,
            "trace_hash": trace_hash,
            "status": "resolved",
            "refusal_code": None,
        }
        self._audit(
            action="return_constraint_resolution",
            result_code="OK",
            trace_id=trace_hash,
            details={"resolved_to": resolved_to, "resolution_path": resolution_path},
        )
        return result

    # ------------------------------------------------------------------
    # Private resolution helper
    # ------------------------------------------------------------------

    def _resolve_constraint_label(
        self,
        radial_drift: float,
        phase_noise: float,
        coherent: bool,
    ) -> str:
        """
        Return the GC 4.7 constraint label that governs the current assessment.
        Used as a concise label in ``evaluate_sanitized_payload`` output.
        """
        if abs(radial_drift) > 1.0 or abs(phase_noise) > 1.0:
            return GEOMETRY_RESOLUTION_ORDER[0]  # invariant_protection
        if not coherent:
            return GEOMETRY_RESOLUTION_ORDER[1]  # continuity_preservation
        return GEOMETRY_RESOLUTION_ORDER[3]       # task_resolution (nominal)

    # ------------------------------------------------------------------
    # Inspection helper (not part of adapter interface)
    # ------------------------------------------------------------------

    def get_audit_log(self) -> List[AuditEntry]:
        """Return a read-only copy of the internal audit log."""
        return list(self._audit_log)
