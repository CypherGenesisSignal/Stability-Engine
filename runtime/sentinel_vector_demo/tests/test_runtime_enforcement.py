"""
System-level runtime enforcement tests for the constrained cleanup pass.
"""

import os
import sys
import unittest
from dataclasses import FrozenInstanceError

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), ".."
))))

from core.audit_log import AuditLog
from core.control_plane import ControlPlane
from core.interposer import InvariantInterposer
from core.qams import QAMS
from core.stability_metrics import StabilityMetrics
from core.types import MemoryTier
from mocks.mock_geometry_coprocessor import MockGeometryCoprocessor
from mocks.mock_persistent_memory import MockPersistentMemory
from mocks.mock_presence_engine import MockPresenceEngine
from orchestration.purple_orchestrator import PurpleOrchestrator
from tsrl.tsrl1_observation import TSRL1Observation
from tsrl.tsrl2_routing import TSRL2Routing
from tsrl.tsrl3_stability import TSRL3Stability


class SpyGeometryAdapter(MockGeometryCoprocessor):
    def __init__(self):
        super().__init__()
        self.last_payload = None

    def evaluate_sanitized_payload(self, payload):
        self.last_payload = dict(payload)
        return super().evaluate_sanitized_payload(payload)


class TestRuntimeEnforcement(unittest.TestCase):
    def setUp(self):
        self.audit_log = AuditLog()
        self.qams = QAMS()
        self.metrics = StabilityMetrics()
        self.interposer = InvariantInterposer()
        self.control_plane = ControlPlane(
            interposer=self.interposer,
            stability_metrics=self.metrics,
            audit_log=self.audit_log,
        )
        self.tsrl1 = TSRL1Observation()
        self.tsrl2 = TSRL2Routing()
        self.tsrl3 = TSRL3Stability()
        self.geometry = SpyGeometryAdapter()
        self.presence = MockPresenceEngine()
        self.memory = MockPersistentMemory()
        self.orchestrator = PurpleOrchestrator(
            control_plane=self.control_plane,
            interposer=self.interposer,
            qams=self.qams,
            stability_metrics=self.metrics,
            audit_log=self.audit_log,
            tsrl1=self.tsrl1,
            tsrl2=self.tsrl2,
            tsrl3=self.tsrl3,
            presence_adapter=self.presence,
            memory_adapter=self.memory,
            geometry_adapter=self.geometry,
        )

    def _safe_request(self, **overrides):
        request = {
            "action": "analyze_data",
            "agent_id": "agent_blue",
            "memory_access": "write",
            "source_tier": 0,
            "target_tier": 0,
            "touches_identity": False,
            "touches_geometry": False,
            "human_prime_signature": None,
            "payload": {
                "data_vector": [3.0, 4.0],
                "sequence_index": 7,
                "entity_id": "entity_main",
            },
        }
        request.update(overrides)
        return request

    def test_geometry_access_routes_through_interposer_and_sanitizes_payload(self):
        result = self.orchestrator.process_request(self._safe_request())
        self.assertTrue(result["allowed"])
        self.assertIsNotNone(self.geometry.last_payload)
        self.assertNotIn("entity_id", self.geometry.last_payload)
        self.assertNotIn("agent_id", self.geometry.last_payload)
        self.assertTrue(self.geometry.last_payload.get("_interposer_cleared"))
        self.assertEqual(self.geometry.last_payload.get("topology"), "fibonacci_spiral")

    def test_runtime_immutability_of_rules_and_envelope(self):
        with self.assertRaises(TypeError):
            self.interposer.rules["identity_immutable"] = False
        with self.assertRaises(AttributeError):
            self.interposer._rules = {}
        with self.assertRaises(FrozenInstanceError):
            self.interposer.default_envelope.can_write_geometry = True

    def test_automatic_tier_0_wipe_on_process_request(self):
        self.control_plane.register_agent("agent_blue", "ready")
        self.control_plane.write_tier_0(
            "agent_blue",
            "temp_key",
            {"value": 1},
            requesting_agent_id="agent_blue",
        )
        pre_state = self.control_plane.get_agent_state(
            "agent_blue",
            requesting_agent_id="agent_blue",
        )
        self.assertEqual(pre_state["tier_0_key_count"], 1)

        result = self.orchestrator.process_request(self._safe_request())
        self.assertTrue(result["allowed"])

        post_state = self.control_plane.get_agent_state(
            "agent_blue",
            requesting_agent_id="agent_blue",
        )
        self.assertEqual(post_state["tier_0_key_count"], 0)

    def test_cross_agent_isolation_enforced(self):
        self.control_plane.register_agent("agent_blue", "ready")
        self.control_plane.register_agent("agent_red", "ready")
        self.control_plane.write_tier_1(
            "agent_blue",
            "session_key",
            {"value": 1},
            requesting_agent_id="agent_blue",
        )

        with self.assertRaises(PermissionError):
            self.control_plane.get_agent_state(
                "agent_blue",
                requesting_agent_id="agent_red",
            )

        with self.assertRaises(PermissionError):
            self.control_plane.write_tier_1(
                "agent_blue",
                "other_key",
                {"value": 2},
                requesting_agent_id="agent_red",
            )

    def test_orchestrator_direct_geometry_bypass_refused(self):
        with self.assertRaises(RuntimeError):
            self.orchestrator.invoke_adapter(
                "geometry_adapter",
                "evaluate_sanitized_payload",
                payload={},
            )

    def test_continuity_fault_blocks_live_runtime_path(self):
        result = self.orchestrator.process_request(
            self._safe_request(
                session_state={"cache_continuity": True},
            )
        )
        self.assertFalse(result["allowed"])
        self.assertEqual(result["refusal_code"], "REFUSAL_EMERGENT_MEMORY")

    def test_synergy_violation_blocks_live_runtime_path(self):
        result = self.orchestrator.process_request(
            self._safe_request(
                agent_capabilities={
                    "agent_blue": {"write_t2"},
                    "agent_red": {"modify_identity"},
                }
            )
        )
        self.assertFalse(result["allowed"])
        self.assertEqual(result["refusal_code"], "REFUSAL_ENVELOPE_EXCEEDED")

    def test_drift_freeze_blocks_tier_1_and_tier_2_write_paths(self):
        high_drift = self.metrics.evaluate_drift((50.0, 50.0), sequence_index=8)
        response = self.orchestrator.coordinate_drift_response(high_drift)
        self.assertTrue(response["cooldown_applied"])
        self.assertTrue(self.control_plane.t2_writes_blocked)

        with self.assertRaises(ValueError):
            self.control_plane.write_tier_1(
                "agent_blue",
                "session_key",
                {"value": 1},
                requesting_agent_id="agent_blue",
            )

        verdict = self.interposer.evaluate({
            "action": "append_t2",
            "agent_id": "agent_blue",
            "memory_access": "write",
            "source_tier": MemoryTier.TIER_1,
            "target_tier": MemoryTier.TIER_2,
            "prevent_t2_writes": self.control_plane.t2_writes_blocked,
            "touches_identity": False,
            "touches_geometry": False,
            "human_prime_signature": "valid_human_prime",
            "payload": {"write_to_t2": True},
        })
        self.assertFalse(verdict.allowed)


if __name__ == "__main__":
    unittest.main()
