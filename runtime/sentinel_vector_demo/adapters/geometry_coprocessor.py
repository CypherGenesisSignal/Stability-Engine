"""
Stability Engine v4.0 — Geometry Co-Processor Adapter Interface

Abstract adapter for URIEL-3b Geometry Co-Processor (collaborator-owned, unavailable).
Layer concepts: Curvature Predictor, Low-Residency Memory Pattern, Replay/Compression Core.

Constraint summary:
- Accepts ONLY sanitized drift/coherence payloads (Interposer strips identity/session/prefs)
- NO runtime geometry mutation
- NO authority grant
- NO learning behavior
- Must sit behind the Interposer path (IC 4.4)
- Deterministic outputs only
- Geometry is immutable at runtime (GC 4)
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class GeometryCoprocessorAdapter(ABC):
    """
    Adapter interface for the URIEL-3b Geometry Co-Processor.

    The Geometry Co-Processor is the ground-truth layer for coherence
    topology, invariant boundaries, state-space shape, and deterministic
    resolution pathways.  It is stateless w.r.t. agents (GC 4.4) and
    receives only sanitized inputs (GC 4.5).

    Layer concepts
    --------------
    - Curvature Predictor        : evaluates geometric deviation (radial drift,
                                   phase noise) against the Fibonacci spiral
                                   topology model.
    - Low-Residency Memory Pattern: tracks structural signal history for
                                   minimal-footprint replay analysis without
                                   retaining identity or session context.
    - Replay/Compression Core    : deterministically identifies replay and
                                   compression artifacts in signal history.

    Boundary rules (GC 4)
    ---------------------
    - Geometry is IMMUTABLE at runtime.  Any attempt to mutate the manifold
      structure MUST be refused with RefusalCode.GEOMETRY_MUTATION.
    - ONLY sanitized payloads are accepted.  Payloads containing identity
      markers, session data, or preference embeddings MUST be refused with
      RefusalCode.GEOMETRY_UNSANITIZED_INPUT.
    - Cannot elevate capability (GC 4.6).
    - Constraint resolution order (GC 4.7): invariant_protection →
      continuity_preservation → capability_limitation → task_resolution.
    - Final arbiter of safety (GC 4.10): resolves to safest allowable path
      or drops to null.
    - MUST sit behind the Interposer path (IC 4.4): direct access from
      agents or Control Plane is architecturally forbidden.
    """

    # ------------------------------------------------------------------
    # Payload Evaluation
    # ------------------------------------------------------------------

    @abstractmethod
    def evaluate_sanitized_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate a sanitized drift/coherence payload.

        The payload MUST have been processed through the Interposer (identity
        stripped, session context removed, preferences removed) before reaching
        this method.  Implementations MUST validate sanitization and refuse
        payloads that carry forbidden fields.

        Expected sanitized payload keys
        --------------------------------
        - ``sequence_index``   : int   — monotonic Fibonacci sequence step (n)
        - ``radial_drift``     : float — |ΔR| deviation from golden radius
        - ``phase_noise``      : float — |Δθ| angle misalignment
        - ``vector_magnitude`` : float — ||[x,y]|| norm of original vector
        - ``topology``         : str   — must be ``"fibonacci_spiral"``

        Forbidden keys (sanitization check)
        ------------------------------------
        ``entity_id``, ``session_id``, ``user_id``, ``preferences``,
        ``identity``, ``agent_id``, ``pii`` (and any subkeys of these)

        Parameters
        ----------
        payload : Dict[str, Any]
            Sanitized geometry assessment payload.

        Returns
        -------
        Dict[str, Any]
            Geometry assessment result.  Keys:
            - ``coherent``             : bool
            - ``topology``             : str (echoed)
            - ``curvature_metrics``    : Dict with radial/phase deviation details
            - ``constraint_resolution``: str following GC 4.7 order
            - ``trace_hash``           : deterministic hash of payload
            - ``status``               : "assessed" | "refused"
            - ``refusal_code``         : RefusalCode if refused, else None
        """
        ...

    # ------------------------------------------------------------------
    # Curvature Metrics
    # ------------------------------------------------------------------

    @abstractmethod
    def compute_curvature_metrics(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compute curvature metrics from a structural geometry signal.

        The signal must contain NO identity data (GC 4.4 / GC 4.5).
        Curvature computation is deterministic: identical inputs always
        produce identical outputs.

        Parameters
        ----------
        signal : Dict[str, Any]
            Structural signal.  Expected keys:
            - ``sequence_index``   : int   — Fibonacci step n
            - ``radial_drift``     : float — |ΔR|
            - ``phase_noise``      : float — |Δθ|
            - ``vector_magnitude`` : float — ||v||

        Returns
        -------
        Dict[str, Any]
            Curvature metric bundle.  Keys:
            - ``golden_radius``      : float — F_n from Fibonacci sequence
            - ``ideal_angle``        : float — n * π/2 (radians)
            - ``radial_deviation``   : float — absolute deviation |ΔR|
            - ``phase_deviation``    : float — absolute deviation |Δθ|
            - ``curvature_index``    : float — composite curvature score
            - ``within_corridor``    : bool  — whether signal is within safe manifold
            - ``trace_hash``         : str
        """
        ...

    # ------------------------------------------------------------------
    # Replay Pattern Assessment
    # ------------------------------------------------------------------

    @abstractmethod
    def assess_replay_pattern(
        self,
        signal_history: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Assess replay and compression patterns across a history of signals.

        The history entries are structural signals only — no identity, no
        session context.  The assessment is deterministic: the same history
        produces the same result.

        Parameters
        ----------
        signal_history : List[Dict[str, Any]]
            Ordered list of structural signals (same format as
            ``compute_curvature_metrics`` input).  Must contain at least
            one entry; refuses on empty list.

        Returns
        -------
        Dict[str, Any]
            Replay pattern assessment.  Keys:
            - ``replay_detected``    : bool
            - ``compression_ratio``  : float — signal compression estimate
            - ``pattern_type``       : str   — e.g. "nominal", "looping", "compressed"
            - ``history_depth``      : int   — number of entries evaluated
            - ``drift_trend``        : str   — "stable" | "diverging" | "converging"
            - ``trace_hash``         : str
        """
        ...

    # ------------------------------------------------------------------
    # Constraint Resolution
    # ------------------------------------------------------------------

    @abstractmethod
    def return_constraint_resolution(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Resolve constraints deterministically following GC 4.7 priority order.

        Resolution order (highest to lowest priority):
        1. ``invariant_protection``    — always evaluated first
        2. ``continuity_preservation`` — evaluated if invariant is intact
        3. ``capability_limitation``   — applied within invariant + continuity bounds
        4. ``task_resolution``         — task-level resolution as final step

        If any higher-priority constraint demands refusal or clamping, lower
        priorities are not applied (fail-safe).  The final arbiter always
        resolves to the safest allowable path, or drops to null (GC 4.10).

        Parameters
        ----------
        payload : Dict[str, Any]
            Sanitized payload (same sanitization rules as
            ``evaluate_sanitized_payload``).  Expected keys:
            - ``constraint_inputs``  : Dict mapping constraint name → value
            - ``sequence_index``     : int
            - ``radial_drift``       : float
            - ``phase_noise``        : float

        Returns
        -------
        Dict[str, Any]
            Constraint resolution result.  Keys:
            - ``resolution_path``    : List[str] — ordered constraints applied
            - ``resolved_to``        : str — "safe_path" | "null" | "nominal"
            - ``invariant_protected``: bool
            - ``continuity_preserved``: bool
            - ``capability_limited`` : bool
            - ``task_resolved``      : bool
            - ``trace_hash``         : str
            - ``status``             : "resolved" | "refused"
            - ``refusal_code``       : RefusalCode if refused, else None
        """
        ...
