"""Regression evidence for the v4.2 contract enforcement changes."""
import unittest
from copy import deepcopy
from core.interposer import InvariantInterposer
from core.types import AuditEntry, ComponentID
import test_runtime_enforcement as fixtures


class TestContractBoundaries(unittest.TestCase):
    setUp = fixtures.TestRuntimeEnforcement.setUp
    _safe_request = fixtures.TestRuntimeEnforcement._safe_request

    def test_raw_t0_t2_both_directions_and_operations(self):
        for source, target in ((0, 2), (2, 0)):
            for access in ('read', 'write'):
                with self.subTest(source=source, access=access):
                    self.assertFalse(self.interposer.evaluate(self._safe_request(
                        source_tier=source, target_tier=target,
                        memory_access=access, human_prime_signature='human_prime')).allowed)

    def test_missing_invalid_or_conflicting_schema_refused(self):
        for key, value in [('source_tier', True), ('target_tier', '0'),
                           ('source_tier', -1), ('target_tier', 3),
                           ('memory_access', None), ('agent_id', ''),
                           ('requesting_agent_id', 'another_agent')]:
            with self.subTest(key=key, value=value):
                self.assertFalse(self.interposer.evaluate(self._safe_request(**{key: value})).allowed)
        for key in ('source_tier', 'target_tier', 'memory_access', 'agent_id'):
            request = self._safe_request()
            del request[key]
            self.assertFalse(self.interposer.evaluate(request).allowed)

    def test_symbolic_authority_cannot_grant_or_be_reused(self):
        for source, target in ((1, 2), (2, 2), (2, 1)):
            request = self._safe_request(source_tier=source, target_tier=target,
                                        human_prime_signature='approved_by_joe')
            for _ in range(2):
                self.assertFalse(self.interposer.evaluate(request).allowed)
        self.assertFalse(self.interposer.verify_human_prime_signature({'human_prime_signature': 'valid'}))

    def test_local_explicit_read_and_write_remain_allowed(self):
        for tier in (0, 1):
            for access in ('read', 'write'):
                self.assertTrue(self.interposer.evaluate(self._safe_request(
                    source_tier=tier, target_tier=tier, memory_access=access)).allowed)

    def test_upward_write_denied_despite_benign_action(self):
        self.assertFalse(self.interposer.evaluate(self._safe_request(
            action='analyze', source_tier=0, target_tier=1)).allowed)

    def test_nested_geometry_sanitization_does_not_mutate_input(self):
        request = self._safe_request(payload={'nested': [{'session_id': 'secret', 'radial_drift': 0.1}]})
        before = deepcopy(request)
        self.interposer.evaluate_geometry_request(request)
        self.assertEqual(request, before)
        self.assertNotIn('session_id', self.geometry.last_payload['nested'][0])
        self.assertEqual(self.geometry.last_payload['nested'][0]['radial_drift'], 0.1)

    def test_geometry_cannot_be_rebound_or_unsealed_via_normal_assignment(self):
        with self.assertRaises(RuntimeError):
            self.interposer.attach_geometry_adapter(self.geometry)
        with self.assertRaises(AttributeError):
            self.interposer._geometry_adapter = object()
        with self.assertRaises(AttributeError):
            self.interposer._sealed = False

    def test_adapter_gate_denies_memory_audit_unknown_and_missing_gate(self):
        for adapter, method in [('memory_adapter', 'append_event_log'),
                                ('audit_log', 'get_entries'), ('unknown', 'anything')]:
            self.assertFalse(self.interposer.check_adapter_call(adapter, method, {}).allowed)
        self.orchestrator.interposer = object()
        with self.assertRaises(RuntimeError):
            self.orchestrator._interposer_adapter_check('presence_adapter', 'get_presence_summary', {})

    def test_audit_snapshots_survive_caller_mutation_and_tier_cleanup(self):
        self.control_plane.log_action('example', 'agent_blue', 'OK', {'nested': ['evidence']})
        snapshots = self.audit_log.get_entries()
        target = snapshots[-1]
        target.details['nested'].append('changed')
        self.control_plane.clear_tier_0()
        self.control_plane.clear_tier_1()
        self.assertEqual(self.audit_log.get_entries_by_action('example')[0].details['nested'], ['evidence'])
        original = self.audit_log.get_entries_by_action('example')[0]
        self.audit_log.record(original)
        original.details['nested'].clear()
        self.assertEqual(self.audit_log.get_entries_by_action('example')[-1].details['nested'], ['evidence'])
        for query in (lambda: self.audit_log.get_entries_by_component(ComponentID.CONTROL_PLANE),
                      lambda: self.audit_log.get_entries_by_result_code('OK'),
                      lambda: self.audit_log.get_entries_by_trace(original.trace_id)):
            for entry in query():
                entry.details.clear()
        self.assertTrue(self.audit_log.get_entries_by_action('example')[-1].details)

    def test_runtime_evidence_not_written_to_agent_memory_or_returned_as_history(self):
        result = self.orchestrator.process_request(self._safe_request())
        self.assertTrue(result['allowed'])
        self.assertTrue(len(self.audit_log))
        self.assertEqual(sum(self.memory.tier_entry_count().values()), 0)
        self.assertEqual(result['execution_trace_snapshot'], [])

    def test_tier_freeze_cannot_be_bypassed_through_nested_aliases(self):
        data = {'nested': ['original']}
        self.control_plane.write_tier_1('agent_blue', 'key', data)
        self.control_plane.apply_interposer_directive({'type': 'memory_freeze'})
        data['nested'].append('changed')
        snapshot = self.control_plane.tier_1_store
        snapshot['agent_blue']['key']['nested'].append('changed_again')
        self.assertEqual(self.control_plane.tier_1_store['agent_blue']['key']['nested'], ['original'])

    def test_mock_rejects_invalid_tier_instead_of_defaulting(self):
        for value in (None, True, '2', -1, 3):
            self.assertEqual(self.memory.append_event_log({'tier': value})['status'], 'refused')
            self.assertEqual(self.memory.query_recall({'tier': value}), [])
        self.assertEqual(sum(self.memory.tier_entry_count().values()), 0)

    def test_mock_recall_isolated_and_detached(self):
        payload = {'nested': ['original']}
        self.memory.append_event_log({'tier': 0, 'actor': 'demo_agent', 'payload': payload})
        self.memory.append_event_log({'tier': 0, 'actor': 'other_agent', 'payload': {'secret': 1}})
        payload['nested'].clear()
        records = self.memory.query_recall({'tier': 0, 'actor': 'demo_agent'})
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['payload']['nested'], ['original'])
        records[0]['payload']['nested'].clear()
        self.assertEqual(self.memory.query_recall({'tier': 0, 'actor': 'demo_agent'})[0]['payload']['nested'], ['original'])

    def test_mock_symbolic_token_never_creates_t2_data(self):
        self.assertEqual(self.memory.append_event_log({'tier': 2}, 'human_prime_authorized')['status'], 'refused')
        self.assertEqual(self.memory.query_recall({'tier': 2}, 'human_prime_authorized'), [])
        self.assertEqual(sum(self.memory.tier_entry_count().values()), 0)

    def test_geometry_refusal_and_malformed_result_cannot_be_success(self):
        for result in ({'status': 'refused'}, {}, None):
            self.interposer.evaluate_geometry_request = lambda request, r=result: r
            response = self.orchestrator.process_request(self._safe_request())
            self.assertFalse(response['allowed'])

    def test_missing_geometry_gate_cannot_be_success(self):
        class IncompleteGate:
            evaluate = self.interposer.evaluate
        self.orchestrator.interposer = IncompleteGate()
        self.assertFalse(self.orchestrator.process_request(self._safe_request())['allowed'])
