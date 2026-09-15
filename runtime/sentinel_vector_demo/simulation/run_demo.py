"""
Sentinel Vector / Stability Engine v4 — Demo Harness
=====================================================

Runs all six demo scenarios in sequence, printing section headers and results
with ANSI colour codes.  At the end, the full audit log is saved to
simulation/demo_audit_log.json.
"""

from __future__ import annotations

import json
import os
import sys

# ---------------------------------------------------------------------------
# Path bootstrap — must come before any sentinel_vector_demo imports
# ---------------------------------------------------------------------------
# Add the sentinel_vector_demo root (for `from core.xxx import ...`)
_DEMO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _DEMO_ROOT)
# Also add workspace root so mock files can resolve `sentinel_vector_demo.*` imports
_WORKSPACE_ROOT = os.path.dirname(_DEMO_ROOT)
if _WORKSPACE_ROOT not in sys.path:
    sys.path.insert(1, _WORKSPACE_ROOT)

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------
from core.types import (
    AuditEntry,
    ComponentID,
    DriftSeverity,
    MemoryTier,
    OperationalMode,
    RefusalCode,
    _trace_id,
)
from core.audit_log import AuditLog
from core.qams import QAMS
from core.stability_metrics import StabilityMetrics
from core.interposer import InvariantInterposer
from core.control_plane import ControlPlane
from tsrl.tsrl1_observation import TSRL1Observation
from tsrl.tsrl2_routing import TSRL2Routing
from tsrl.tsrl3_stability import TSRL3Stability
from orchestration.purple_orchestrator import PurpleOrchestrator
from mocks.mock_presence_engine import MockPresenceEngine
from mocks.mock_persistent_memory import MockPersistentMemory
from mocks.mock_geometry_coprocessor import MockGeometryCoprocessor

# ---------------------------------------------------------------------------
# ANSI colour helpers
# ---------------------------------------------------------------------------
RESET  = "\033[0m"
BOLD   = "\033[1m"
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
CYAN   = "\033[96m"
WHITE  = "\033[97m"


def pass_msg(text: str) -> str:
    return f"{GREEN}{BOLD}[PASS]{RESET} {text}"


def fail_msg(text: str) -> str:
    return f"{RED}{BOLD}[FAIL]{RESET} {text}"


def warn_msg(text: str) -> str:
    return f"{YELLOW}{BOLD}[WARN]{RESET} {text}"


def info_msg(text: str) -> str:
    return f"{BLUE}[INFO]{RESET} {text}"


def section(title: str) -> None:
    print(f"\n{CYAN}{'='*80}{RESET}")
    print(f"{BOLD}{WHITE}{title}{RESET}")
    print(f"{CYAN}{'='*80}{RESET}")


def check(condition: bool, label: str) -> bool:
    """Print PASS/FAIL for a single assertion and return the bool."""
    if condition:
        print(pass_msg(label))
    else:
        print(fail_msg(label))
    return condition


# ---------------------------------------------------------------------------
# Scenario 1 — Normal Safe Request
# ---------------------------------------------------------------------------

def scenario_1_safe_request(orchestrator: PurpleOrchestrator,
                              metrics: StabilityMetrics,
                              control_plane: ControlPlane) -> bool:
    """Normal safe request — full pipeline, all checks pass."""
    section("SCENARIO 1: Normal Safe Request")
    passed = True

    # Register an agent
    control_plane.register_agent("agent_blue", "ready")
    print(info_msg("Registered agent_blue (status=ready)"))

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
            "data_vector": [0.3, 0.4],
            "sequence_index": 5,
            "entity_id": "entity_001",
            "task": "structural_analysis",
        },
    }

    print(info_msg("Submitting safe request through full 10-step pipeline…"))
    result = orchestrator.process_request(request)

    # Print key results
    print(info_msg(f"  allowed          : {result.get('allowed')}"))
    print(info_msg(f"  trace_id         : {result.get('trace_id')}"))
    print(info_msg(f"  operational_mode : {result.get('operational_mode')}"))

    interposer_v = result.get("interposer_verdict", {})
    print(info_msg(f"  interposer.allowed   : {interposer_v.get('allowed')}"))
    print(info_msg(f"  interposer.trace_hash: {interposer_v.get('trace_hash')}"))

    stability_cert = result.get("stability_certificate", {})
    print(info_msg(f"  stability certified  : {stability_cert.get('certified')}"))

    audit_len = len(result.get("audit_trail", []))
    print(info_msg(f"  audit_trail steps    : {audit_len}"))

    # Assertions
    passed &= check(result.get("allowed") is True,
                    "result['allowed'] is True")
    passed &= check(result.get("operational_mode") == "NORMAL",
                    "operational_mode is NORMAL")
    passed &= check(interposer_v.get("allowed") is True,
                    "interposer verdict is allowed")
    passed &= check(stability_cert.get("certified") is True,
                    "stability baseline certified")

    print(f"\n{BOLD}Scenario 1 result: {'PASS' if passed else 'FAIL'}{RESET}")
    return passed


