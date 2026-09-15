# Stability Engine v4.2 conformance and implementation work

Joe Kasper approved the [consolidated structural contract](contracts/Stability_Engine_v4_2_Consolidated_Structural_Contract.md), including Clauses 15.1 through 15.6. On 15 September 2026 he confirmed that the uploaded v4.1 scaffold is the latest runtime. Approval establishes requirements, not runtime certification.

## Source and working location

The original repository baseline is `d258766c1d81d8b95fea3f9953a51d9dc445c8e9`. It contains historical Sentinel Vector code and the standalone pair under `releases/v4.2/`, but no v4.1 scaffold or test suite. This PR adds the confirmed outer v4.1 scaffold as a working copy under [runtime/sentinel_vector_demo](../runtime/sentinel_vector_demo/README.md). This is an additive import, not a v5 repository reorganization.

[Source provenance](../runtime/SOURCE_PROVENANCE.json) records the uploaded archive hash and original/working hashes for every imported source file. The nested duplicate, generated evidence files, and bytecode are excluded. The published v4.2 correction pair is unchanged.

The Markdown contract transcribes the approved final document, including its historical evidence and date line. Its September 14 test results describe the supplied archives. The results below describe the modified working runtime and do not rewrite that history.

## Approved clause disposition

| Clause | Implemented in this working copy | Still open |
| --- | --- | --- |
| 15.1 | Explicit requester/data-source/data-destination schema; both raw T0/T2 directions refused; upward writes refused; symbolic T2 tokens rejected; missing/invalid tiers refused. Local store and recall snapshots prevent nested-reference mutation; mock recall filters actors. | Positive T2 authorization, authenticated requester identity, scoped execution, expiration/replay control, and sanitized T2-to-T1 metadata integration. T2 is disabled until these exist. |
| 15.2 | Geometry adapter can be bound once; ordinary rebinding and unsealing assignments fail. Nested restricted keys are sanitized. Missing or unsuccessful geometry gates cannot return execution success. | Collaborator agreement on configuration activation and backend transitions; full payload allowlist; hostile same-process protection. No collaborator integration added. |
| 15.3 | Existing in-process AuditLog takes and returns detached snapshots. Orchestrator records its events there, stops automatically copying evidence into agent memory, and stops returning cross-request execution history. Generic adapter dispatch rejects memory/audit exports. | Authorized durable record schema, retention authority/lifetime, access control, and storage placement. No new persistence layer or authority is introduced. Operator objects remain trusted Python interfaces. |
| 15.4 | Solver remains standalone, with no new execution/commit path. | Numerical acceptance alternatives, domain timing, exception normalization, callback limits, final-iteration acceptance. None selected implicitly. |
| 15.5 | Contract preserves distinct historical maps, naming, and R = 4 provenance. Import provenance identifies the scaffold. | No universal mathematical guarantee or repository-wide renaming claimed. |
| 15.6 | Requirement register links affected clauses to partial implementation/test evidence and leaves unresolved requirements open. | Full conformance review, authenticated enforcement, hostile audit, production hardening. |

## Test evidence

Run from `runtime/sentinel_vector_demo`:

```bash
python -m unittest discover -s tests -v
python -m simulation.run_demo
```

On 15 September 2026, Python 3.12.14 ran **51 scaffold tests successfully**, including 16 new contract regression tests. The 35 inherited tests were retained, with explicit memory schemas added to fixtures and two old symbolic-T2-success expectations changed to refusals. Those expectation changes follow the contract's requirement that a claim of approval is not approval.

The six-scenario demo now passes **6/6**. Its recovery scenario creates a fresh fixture rather than resetting a cooled-down runtime; the Tier 1 cooldown guard remains enforced. Its T2 token example now expects refusal.

From the repository root:

```bash
python -m pytest releases/v4.2/test_integrity_unit_v4_2.py -v
```

The unchanged v4.2 suite passes **7/7** with NumPy 2.3.5 and pytest 9.1.1. This is a separate standalone solver suite, not a 58-test integrated containment certification.

## Regression mapping

All tests below are in `runtime/sentinel_vector_demo/tests/test_contract_v4_2.py`.

| Boundary | Test methods |
| --- | --- |
| Explicit memory schema and directional refusal | `test_missing_invalid_or_conflicting_schema_refused`, `test_raw_t0_t2_both_directions_and_operations`, `test_upward_write_denied_despite_benign_action`, `test_local_explicit_read_and_write_remain_allowed` |
| No symbolic authority | `test_symbolic_authority_cannot_grant_or_be_reused`, `test_mock_symbolic_token_never_creates_t2_data` |
| Fixed geometry binding and sanitization | `test_geometry_cannot_be_rebound_or_unsealed_via_normal_assignment`, `test_nested_geometry_sanitization_does_not_mutate_input` |
| Missing gates and geometry failure | `test_adapter_gate_denies_memory_audit_unknown_and_missing_gate`, `test_geometry_refusal_and_malformed_result_cannot_be_success`, `test_missing_geometry_gate_cannot_be_success` |
| Evidence separation and reference safety | `test_audit_snapshots_survive_caller_mutation_and_tier_cleanup`, `test_runtime_evidence_not_written_to_agent_memory_or_returned_as_history`, `test_tier_freeze_cannot_be_bypassed_through_nested_aliases` |
| Mock memory isolation and validation | `test_mock_recall_isolated_and_detached`, `test_mock_rejects_invalid_tier_instead_of_defaulting` |

## Requirement register and limits

[requirements_v4_2.csv](contracts/requirements_v4_2.csv) records all 83 contract paragraphs containing uppercase MUST, including MUST NOT. A paragraph may contain multiple obligations. OPEN means no complete conformance determination; PARTIAL means specific related API behavior has evidence while broader obligations remain unresolved. Neither status certifies the paragraph.

The current runtime remains cooperative Python code. Attribute reflection, direct internal access, trusted caller labels, Control Plane state ownership, complete agent-tool isolation, dynamic envelope narrowing, and collaborator backends are unresolved. The tests do not establish authenticated Human Prime authority, replay-safe transactions, a production audit store, or non-bypassable process isolation.
