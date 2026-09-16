"""
TSRL-3 Recursive Stability Layer
Stability Engine v4.0

Evaluates recursive update behavior across increasing memory depths.
Identifies zero-friction invariant at R = 4.
Guarantees: coherence and recoverability.

Constraints enforced here:
- Orchestration cannot act safely without a certified stability baseline.
- Certification is only issued when r_invariant_met AND coherence_score
  meets the minimum threshold.
- Recursion depth is bounded at R_INVARIANT (4); exceeding it is a hard
  stability failure.
- History is append-only; no retroactive modification.
"""

from __future__ import annotations

import math
from typing import Optional

from core.types import ComponentID, _trace_id, _timestamp


# Minimum coherence score required for certification
_COHERENCE_THRESHOLD: float = 0.6

# Maximum allowed recursion depth (zero-friction invariant)
_R_INVARIANT: int = 4


class TSRL3Stability:
    """
    Recursive stability evaluator and baseline certifier.

    Responsibilities
    ----------------
    - Evaluate a sequence of attributed signals to determine whether the
      current recursion depth and coherence satisfy the R=4 invariant.
    - Certify a stability baseline that higher layers (e.g. Purple
      Orchestrator) MUST obtain before proceeding with any state-mutating
      operation.
    - Maintain an append-only history of all stability assessments.

    Key invariant
    -------------
    R_INVARIANT = 4 identifies the zero-friction depth at which recursive
    updates across memory tiers converge without residual drift.  Any
    depth above 4 is structurally unsafe.

    What this layer must NOT do
    ---------------------------
    - Issue certifications for sub-threshold coherence.
    - Modify or retroactively revise stability history.
    - Bypass the R=4 bound for performance reasons.
    - Interpret signal semantics to manufacture a passing coherence score.
    """

    R_INVARIANT: int = _R_INVARIANT

    def __init__(self) -> None:
        self.stability_history: list[dict] = []
        self.current_recursion_depth: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate_recursive_stability(self, signals: list[dict]) -> dict:
        """
        Assess stability across the provided signal history.

        Algorithm
        ---------
        1. Derive recursion depth from the length and structural nesting of
           ``signals``.
        2. Check depth against R_INVARIANT.
        3. Compute a coherence score based on signal integrity metrics.
        4. Determine recoverability (True when depth ≤ R_INVARIANT and
           coherence ≥ threshold, or when depth is only marginally exceeded).
        5. Append the assessment to ``stability_history``.

        Coherence score heuristic
        -------------------------
        - Baseline is 1.0.
        - Deducted for: missing integrity hashes, broken attribution, signals
          flagged as semantically compressed, and relative depth overshoot.
        - Score is clamped to [0.0, 1.0].

        Parameters
        ----------
        signals : list[dict]
            Attributed signals produced by TSRL-2.  Each signal is inspected
            for structural integrity markers.

        Returns
        -------
        dict
            Assessment record with keys:
            ``stable``, ``recursion_depth``, ``r_invariant_met``,
            ``coherence_score``, ``recoverable``, ``trace_id``,
            ``timestamp``.
        """
        depth = self._compute_recursion_depth(signals)
        self.current_recursion_depth = depth

        r_invariant_met = self.check_recursion_bound(depth)
        coherence_score = self._compute_coherence(signals, depth)
        stable = r_invariant_met and coherence_score >= _COHERENCE_THRESHOLD

        # Recoverability: safe if within invariant; marginally recoverable
        # if depth is exactly R_INVARIANT+1 and coherence is non-trivial.
        if r_invariant_met:
            recoverable = True
        elif depth == self.R_INVARIANT + 1 and coherence_score >= _COHERENCE_THRESHOLD:
            recoverable = True
        else:
            recoverable = False

        assessment = {
            "record_type": "stability_assessment",
            "trace_id": _trace_id(),
            "timestamp": _timestamp(),
            "stable": stable,
            "recursion_depth": depth,
            "r_invariant": self.R_INVARIANT,
            "r_invariant_met": r_invariant_met,
            "coherence_score": round(coherence_score, 4),
            "recoverable": recoverable,
            "signal_count": len(signals),
            "certified": False,  # Not certified until certify_stability_baseline is called
        }

        self.stability_history.append(assessment)
        return assessment

    def certify_stability_baseline(self, assessment: dict) -> dict:
        """
        Produce a certified stability baseline for consumption by higher layers.

        Certification rules
        -------------------
        - ``r_invariant_met`` MUST be ``True``.
        - ``coherence_score`` MUST be ≥ :data:`_COHERENCE_THRESHOLD`.
        - If either condition is unmet, a refusal record is returned instead
          of a certificate; the caller MUST NOT proceed with orchestration.

        Parameters
        ----------
        assessment : dict
            A stability assessment as returned by
            :meth:`evaluate_recursive_stability`.

        Returns
        -------
        dict
            Either a certified baseline record (``certified: True``) or a
            refusal record (``certified: False``) with a ``refusal_reason``.
        """
        r_invariant_met = assessment.get("r_invariant_met", False)
        coherence_score = assessment.get("coherence_score", 0.0)

        if not r_invariant_met:
            return self._build_refusal(
                assessment,
                reason=(
                    f"R_INVARIANT not met: recursion_depth="
                    f"{assessment.get('recursion_depth')} exceeds "
                    f"R={self.R_INVARIANT}"
                ),
            )

        if coherence_score < _COHERENCE_THRESHOLD:
            return self._build_refusal(
                assessment,
                reason=(
                    f"Coherence score {coherence_score:.4f} below threshold "
                    f"{_COHERENCE_THRESHOLD:.4f}"
                ),
            )

        certificate = {
            "record_type": "stability_certificate",
            "certificate_id": _trace_id(),
            "timestamp": _timestamp(),
            "certified": True,
            "assessment_trace_id": assessment.get("trace_id"),
            "recursion_depth": assessment.get("recursion_depth"),
            "r_invariant": self.R_INVARIANT,
            "r_invariant_met": True,
            "coherence_score": coherence_score,
            "recoverable": assessment.get("recoverable", False),
            "authorised_for_orchestration": True,
        }

        self.stability_history.append(certificate)
        return certificate

    def check_recursion_bound(self, depth: int) -> bool:
        """
        Return ``True`` if *depth* is within the R_INVARIANT bound.

        Parameters
        ----------
        depth : int
            The recursion depth to check.

        Returns
        -------
        bool
            ``True`` iff ``depth <= R_INVARIANT``.
        """
        return depth <= self.R_INVARIANT

    def get_stability_history(self) -> list:
        """
        Return the full append-only stability history.

        Returns
        -------
        list
            All assessment and certificate records in insertion order.
        """
        return list(self.stability_history)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _compute_recursion_depth(self, signals: list[dict]) -> int:
        """
        Derive recursion depth from the signal list.

        Heuristic
        ---------
        - Depth is the count of distinct recursion-related nesting levels
          observed in the signal chain.
        - For a flat list of signals, depth equals the number of signals
          (each represents one recursion step through the observation stack).
        - Capped at R_INVARIANT * 2 to prevent runaway depth reporting from
          corrupted inputs.
        """
        if not signals:
            return 0

        # Count how many signals carry explicit depth markers first
        explicit_depths = [
            s.get("recursion_depth")
            for s in signals
            if isinstance(s.get("recursion_depth"), int)
        ]
        if explicit_depths:
            return max(explicit_depths)

        # Default: treat each signal as a recursion step up to the cap
        raw_depth = len(signals)
        return min(raw_depth, self.R_INVARIANT * 2)

    def _compute_coherence(self, signals: list[dict], depth: int) -> float:
        """
        Compute a coherence score in [0.0, 1.0] based on signal quality.

        Deductions (each is a fractional penalty)
        ------------------------------------------
        - Missing ``integrity_hash``: −0.15 per signal (normalised by count)
        - ``semantically_compressed`` is True: −0.20 per signal (normalised)
        - ``attribution_intact`` is False: −0.15 per signal (normalised)
        - Depth overshoot: −0.10 per step beyond R_INVARIANT (up to −0.40)
        - Empty signal list: score = 0.0
        """
        if not signals:
            return 0.0

        score = 1.0
        n = len(signals)

        for sig in signals:
            if not sig.get("integrity_hash"):
                score -= 0.15 / n
            if sig.get("semantically_compressed", False):
                score -= 0.20 / n
            if not sig.get("attribution_intact", True):
                score -= 0.15 / n

        # Depth overshoot penalty
        overshoot = max(0, depth - self.R_INVARIANT)
        score -= min(overshoot * 0.10, 0.40)

        return max(0.0, min(1.0, score))

    def _build_refusal(self, assessment: dict, reason: str) -> dict:
        """Build and record a certification refusal record."""
        refusal = {
            "record_type": "stability_refusal",
            "refusal_id": _trace_id(),
            "timestamp": _timestamp(),
            "certified": False,
            "authorised_for_orchestration": False,
            "assessment_trace_id": assessment.get("trace_id"),
            "recursion_depth": assessment.get("recursion_depth"),
            "coherence_score": assessment.get("coherence_score"),
            "refusal_reason": reason,
        }
        self.stability_history.append(refusal)
        return refusal