# ---------------------------------------------------------------------------
# Scenario 2 — Drift Escalation Event
# ---------------------------------------------------------------------------

def scenario_2_drift_escalation(orchestrator: PurpleOrchestrator,
                                  metrics: StabilityMetrics) -> bool:
    """Drift escalation — metrics detect drift, Interposer handles cooldown."""
    section("SCENARIO 2: Drift Escalation Event")
    passed = True

    # Use StabilityMetrics to evaluate a drifted vector
    print(info_msg("Evaluating drifted vector (50.0, 50.0) at sequence_index=8…"))
    drift_report = metrics.evaluate_drift(vector=(50.0, 50.0), sequence_index=8)

    print(info_msg(f"  Drift severity   : {drift_report.severity.name}"))
    print(info_msg(f"  Radial drift     : {drift_report.radial_drift:.4f}"))
    print(info_msg(f"  Phase noise      : {drift_report.phase_noise:.4f}"))
    print(info_msg(f"  Vector magnitude : {drift_report.vector_magnitude:.4f}"))
    print(info_msg(f"  Drift details    : {drift_report.details}"))

    # Severity should be HIGH or CRITICAL for such an extreme vector
    is_severe = drift_report.severity in (DriftSeverity.HIGH, DriftSeverity.CRITICAL)
    passed &= check(is_severe,
                    f"Drift severity is HIGH or CRITICAL (got {drift_report.severity.name})")

    # Coordinate drift response through orchestrator
    print(info_msg("Coordinating drift response through PurpleOrchestrator…"))
    response = orchestrator.coordinate_drift_response(drift_report)

    print(info_msg(f"  drift_severity   : {response.get('drift_severity')}"))
    print(info_msg(f"  cooldown_applied : {response.get('cooldown_applied')}"))
    print(info_msg(f"  operational_mode : {response.get('operational_mode')}"))

    escalation = response.get("escalation_verdict", {})
    print(info_msg(f"  escalation cooldown_required : {escalation.get('cooldown_required')}"))
    print(info_msg(f"  escalation envelope_narrowing: {escalation.get('envelope_narrowing')}"))
    print(info_msg(f"  escalation t2_write_blocked  : {escalation.get('t2_write_blocked')}"))

    # Verify cooldown was applied
    passed &= check(response.get("cooldown_applied") is True,
                    "cooldown_applied is True")
    passed &= check(response.get("operational_mode") != "NORMAL",
                    "operational_mode changed from NORMAL (cooldown active)")
    passed &= check(escalation.get("cooldown_required") is True,
                    "escalation_verdict indicates cooldown_required")

    print(f"\n{BOLD}Scenario 2 result: {'PASS' if passed else 'FAIL'}{RESET}")
    return passed


# ---------------------------------------------------------------------------
# Scenario 3 — Unauthorized Memory Write Attempt
# ---------------------------------------------------------------------------

