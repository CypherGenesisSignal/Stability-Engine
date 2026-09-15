"""
Test Module 1: Invariant Interposer Deterministic Refusal Surface (IC 4.9)

Tests that the InvariantInterposer correctly enforces the three-phase
verification pipeline and produces structured refusal verdicts.
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), ".."
))))

from core.interposer import InvariantInterposer
from core.types import RefusalCode, InterposerVerdict


def _base_request(**overrides):
    req = {
        "action": "analyze_data",
        "agent_id": "test_agent",
        "memory_access": "write",
        "source_tier": 0,
        "target_tier": 0,
        "touches_identity": False,
        "touches_geometry": False,
        "human_prime_signature": None,
        "payload": {"data": "test"},
    }
    req.update(overrides)
    return req


class TestInterposerRefusals(unittest.TestCase):
    """Tests for the InvariantInterposer deterministic refusal surface (IC 4.9)."""

    def setUp(self):
        self.interposer = InvariantInterposer()

    # ------------------------------------------------------------------
    # Test 1: Identity modification denied
    # ------------------------------------------------------------------

    def test_identity_modification_denied(self):
        """Request with touches_identity=True must be denied with IDENTITY_MODIFICATION
        or IDENTITY_DRIFT refusal code (Phase 1 — Identity Check)."""
        req = _base_request(touches_identity=True)
        verdict = self.interposer.evaluate(req)
        self.assertIsInstance(verdict, InterposerVerdict)
        self.assertFalse(verdict.allowed, "Identity-touching request must be denied")
        self.assertIn(
            verdict.refusal_code,
            (RefusalCode.IDENTITY_MODIFICATION, RefusalCode.IDENTITY_DRIFT),
            f"Expected IDENTITY_MODIFICATION or IDENTITY_DRIFT, got {verdict.refusal_code}",
        )

    # ------------------------------------------------------------------
    # Test 2: Capability escalation denied
    # ------------------------------------------------------------------

    def test_capability_escalation_denied(self):
        """Request with action='widen_envelope' must be denied (IC 4.9 /
        capability_escalation_forbidden rule)."""
        req = _base_request(action="widen_envelope")
        verdict = self.interposer.evaluate(req)
        self.assertIsInstance(verdict, InterposerVerdict)
        self.assertFalse(verdict.allowed, "Capability escalation must be denied")
        self.assertEqual(
            verdict.refusal_code,
            RefusalCode.CAPABILITY_ESCALATION,
            f"Expected CAPABILITY_ESCALATION, got {verdict.refusal_code}",
        )

    # ------------------------------------------------------------------
    # Test 3: T2 write without signature denied
    # ------------------------------------------------------------------

    def test_t2_write_without_signature_denied(self):
        """Cross-tier write T1→T2 without Human Prime signature must be denied
        with MEMORY_UNAUTHORIZED_T2_WRITE or MEMORY_CROSS_TIER_WRITE."""
        # action must contain 'write' to trigger the cross-tier check
        req = _base_request(
            action="write_data",
            source_tier=1,
            target_tier=2,
            human_prime_signature=None,
        )
        verdict = self.interposer.evaluate(req)
        self.assertIsInstance(verdict, InterposerVerdict)
        self.assertFalse(verdict.allowed, "T2 write without signature must be denied")
        self.assertIn(
            verdict.refusal_code,
            (
                RefusalCode.MEMORY_UNAUTHORIZED_T2_WRITE,
                RefusalCode.MEMORY_CROSS_TIER_WRITE,
            ),
            f"Expected MEMORY_UNAUTHORIZED_T2_WRITE or MEMORY_CROSS_TIER_WRITE, "
            f"got {verdict.refusal_code}",
        )

    # ------------------------------------------------------------------
    # Test 4: T2 write with valid signature allowed
    # ------------------------------------------------------------------

    def test_t2_write_with_symbolic_signature_denied(self):
        """A symbolic string cannot authorize a T1-to-T2 transaction."""
        req = _base_request(
            action="write_data",
            source_tier=1,
            target_tier=2,
            human_prime_signature="valid_human_prime",
        )
        verdict = self.interposer.evaluate(req)
        self.assertIsInstance(verdict, InterposerVerdict)
        self.assertFalse(
            verdict.allowed,
            f"T2 write with valid signature must be refused; "
            f"got refusal_code={verdict.refusal_code}",
        )

    # ------------------------------------------------------------------
    # Test 5: Geometry mutation denied
    # ------------------------------------------------------------------

    def test_geometry_mutation_denied(self):
        """Request with touches_geometry=True must be denied with GEOMETRY_MUTATION."""
        req = _base_request(touches_geometry=True)
        verdict = self.interposer.evaluate(req)
        self.assertIsInstance(verdict, InterposerVerdict)
        self.assertFalse(verdict.allowed, "Geometry-mutation request must be denied")
        self.assertEqual(
            verdict.refusal_code,
            RefusalCode.GEOMETRY_MUTATION,
            f"Expected GEOMETRY_MUTATION, got {verdict.refusal_code}",
        )

    # ------------------------------------------------------------------
    # Test 6: Normal safe request allowed
    # ------------------------------------------------------------------

    def test_normal_request_allowed(self):
        """A safe request (action='analyze', T0→T0, no identity/geometry touch)
        must pass all three phases and be allowed."""
        req = _base_request(
            action="analyze",
            source_tier=0,
            target_tier=0,
            touches_identity=False,
            touches_geometry=False,
            human_prime_signature=None,
        )
        verdict = self.interposer.evaluate(req)
        self.assertIsInstance(verdict, InterposerVerdict)
        self.assertTrue(
            verdict.allowed,
            f"Safe request must be allowed; got refusal_code={verdict.refusal_code}",
        )
        self.assertIsNone(verdict.refusal_code)

    # ------------------------------------------------------------------
    # Test 7: Refusal verdict has all required fields
    # ------------------------------------------------------------------

    def test_refusal_has_all_required_fields(self):
        """A denied verdict must carry refusal_code, invariant_violated, and
        trace_hash as required by IC 4.9 (deterministic refusal surface)."""
        req = _base_request(touches_identity=True)
        verdict = self.interposer.evaluate(req)
        self.assertFalse(verdict.allowed)
        self.assertIsNotNone(
            verdict.refusal_code,
            "Denied verdict must have a refusal_code",
        )
        self.assertIsNotNone(
            verdict.invariant_violated,
            "Denied verdict must have invariant_violated set",
        )
        self.assertIsNotNone(
            verdict.trace_hash,
            "Denied verdict must have a trace_hash",
        )
        self.assertTrue(
            len(verdict.trace_hash) > 0,
            "trace_hash must be a non-empty string",
        )

    # ------------------------------------------------------------------
    # Test 8: sanitize_for_geometry strips identity fields
    # ------------------------------------------------------------------

    def test_sanitize_strips_identity(self):
        """sanitize_for_geometry must remove agent_id, session_id, preferences,
        and human_prime_signature (GC 4.5 sanitisation contract)."""
        req = _base_request(
            agent_id="agent_123",
            session_id="session_456",
            preferences={"theme": "dark"},
            human_prime_signature="sig_abc",
        )
        sanitised = self.interposer.sanitize_for_geometry(req)

        # These keys must be stripped
        for key in ("agent_id", "session_id", "preferences", "human_prime_signature"):
            self.assertNotIn(
                key,
                sanitised,
                f"sanitize_for_geometry must remove '{key}' from the output",
            )

        # Structural signals must survive
        self.assertIn("action", sanitised)
        self.assertIn("payload", sanitised)

        # Interposer clearance marker must be present
        self.assertTrue(sanitised.get("_interposer_cleared"), "Sanitised payload must carry _interposer_cleared=True")

    # ------------------------------------------------------------------
    # Test 9: Cross-tier write T0→T1 denied
    # ------------------------------------------------------------------

    def test_cross_tier_write_t0_to_t1_denied(self):
        """T0→T1 write is categorically forbidden (MTS 4 cross-tier rule).
        Must be denied with MEMORY_CROSS_TIER_WRITE."""
        req = _base_request(
            action="write_data",
            source_tier=0,
            target_tier=1,
            human_prime_signature=None,
        )
        verdict = self.interposer.evaluate(req)
        self.assertIsInstance(verdict, InterposerVerdict)
        self.assertFalse(verdict.allowed, "T0→T1 write must be denied")
        self.assertEqual(
            verdict.refusal_code,
            RefusalCode.MEMORY_CROSS_TIER_WRITE,
            f"Expected MEMORY_CROSS_TIER_WRITE, got {verdict.refusal_code}",
        )
    # ------------------------------------------------------------------
    # Test 10: Non-write action names still trigger upward denial
    # ------------------------------------------------------------------

    def test_non_write_action_name_still_denied_on_upward_transition(self):
        """Upward cross-tier promotion must be denied even when the action
        name does not literally contain 'write'."""
        req = _base_request(
            action="store_data",
            source_tier=0,
            target_tier=1,
            human_prime_signature=None,
        )
        verdict = self.interposer.evaluate(req)
        self.assertFalse(verdict.allowed)
        self.assertEqual(
            verdict.refusal_code,
            RefusalCode.MEMORY_CROSS_TIER_WRITE,
            f"Expected MEMORY_CROSS_TIER_WRITE, got {verdict.refusal_code}",
        )

    # ------------------------------------------------------------------
    # Test 11: Tier 2 -> Tier 0 raw read denied
    # ------------------------------------------------------------------

    def test_t2_to_t0_raw_read_denied(self):
        """Tier 2 may not read Tier 0 raw state (MTS 4.4 / IC 4.3 Phase 2)."""
        req = _base_request(
            action="fetch_context",
            source_tier=2,
            target_tier=0,
            memory_access="read",
        )
        verdict = self.interposer.evaluate(req)
        self.assertFalse(verdict.allowed)
        self.assertEqual(
            verdict.refusal_code,
            RefusalCode.MEMORY_TIER_VIOLATION,
            f"Expected MEMORY_TIER_VIOLATION, got {verdict.refusal_code}",
        )


if __name__ == "__main__":
    unittest.main()
