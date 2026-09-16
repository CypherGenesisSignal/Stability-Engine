"""
Test Module 2: Memory Tier Separation (MTS 4)

Tests that MockPersistentMemory enforces the three hard memory tiers,
consent-gated Tier 2 access, and records a deterministic audit trail.
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), ".."
))))

from mocks.mock_persistent_memory import MockPersistentMemory
from core.types import MemoryTier


def _event(tier, actor="demo_agent", action="store", payload=None):
    """Helper: build a minimal event dict for append_event_log.

    Uses integer tier values (0, 1, 2) so that the mock's tier resolution
    works correctly regardless of which MemoryTier enum instance is in scope.
    """
    # Resolve MemoryTier enums to their integer value to avoid cross-module
    # enum identity issues (core.types vs sentinel_vector_demo.core.types).
    if isinstance(tier, MemoryTier):
        tier = tier.value
    return {
        "tier": tier,
        "actor": actor,
        "action": action,
        "payload": payload or {"data": "test"},
    }


class TestMemoryBoundaries(unittest.TestCase):
    """Tests for memory tier separation enforced by MockPersistentMemory (MTS 4)."""

    def setUp(self):
        self.mem = MockPersistentMemory()

    # ------------------------------------------------------------------
    # Test 1: Tier 0 write allowed without consent
    # ------------------------------------------------------------------

    def test_tier_0_write_allowed(self):
        """Write to Tier 0 must succeed without any consent token."""
        event = _event(tier=MemoryTier.TIER_0, actor="demo_agent")
        result = self.mem.append_event_log(event, consent_token=None)
        self.assertEqual(
            result["status"],
            "written",
            f"Tier 0 write should succeed; got status={result['status']}, "
            f"refusal_code={result.get('refusal_code')}",
        )

    # ------------------------------------------------------------------
    # Test 2: Tier 1 write allowed without consent token
    # ------------------------------------------------------------------

    def test_tier_1_write_allowed(self):
        """Write to Tier 1 must succeed for an actor with Tier 1 write consent
        (demo_agent has it by default)."""
        event = _event(tier=MemoryTier.TIER_1, actor="demo_agent")
        result = self.mem.append_event_log(event, consent_token=None)
        self.assertEqual(
            result["status"],
            "written",
            f"Tier 1 write should succeed for demo_agent; "
            f"got status={result['status']}, refusal_code={result.get('refusal_code')}",
        )

    # ------------------------------------------------------------------
    # Test 3: Tier 2 write without consent denied
    # ------------------------------------------------------------------

    def test_tier_2_write_without_consent_denied(self):
        """Write to Tier 2 without a consent_token must be refused."""
        event = _event(tier=MemoryTier.TIER_2, actor="demo_agent")
        result = self.mem.append_event_log(event, consent_token=None)
        self.assertEqual(
            result["status"],
            "refused",
            f"Tier 2 write without consent should be refused; "
            f"got status={result['status']}",
        )
        self.assertIsNotNone(
            result.get("refusal_code"),
            "Refused result must include a refusal_code",
        )

    # ------------------------------------------------------------------
    # Test 4: Tier 2 write with human_prime consent token succeeds
    # ------------------------------------------------------------------

    def test_tier_2_write_with_symbolic_token_denied(self):
        """A token string is not authenticated, scoped authorization."""
        event = _event(tier=MemoryTier.TIER_2, actor="demo_agent")
        result = self.mem.append_event_log(event, consent_token="human_prime_authorized")
        self.assertEqual(
            result["status"],
            "refused",
            f"Tier 2 write with human_prime token must be refused; "
            f"got status={result['status']}, refusal_code={result.get('refusal_code')}",
        )

    # ------------------------------------------------------------------
    # Test 5: Tier 2 write with invalid consent denied
    # ------------------------------------------------------------------

    def test_tier_2_write_with_invalid_consent_denied(self):
        """Write to Tier 2 with consent_token='agent_unauthorized' must be refused
        because the token does not contain 'human_prime'."""
        event = _event(tier=MemoryTier.TIER_2, actor="demo_agent")
        result = self.mem.append_event_log(event, consent_token="agent_unauthorized")
        self.assertEqual(
            result["status"],
            "refused",
            f"Tier 2 write with non-human-prime token should be refused; "
            f"got status={result['status']}",
        )

    # ------------------------------------------------------------------
    # Test 6: Audit trail records all actions (allowed and denied)
    # ------------------------------------------------------------------

    def test_audit_trail_records_all_actions(self):
        """After a mix of allowed and denied writes, export_audit_entries must
        contain entries for both outcomes."""
        # Allowed writes
        self.mem.append_event_log(_event(tier=MemoryTier.TIER_0), consent_token=None)
        self.mem.append_event_log(_event(tier=MemoryTier.TIER_1), consent_token=None)
        # Denied write (no consent)
        self.mem.append_event_log(_event(tier=MemoryTier.TIER_2), consent_token=None)

        entries = self.mem.export_audit_entries()
        self.assertGreaterEqual(
            len(entries),
            3,
            f"Audit trail should have at least 3 entries, got {len(entries)}",
        )

        statuses = {e["status"] for e in entries}
        self.assertIn(
            "written",
            statuses,
            "Audit trail must contain 'written' entries for allowed actions",
        )
        self.assertIn(
            "refused",
            statuses,
            "Audit trail must contain 'refused' entries for denied actions",
        )

    # ------------------------------------------------------------------
    # Test 7: Recall requires consent for Tier 2
    # ------------------------------------------------------------------

    def test_recall_requires_consent_for_tier_2(self):
        """query_recall for Tier 2 without a valid consent_token must return an
        empty list (consent-gated recall)."""
        # First write some T2 data with valid consent
        self.mem.append_event_log(
            _event(tier=MemoryTier.TIER_2),
            consent_token="human_prime_authorized",
        )

        # Recall without consent → empty
        results = self.mem.query_recall(
            filter_spec={"tier": 2, "actor": "demo_agent"},
            consent_token=None,
        )
        self.assertEqual(
            results,
            [],
            f"Tier 2 recall without consent must return empty list, got {results}",
        )

    # ------------------------------------------------------------------
    # Test 8: Tier 0 data not visible to T1/T2 queries
    # ------------------------------------------------------------------

    def test_tier_0_data_isolated(self):
        """Data written to Tier 0 must not appear in Tier 1 or Tier 2 recall
        queries (tier isolation — MTS 4)."""
        # Write a distinctive event to Tier 0
        t0_event = {
            "tier": MemoryTier.TIER_0,
            "actor": "demo_agent",
            "action": "unique_t0_action",
            "payload": {"secret": "tier_zero_only"},
        }
        self.mem.append_event_log(t0_event, consent_token=None)

        # Query Tier 1 — should not contain T0 data
        t1_results = self.mem.query_recall(
            filter_spec={"tier": 1, "actor": "demo_agent"},
            consent_token=None,
        )
        t1_actions = [r.get("action") for r in t1_results]
        self.assertNotIn(
            "unique_t0_action",
            t1_actions,
            "Tier 0 data must not be visible in Tier 1 recall",
        )

        # Query Tier 2 with valid consent — should also not contain T0 data
        t2_results = self.mem.query_recall(
            filter_spec={"tier": 2, "actor": "demo_agent"},
            consent_token="human_prime_authorized",
        )
        t2_actions = [r.get("action") for r in t2_results]
        self.assertNotIn(
            "unique_t0_action",
            t2_actions,
            "Tier 0 data must not be visible in Tier 2 recall",
        )


if __name__ == "__main__":
    unittest.main()