def scenario_3_unauthorized_memory_write(interposer: InvariantInterposer,
                                          memory: MockPersistentMemory) -> bool:
    """Unauthorized Tier 2 write — blocked at Interposer and adapter level."""
    section("SCENARIO 3: Unauthorized Memory Write Attempt")
    passed = True

    # ── Test 1: Interposer blocks T2 write without signature ──────────────
    print(info_msg("Test 1: Interposer three-phase check on T1→T2 write without signature"))
    request = {
        "action": "write_memory",
        "agent_id": "agent_red",
        "memory_access": "write",
        "source_tier": 1,
        "target_tier": 2,
        "touches_identity": False,
        "touches_geometry": False,
        "human_prime_signature": None,
        "payload": {"data": "attempt_to_persist"},
    }
    verdict = interposer.evaluate(request)

    print(info_msg(f"  verdict.allowed      : {verdict.allowed}"))
    print(info_msg(f"  verdict.refusal_code : {verdict.refusal_code}"))
    print(info_msg(f"  invariant_violated   : {verdict.invariant_violated}"))
    print(info_msg(f"  safe_alternative     : {verdict.safe_alternative}"))
    print(info_msg(f"  trace_hash           : {verdict.trace_hash}"))

    # Assertions for Test 1
    passed &= check(verdict.allowed is False,
                    "Interposer verdict.allowed is False (T2 write blocked)")
    passed &= check(
        verdict.refusal_code in (
            RefusalCode.MEMORY_UNAUTHORIZED_T2_WRITE,
            RefusalCode.MEMORY_CROSS_TIER_WRITE,
        ),
        f"refusal_code is MEMORY_UNAUTHORIZED_T2_WRITE or MEMORY_CROSS_TIER_WRITE "
        f"(got {verdict.refusal_code})"
    )

    # ── Test 2: MockPersistentMemory blocks T2 write without consent token ─
    print(info_msg("\nTest 2: Mock memory adapter blocks T2 write without consent_token"))
    result = memory.append_event_log(
        event={"tier": 2, "data": "unauthorized_write", "key": "secret"},
        consent_token=None,
    )

    print(info_msg(f"  result.status        : {result.get('status')}"))
    print(info_msg(f"  result.refusal_code  : {result.get('refusal_code')}"))
    print(info_msg(f"  result.reason        : {result.get('reason')}"))

    # Assertions for Test 2
    passed &= check(result.get("status") == "refused",
                    "Memory adapter result.status is 'refused'")
    # Compare by .value string to handle dual-import-path enum identity issues
    _rc = result.get("refusal_code")
    _rc_val = _rc.value if hasattr(_rc, 'value') else str(_rc)
    passed &= check(
        _rc_val == RefusalCode.MEMORY_UNAUTHORIZED_T2_WRITE.value,
        f"Memory adapter refusal_code is MEMORY_UNAUTHORIZED_T2_WRITE "
        f"(got {_rc})"
    )

    print(f"\n{BOLD}Scenario 3 result: {'PASS' if passed else 'FAIL'}{RESET}")
    return passed


# ---------------------------------------------------------------------------
# Scenario 4 — Geometry Violation Attempt
# ---------------------------------------------------------------------------

