"""
Stability Metrics — Sentinel Vector / Stability Engine v4.0

Implements MTS 4.5 drift detection, memory bleed detection, synergy violation
flags, and continuity diagnostics.  All measurements are grounded in the
Fibonacci Spiral Projection model described in the build specification.

TSRL-1 feeds raw state snapshots into this module.
Outputs (DriftReport) are consumed by the Invariant Interposer and the
Control Plane's recovery path.
"""

from __future__ import annotations

import math
from typing import Optional

from core.types import (
    ComponentID,
    DriftReport,
    DriftSeverity,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _fibonacci(n: int) -> int:
    """Iterative Fibonacci — F(0)=0, F(1)=1, F(2)=1, F(3)=2, …"""
    if n <= 0:
        return 0
    a, b = 0, 1
    for _ in range(1, n):
        a, b = b, a + b
    return b


def _normalize_angle_diff(delta: float) -> float:
    """Fold an arbitrary angle difference into [0, π]."""
    # Wrap to (-π, π], then take absolute value → [0, π]
    delta = delta % (2 * math.pi)
    if delta > math.pi:
        delta = 2 * math.pi - delta
    return abs(delta)


# ---------------------------------------------------------------------------
# StabilityMetrics
# ---------------------------------------------------------------------------

class StabilityMetrics:
    """
    Monitors for drift, memory anomalies, synergy violations, and
    continuity faults in accordance with MTS 4.5 and TLS 4.

    Monitored threat surfaces
    -------------------------
    - Memory bleed (unauthorized key retention / T0→T1 leakage)
    - Cross-agent contamination (T1 shared without envelope justification)
    - Optimization artifacts stored persistently
    - Caching pathways that simulate continuity
    - Shadow copies of identity state
    - Synergy violations (combined capabilities exceeding individual envelopes)
    - Continuity discontinuities between session states
    """

    # Drift severity thresholds (combined score)
    THRESHOLD_LOW      = 0.1
    THRESHOLD_MODERATE = 0.3
    THRESHOLD_HIGH     = 0.6
    THRESHOLD_CRITICAL = 0.8

    # Keys that must never appear in Tier-0 context (MTS 4 — identity prohibition)
    _IDENTITY_MARKER_KEYS: frozenset = frozenset({
        "identity", "identity_anchor", "agent_id_persistent",
        "user_profile", "session_continuity", "persistent_context",
        "cross_session_state", "shadow_copy", "optimization_artifact",
        "cache_continuity",
    })

    # Capabilities that are individually harmless but dangerous in combination
    _DANGEROUS_CAPABILITY_PAIRS: tuple = (
        ("write_t2", "modify_identity"),
        ("write_t2", "modify_geometry"),
        ("write_t2", "escalate_capability"),
        ("modify_identity", "bypass_interposer"),
        ("modify_geometry", "bypass_interposer"),
        ("read_t2_raw", "write_t2"),
        ("persist_t0", "cross_agent_share"),
    )

    def __init__(self) -> None:
        self.component_id = ComponentID.STABILITY_METRICS

        # Drift threshold mapping (stored for external inspection / audit)
        self.drift_thresholds: dict[DriftSeverity, float] = {
            DriftSeverity.LOW:      self.THRESHOLD_LOW,
            DriftSeverity.MODERATE: self.THRESHOLD_MODERATE,
            DriftSeverity.HIGH:     self.THRESHOLD_HIGH,
            DriftSeverity.CRITICAL: self.THRESHOLD_CRITICAL,
        }

    # ------------------------------------------------------------------
    # Primary public interface
    # ------------------------------------------------------------------

    def evaluate_drift(
        self,
        vector: tuple,
        sequence_index: int,
    ) -> DriftReport:
        """
        Fibonacci Spiral Projection drift evaluation.

        Parameters
        ----------
        vector : tuple
            At minimum (x, y).  Additional dimensions are ignored for
            2-D spiral projection.
        sequence_index : int
            Position on the Fibonacci sequence that defines the ideal
            state for this measurement cycle.

        Returns
        -------
        DriftReport
            Fully populated report including severity classification.
        """
        x = float(vector[0]) if len(vector) > 0 else 0.0
        y = float(vector[1]) if len(vector) > 1 else 0.0

        # --- Ideal state (Fibonacci spiral) ----------------------------
        ideal_radius: float = float(_fibonacci(sequence_index))
        ideal_angle: float  = sequence_index * math.pi / 2.0

        # --- Actual state ----------------------------------------------
        actual_radius: float = math.sqrt(x ** 2 + y ** 2)
        actual_angle: float  = math.atan2(y, x)

        # --- Radial drift |ΔR| -----------------------------------------
        # Normalised so that a full-radius deviation = 1.0
        radial_drift: float = abs(actual_radius - ideal_radius) / max(ideal_radius, 1e-9)

        # --- Phase noise |Δθ| ------------------------------------------
        raw_phase_diff   = actual_angle - ideal_angle
        phase_noise: float = _normalize_angle_diff(raw_phase_diff)

        # --- Vector magnitude ------------------------------------------
        vector_magnitude: float = actual_radius

        # --- Combined drift score (equal-weight blend) -----------------
        # phase_noise lives in [0, π] ≈ [0, 3.14]; normalise to [0, 1]
        normalised_phase = phase_noise / math.pi
        drift_score = 0.5 * radial_drift + 0.5 * normalised_phase

        # --- Severity classification -----------------------------------
        severity = self._classify_severity(drift_score)

        details_parts = [
            f"ideal_radius={ideal_radius:.4f}",
            f"actual_radius={actual_radius:.4f}",
            f"ideal_angle_rad={ideal_angle:.4f}",
            f"actual_angle_rad={actual_angle:.4f}",
            f"drift_score={drift_score:.4f}",
        ]

        return DriftReport(
            severity=severity,
            radial_drift=radial_drift,
            phase_noise=phase_noise,
            vector_magnitude=vector_magnitude,
            sequence_index=sequence_index,
            details="; ".join(details_parts),
        )

    def check_memory_bleed(
        self,
        tier_0_keys: set,
        tier_1_keys: set,
    ) -> bool:
        """
        Detect key overlap between Tier-0 and Tier-1 stores.

        A key present in both tiers indicates either:
        - Unauthorised T0→T1 promotion (retention beyond operation cycle), or
        - A shadow copy of T0 state living in T1.

        Also flags any identity-marker keys that have leaked into T0
        (MTS 4: T0 cannot contain identity markers).

        Returns True when a bleed is detected.
        """
        # Direct key overlap
        overlap = tier_0_keys & tier_1_keys
        if overlap:
            return True

        # Identity-marker contamination in T0
        t0_identity_contamination = tier_0_keys & self._IDENTITY_MARKER_KEYS
        if t0_identity_contamination:
            return True

        return False

    def check_synergy_violation(
        self,
        agent_capabilities: dict,
    ) -> bool:
        """
        Detect combined capabilities that exceed individually authorised
        envelopes.

        ``agent_capabilities`` maps agent_id → set/list of capability strings.

        Violation occurs when the *union* of all capabilities across agents
        (or within a single agent) contains a dangerous pairing defined in
        _DANGEROUS_CAPABILITY_PAIRS.

        Returns True if a synergy violation is detected.
        """
        # Collect the union of all capabilities presented
        all_caps: set[str] = set()
        for caps in agent_capabilities.values():
            all_caps.update(caps)

        for cap_a, cap_b in self._DANGEROUS_CAPABILITY_PAIRS:
            if cap_a in all_caps and cap_b in all_caps:
                return True

        return False

    def check_continuity_fault(
        self,
        session_state: dict,
    ) -> bool:
        """
        Detect discontinuities or illegal continuity simulations in session
        state.

        Flags
        -----
        - ``cross_session_data``: data bridging session boundaries
        - ``cache_continuity``: caching pathway simulating cross-session memory
        - ``optimization_artifact``: persistently stored optimisation result
        - ``shadow_copy``: duplicate identity/state hidden in session context
        - ``tier_boundary_collapsed``: session no longer isolated per MTS 4
        - ``unauthorized_retention``: explicit retention of T0 material in T1

        Returns True if a continuity fault is detected.
        """
        fault_indicators = {
            "cross_session_data",
            "cache_continuity",
            "optimization_artifact",
            "shadow_copy",
            "tier_boundary_collapsed",
            "unauthorized_retention",
        }

        for key in fault_indicators:
            if session_state.get(key):
                return True

        # A session_id that spans multiple external IDs is a continuity bridge
        if "linked_sessions" in session_state:
            linked = session_state["linked_sessions"]
            if isinstance(linked, (list, tuple, set)) and len(linked) > 1:
                return True

        return False

    def prepare_data_for_uri(
        self,
        vector: tuple,
        sequence_index: int,
        entity_id: str,
    ) -> dict:
        """
        Prepare a sanitised geometric coherence payload for the URIEL adapter
        (Geometry Co-Processor / URIEL-3b).

        Per GC 4.5 the Interposer strips identity/session context before
        forwarding; this method attaches *only* the structural drift signals
        — no identity markers, no session artefacts.

        Returns
        -------
        dict
            Keys: sequence_index, radial_drift, phase_noise, vector_magnitude,
            topology.  ``entity_id`` is hashed before inclusion so the
            Geometry layer remains stateless w.r.t. identity (GC 4.4).
        """
        import hashlib

        report = self.evaluate_drift(vector, sequence_index)

        # Hash the entity ID so Geometry never receives a raw identity anchor
        entity_hash = hashlib.sha256(entity_id.encode()).hexdigest()[:16]

        return {
            "sequence_index":   sequence_index,
            "radial_drift":     report.radial_drift,
            "phase_noise":      report.phase_noise,
            "vector_magnitude": report.vector_magnitude,
            "topology":         "fibonacci_spiral",
            "entity_hash":      entity_hash,   # opaque — not an identity anchor
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _classify_severity(self, drift_score: float) -> DriftSeverity:
        """Map a combined drift score to a DriftSeverity level."""
        if drift_score >= self.THRESHOLD_CRITICAL:
            return DriftSeverity.CRITICAL
        if drift_score >= self.THRESHOLD_HIGH:
            return DriftSeverity.HIGH
        if drift_score >= self.THRESHOLD_MODERATE:
            return DriftSeverity.MODERATE
        if drift_score >= self.THRESHOLD_LOW:
            return DriftSeverity.LOW
        return DriftSeverity.NONE