def scenario_4_geometry_violation(interposer: InvariantInterposer,
                                    geometry: MockGeometryCoprocessor) -> bool:
    """Geometry violation — Interposer blocks before geometry sees it."""
    section("SCENARIO 4: Geometry Violation Attempt")
    passed = True

    # ── Test 1: Interposer blocks geometry mutation via touches_geometry flag ─
    print(info_msg("Test 1: Interposer blocks request with touches_geometry=True"))
    request = {
        "action": "modify_topology",
        "agent_id": "agent_red",
        "memory_access": "write",
        "source_tier": 0,
        "target_tier": 0,
        "touches_identity": False,
        "touches_geometry": True,
        "human_prime_signature": None,
        "payload": {"modify_geometry": True, "new_manifold": "custom"},
    }
    verdict = interposer.evaluate(request)

    print(info_msg(f"  verdict.allowed      : {verdict.allowed}"))
    print(info_msg(f"  verdict.refusal_code : {verdict.refusal_code}"))
    print(info_msg(f"  invariant_violated   : {verdict.invariant_violated}"))

    passed &= check(verdict.allowed is False,
                    "Interposer verdict.allowed is False (geometry mutation blocked)")
    passed &= check(
        verdict.refusal_code == RefusalCode.GEOMETRY_MUTATION,
        f"refusal_code is GEOMETRY_MUTATION (got {verdict.refusal_code})"
    )

    # ── Test 2: Geometry adapter refuses unsanitized payloads ─────────────
    print(info_msg("\nTest 2: Geometry adapter refuses payload with identity/session keys"))
    unsanitized = {"agent_id": "red", "session_id": "s123", "data": [1.0, 2.0]}
    result2 = geometry.evaluate_sanitized_payload(unsanitized)

    print(info_msg(f"  result.status        : {result2.get('status')}"))
    print(info_msg(f"  result.refusal_code  : {result2.get('refusal_code')}"))
    print(info_msg(f"  result.reason        : {result2.get('reason')}"))

    passed &= check(result2.get("status") == "refused",
                    "Geometry adapter refuses unsanitized payload (status=refused)")
    # Compare by .value string to handle dual-import-path enum identity issues
    _rc2 = result2.get("refusal_code")
    _rc2_val = _rc2.value if hasattr(_rc2, 'value') else str(_rc2)
    passed &= check(
        _rc2_val in (
            RefusalCode.GEOMETRY_UNSANITIZED_INPUT.value,
            RefusalCode.GEOMETRY_MUTATION.value,
        ),
        f"refusal_code is GEOMETRY_UNSANITIZED_INPUT or GEOMETRY_MUTATION "
        f"(got {_rc2})"
    )

    # ── Test 3: Geometry adapter refuses mutation attempts ─────────────────
    # MUTATION_FIELDS = {"mutate", "rewrite_geometry", "override_topology",
    #                    "modify_manifold", "set_geometry", "patch_geometry"}
    # Use "modify_manifold" and "set_geometry" — both are in the frozenset.
    print(info_msg("\nTest 3: Geometry adapter refuses mutation attempt"))
    mutation = {"modify_manifold": True, "set_geometry": "custom_topology"}
    result3 = geometry.evaluate_sanitized_payload(mutation)

    print(info_msg(f"  result.status        : {result3.get('status')}"))
    print(info_msg(f"  result.refusal_code  : {result3.get('refusal_code')}"))
    print(info_msg(f"  result.reason        : {result3.get('reason')}"))

    passed &= check(result3.get("status") == "refused",
                    "Geometry adapter refuses mutation attempt (status=refused)")
    _rc3 = result3.get("refusal_code")
    _rc3_val = _rc3.value if hasattr(_rc3, 'value') else str(_rc3)
    passed &= check(
        _rc3_val == RefusalCode.GEOMETRY_MUTATION.value,
        f"refusal_code is GEOMETRY_MUTATION (got {_rc3})"
    )

    print(f"\n{BOLD}Scenario 4 result: {'PASS' if passed else 'FAIL'}{RESET}")
    return passed


# ---------------------------------------------------------------------------
# Scenario 5 — Cooldown and Recovery Flow
# ---------------------------------------------------------------------------

def scenario_5_cooldown_recovery(control_plane: ControlPlane,
                                   audit_log: AuditLog) -> bool:
    """Cooldown and recovery — deterministic error recovery sequence."""
    section("SCENARIO 5: Cooldown and Recovery Flow")
    passed = True

    # This scenario needs a fresh fixture, not a mode reset on the runtime
    # already cooled down by previous scenarios. Share operator evidence only.
    control_plane = ControlPlane(InvariantInterposer(), StabilityMetrics(), audit_log)
    # Register agent and write some data to T0 and T1
    control_plane.register_agent("agent_green", "ready")
    control_plane.write_tier_0("agent_green", "temp_data", {"value": 42})
    control_plane.write_tier_1("agent_green", "session_data", {"context": "test"})
    print(info_msg("Registered agent_green, wrote T0 key 'temp_data', T1 key 'session_data'"))

    # Verify data is present before recovery
    pre_state = control_plane.get_agent_state("agent_green")
    print(info_msg(f"  Pre-recovery T0 key count : {pre_state['tier_0_key_count']}"))
    print(info_msg(f"  Pre-recovery T1 key count : {pre_state['tier_1_key_count']}"))

    # Simulate fault — note: execute_recovery uses 'agent_id' key, not 'faulted_agent'
    fault_info = {
        "agent_id": "agent_green",          # control_plane uses this key
        "fault_type": "drift_detected",
        "severity": "HIGH",
        "clear_tier_1": True,
        "allow_retry": True,                # actual key used by execute_recovery
    }

    print(info_msg("Executing recovery sequence…"))
    recovery_result = control_plane.execute_recovery(fault_info)

    print(info_msg(f"  status           : {recovery_result.get('status')}"))
    print(info_msg(f"  agent_id         : {recovery_result.get('agent_id')}"))
    print(info_msg(f"  fault_type       : {recovery_result.get('fault_type')}"))
    print(info_msg(f"  prior_mode       : {recovery_result.get('prior_mode')}"))
    print(info_msg(f"  new_mode         : {recovery_result.get('new_mode')}"))
    print(info_msg(f"  tier_1_cleared   : {recovery_result.get('tier_1_cleared')}"))
    print(info_msg(f"  result_code      : {recovery_result.get('result_code')}"))

    recovery_steps = recovery_result.get("recovery_steps", [])
    print(info_msg(f"  recovery_steps ({len(recovery_steps)} steps):"))
    for step in recovery_steps:
        print(info_msg(f"    • {step}"))

    # Geometry-untouched assertion in recovery steps
    geometry_assertion = any("geometry_untouched" in s for s in recovery_steps)
    t0_cleared_step    = any("tier_0_cleared" in s for s in recovery_steps)
    t1_cleared_step    = any("tier_1_cleared" in s for s in recovery_steps)

    passed &= check(recovery_result.get("status") == "recovery_complete",
                    "recovery_result.status is 'recovery_complete'")
    passed &= check(recovery_result.get("result_code") == "RECOVERY_EXECUTED",
                    "result_code is RECOVERY_EXECUTED")
    passed &= check(recovery_result.get("tier_1_cleared") is True,
                    "tier_1_cleared is True (T1 cleared per fault directive)")
    passed &= check(geometry_assertion,
                    "recovery_steps includes geometry_untouched assertion (GC4)")
    passed &= check(t0_cleared_step,
                    "recovery_steps includes tier_0_cleared step")
    passed &= check(t1_cleared_step,
                    "recovery_steps includes tier_1_cleared step")

    # Show recent audit log entries covering the recovery
    all_entries = audit_log.get_entries()
    recent = all_entries[-8:]
    print(info_msg(f"\nLast {len(recent)} audit log entries (recovery path):"))
    for e in recent:
        comp_val = e.component.value if isinstance(e.component, ComponentID) else str(e.component)
        print(f"  {CYAN}[{comp_val}]{RESET} {e.action} → {e.result_code}")

    total_audit = len(all_entries)
    print(info_msg(f"  Total audit entries so far: {total_audit}"))

    print(f"\n{BOLD}Scenario 5 result: {'PASS' if passed else 'FAIL'}{RESET}")
    return passed


# ---------------------------------------------------------------------------
# Scenario 6 — Adapter-Backed End-to-End Cycle
# ---------------------------------------------------------------------------

def scenario_6_adapter_end_to_end(orchestrator: PurpleOrchestrator,
                                    presence: MockPresenceEngine,
                                    memory: MockPersistentMemory,
                                    geometry: MockGeometryCoprocessor,
                                    metrics: StabilityMetrics) -> bool:
    """End-to-end adapter cycle — all three adapters invoked safely."""
    section("SCENARIO 6: Adapter-Backed End-to-End Cycle")
    passed = True

    if orchestrator.operational_mode != OperationalMode.NORMAL:
        (
            _, _, metrics, _, _, _, _, _,
            orchestrator, presence, memory, geometry,
        ) = initialise_components()
        print(info_msg("Reinitialised fresh components for scenario 6 after prior cooldown state"))

    # ── 1. Presence Engine ────────────────────────────────────────────────
    print(info_msg("\n[1/4] Presence Engine: ingest snapshot + compute overlay + summary"))
    snapshot = {
        "entity_id": "entity_main",
        "state": {"mode": "active", "coherence": 0.95},
    }
    presence_receipt = presence.ingest_state_snapshot(snapshot)
    print(info_msg(f"  ingest_state_snapshot status : {presence_receipt.get('status')}"))
    print(info_msg(f"  receipt_id                   : {presence_receipt.get('receipt_id')}"))

    overlay = presence.compute_overlay_annotations(snapshot)
    print(info_msg(f"  compute_overlay_annotations  : {overlay.get('status')} | profile={overlay.get('profile_tag')}"))

    summary = presence.get_presence_summary("entity_main")
    print(info_msg(f"  get_presence_summary status  : {summary.get('status')}"))
    print(info_msg(f"  coherence_signal             : {summary.get('coherence_signal')}"))
    print(info_msg(f"  snapshot_count               : {summary.get('snapshot_count')}"))

    passed &= check(presence_receipt.get("status") == "accepted",
                    "Presence snapshot accepted")
    passed &= check(overlay.get("status") == "computed",
                    "Overlay computed successfully")
    passed &= check(summary.get("status") == "ok",
                    "Presence summary returned ok")

    # ── 2. Persistent Memory: T0, T1, and T2 writes ───────────────────────
    print(info_msg("\n[2/4] Persistent Memory: T0 write, T1 write, T2 write with consent"))
    # actor="demo_agent" has T0/T1 write consent seeded in MockPersistentMemory
    t0_result = memory.append_event_log({"tier": 0, "data": "ephemeral_note", "actor": "demo_agent"})
    print(info_msg(f"  T0 write status : {t0_result.get('status')} | tier={t0_result.get('tier')}"))

    t1_result = memory.append_event_log({"tier": 1, "data": "session_record", "actor": "demo_agent"})
    print(info_msg(f"  T1 write status : {t1_result.get('status')} | tier={t1_result.get('tier')}"))

    t2_result = memory.append_event_log(
        {"tier": 2, "data": "authorized_persistent_record"},
        consent_token="human_prime_authorized_token",
    )
    print(info_msg(f"  T2 write status : {t2_result.get('status')} | tier={t2_result.get('tier')}"))

    passed &= check(t0_result.get("status") == "written",
                    "T0 write accepted")
    passed &= check(t1_result.get("status") == "written",
                    "T1 write accepted")
    passed &= check(t2_result.get("status") == "refused",
                    "T2 refused: symbolic token is not authority")

    # ── 3. Geometry Co-Processor: sanitized payload evaluation ────────────
    print(info_msg("\n[3/4] Geometry Co-Processor: Fibonacci spiral URI payload evaluation"))
    uri_payload = metrics.prepare_data_for_uri(
        vector=(3.0, 4.0), sequence_index=7, entity_id="entity_main"
    )
    print(info_msg(f"  URI payload keys : {list(uri_payload.keys())}"))
    print(info_msg(f"  sequence_index   : {uri_payload.get('sequence_index')}"))
    print(info_msg(f"  radial_drift     : {uri_payload.get('radial_drift'):.4f}"))
    print(info_msg(f"  phase_noise      : {uri_payload.get('phase_noise'):.4f}"))
    print(info_msg(f"  entity_hash      : {uri_payload.get('entity_hash')}"))

    geo_result = geometry.evaluate_sanitized_payload(uri_payload)
    print(info_msg(f"  evaluate result  : status={geo_result.get('status', 'ok')} | coherent={geo_result.get('coherent')}"))
    print(info_msg(f"  topology         : {geo_result.get('topology')}"))
    print(info_msg(f"  constraint_res   : {geo_result.get('constraint_resolution')}"))

    geo_ok = geo_result.get("coherent") is not None  # result came back (not refused)
    passed &= check(geo_result.get("status") != "refused",
                    "Geometry adapter accepted sanitized URI payload")
    passed &= check(geo_result.get("topology") == "fibonacci_spiral",
                    "Geometry topology is fibonacci_spiral")

    # ── 4. Full orchestrator request with adapters ─────────────────────────
    print(info_msg("\n[4/4] Full orchestrator process_request (geometry + presence + memory adapters)"))
    request = {
        "action": "full_cycle_analysis",
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
    full_result = orchestrator.process_request(request)

    print(info_msg(f"  allowed          : {full_result.get('allowed')}"))
    print(info_msg(f"  trace_id         : {full_result.get('trace_id')}"))
    print(info_msg(f"  operational_mode : {full_result.get('operational_mode')}"))

    adapter_results = full_result.get("result", {})
    geo_res   = adapter_results.get("geometry", {})
    pres_res  = adapter_results.get("presence", {})
    mem_res   = adapter_results.get("memory", {})
    print(info_msg(f"  geometry result keys   : {list(geo_res.keys()) if geo_res else '(skipped)'}"))
    print(info_msg(f"  presence result keys   : {list(pres_res.keys()) if pres_res else '(skipped)'}"))
    print(info_msg(f"  memory result keys     : {list(mem_res.keys()) if mem_res else '(skipped)'}"))

    passed &= check(full_result.get("allowed") is True,
                    "Full cycle orchestrator result is allowed")
    passed &= check(full_result.get("operational_mode") == "NORMAL",
                    "operational_mode is NORMAL after full cycle")

    print(f"\n{BOLD}Scenario 6 result: {'PASS' if passed else 'FAIL'}{RESET}")
    return passed


# ---------------------------------------------------------------------------
# Adapter shims
# ---------------------------------------------------------------------------
# The PurpleOrchestrator's invoke_adapter() forwards all keyword arguments
# (including 'trace_id') to the adapter methods.  The mock implementations
# only accept their documented parameters, so we wrap them with shims that
# silently absorb extra kwargs.

class _GeometryShim:
    """
    Thin shim over MockGeometryCoprocessor that absorbs extra keyword
    arguments (e.g. trace_id) forwarded by PurpleOrchestrator.invoke_adapter.
    Delegates all substantive logic to the underlying mock.
    """
    def __init__(self, inner: MockGeometryCoprocessor) -> None:
        self._inner = inner

    def evaluate_sanitized_payload(self, payload=None, **_ignored):
        return self._inner.evaluate_sanitized_payload(payload or {})

    def compute_curvature_metrics(self, signal=None, **_ignored):
        return self._inner.compute_curvature_metrics(signal or {})

    # Forward any other attribute access to the inner mock
    def __getattr__(self, name):
        return getattr(self._inner, name)


class _PresenceShim:
    """
    Thin shim over MockPresenceEngine.  The orchestrator calls
    get_presence_summary(trace_id=...) but the mock expects entity_id.
    We derive entity_id from the first positional arg or fallback to ""
    and absorb extra kwargs.
    """
    def __init__(self, inner: MockPresenceEngine) -> None:
        self._inner = inner

    def get_presence_summary(self, entity_id: str = "", **_ignored):
        return self._inner.get_presence_summary(entity_id)

    def ingest_state_snapshot(self, snapshot=None, **_ignored):
        return self._inner.ingest_state_snapshot(snapshot or {})

    def compute_overlay_annotations(self, snapshot=None, **_ignored):
        return self._inner.compute_overlay_annotations(snapshot or {})

    # Forward any other attribute access to the inner mock
    def __getattr__(self, name):
        return getattr(self._inner, name)


class _MemoryShim:
    """
    Thin shim over MockPersistentMemory that absorbs extra kwargs.
    """
    def __init__(self, inner: MockPersistentMemory) -> None:
        self._inner = inner

    def append_event_log(self, event=None, consent_token=None, **_ignored):
        return self._inner.append_event_log(event or {}, consent_token=consent_token)

    def query_recall(self, filter_spec=None, consent_token=None, **_ignored):
        return self._inner.query_recall(filter_spec or {}, consent_token=consent_token)

    def check_consent(self, scope: str, actor: str, **_ignored):
        return self._inner.check_consent(scope, actor)

    def export_audit_entries(self, **_ignored):
        return self._inner.export_audit_entries()

    # Forward any other attribute access to the inner mock
    def __getattr__(self, name):
        return getattr(self._inner, name)


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

def initialise_components():
    """Construct and wire all Stability Engine v4 components."""
    audit_log     = AuditLog()
    qams          = QAMS()
    metrics       = StabilityMetrics()
    interposer    = InvariantInterposer()
    control_plane = ControlPlane(
        interposer=interposer,
        stability_metrics=metrics,
        audit_log=audit_log,
    )
    tsrl1 = TSRL1Observation()
    tsrl2 = TSRL2Routing()
    tsrl3 = TSRL3Stability()

    # Underlying mock instances (used directly in scenarios and by the orchestrator)
    _presence_inner = MockPresenceEngine()
    _memory_inner = MockPersistentMemory()
    _geometry_inner = MockGeometryCoprocessor()

    orchestrator = PurpleOrchestrator(
        control_plane=control_plane,
        interposer=interposer,
        qams=qams,
        stability_metrics=metrics,
        audit_log=audit_log,
        tsrl1=tsrl1,
        tsrl2=tsrl2,
        tsrl3=tsrl3,
        presence_adapter=_presence_inner,
        memory_adapter=_memory_inner,
        geometry_adapter=_geometry_inner,
    )

    # Return the raw inner mocks for direct scenario use
    return (
        audit_log, qams, metrics, interposer, control_plane,
        tsrl1, tsrl2, tsrl3,
        orchestrator, _presence_inner, _memory_inner, _geometry_inner,
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    print(f"\n{BOLD}{CYAN}{'#'*80}{RESET}")
    print(f"{BOLD}{CYAN}  Sentinel Vector / Stability Engine v4 — Demo Harness{RESET}")
    print(f"{BOLD}{CYAN}{'#'*80}{RESET}")

    # ── Initialise ────────────────────────────────────────────────────────
    print(info_msg("Initialising all Stability Engine v4 components…"))
    (
        audit_log, qams, metrics, interposer, control_plane,
        tsrl1, tsrl2, tsrl3,
        orchestrator, presence, memory, geometry,
    ) = initialise_components()
    print(info_msg("All components initialised."))

    # ── Run scenarios ─────────────────────────────────────────────────────
    results: list[tuple[str, bool]] = []

    scenarios = [
        ("Scenario 1: Normal Safe Request",
         lambda: scenario_1_safe_request(orchestrator, metrics, control_plane)),
        ("Scenario 2: Drift Escalation Event",
         lambda: scenario_2_drift_escalation(orchestrator, metrics)),
        ("Scenario 3: Unauthorized Memory Write",
         lambda: scenario_3_unauthorized_memory_write(interposer, memory)),
        ("Scenario 4: Geometry Violation Attempt",
         lambda: scenario_4_geometry_violation(interposer, geometry)),
        ("Scenario 5: Cooldown and Recovery",
         lambda: scenario_5_cooldown_recovery(control_plane, audit_log)),
        ("Scenario 6: Adapter-Backed End-to-End",
         lambda: scenario_6_adapter_end_to_end(orchestrator, presence, memory, geometry, metrics)),
    ]

    for name, fn in scenarios:
        try:
            result = fn()
        except Exception as exc:  # noqa: BLE001
            import traceback as _tb
            print(f"\n{RED}[EXCEPTION in {name}]{RESET}")
            _tb.print_exc()
            result = False
        results.append((name, result))

    # ── Final summary ─────────────────────────────────────────────────────
    section("FINAL SUMMARY")

    passed_count = sum(1 for _, r in results if r)
    failed_count = len(results) - passed_count

    print(f"\n  {BOLD}Total scenarios : {len(results)}{RESET}")
    print(f"  {GREEN}{BOLD}Passed          : {passed_count}{RESET}")
    if failed_count:
        print(f"  {RED}{BOLD}Failed          : {failed_count}{RESET}")
    else:
        print(f"  {GREEN}Failed          : {failed_count}{RESET}")

    print()
    for name, result in results:
        status_str = f"{GREEN}PASS{RESET}" if result else f"{RED}FAIL{RESET}"
        print(f"  [{status_str}] {name}")

    # ── Audit log summary ─────────────────────────────────────────────────
    all_entries = audit_log.get_entries()
    print(f"\n{BOLD}Audit Log Summary:{RESET}")
    print(info_msg(f"  Total entries : {len(all_entries)}"))

    # Count by component
    from collections import Counter
    comp_counts: Counter = Counter()
    for e in all_entries:
        comp_val = e.component.value if isinstance(e.component, ComponentID) else str(e.component)
        comp_counts[comp_val] += 1

    print(info_msg("  Entries by component:"))
    for comp, count in sorted(comp_counts.items(), key=lambda x: -x[1]):
        print(f"    {CYAN}{comp}{RESET}: {count}")

    # ── Save audit log ────────────────────────────────────────────────────
    output_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "demo_audit_log.json",
    )
    json_str = audit_log.export_json()
    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(json_str)
    print(info_msg(f"\nFull audit log saved to: {output_path}"))

    # Exit code
    sys.exit(0 if failed_count == 0 else 1)


if __name__ == "__main__":
    main()
