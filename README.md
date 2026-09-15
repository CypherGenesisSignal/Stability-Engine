# Stability Engine

Multi-agent runtime constraint framework for structural integrity, invariant enforcement, and controlled execution.

## Project Status

Stability Engine is a deterministic runtime-constraint architecture for multi-agent AI systems. It governs the environment agents operate within rather than tuning agent behavior. Its core concern is preserving structural continuity across identity, capability, memory, geometry, and execution.

The current public implementation line is:

- **v4.0** - contract-defined architecture and runnable demo baseline
- **v4.1** - hostile-audited structural baseline with critical runtime-path remediation
- **v4.2** - released Integrity Unit holonomic drift correction prototype
- **v5.0** - planned future consolidation release

The repository contains historical Sentinel Vector code, the standalone v4.2 Integrity Unit correction prototype, and a working copy of the latest v4.1 runtime scaffold with bounded v4.2 contract enforcement changes under `runtime/sentinel_vector_demo`.

The project is not integration-ready, production-ready, adversarially hardened, cryptographically enforced, or hardware-isolated.

See [VERSION_HISTORY.md](VERSION_HISTORY.md) for the release lineage.

## Approved v4.2 contract

Joe Kasper approved the consolidated structural contract, including Clauses 15.1 through 15.6, on 15 September 2026.

- [Final consolidated structural contract](Docs/contracts/Stability_Engine_v4_2_Consolidated_Structural_Contract.md)
- [Conformance and implementation work](Docs/CONFORMANCE_v4_2.md)
- [Requirement register](Docs/contracts/requirements_v4_2.csv)

The contract preserves transaction-scoped Human Prime authority, separates audit evidence from agent recall, and keeps numerical convergence separate from execution permission. Approval of the contract does not certify runtime conformance. Clause 15.4 requires explicit numerical acceptance and failure-handling choices before integration; it does not select those choices.

Joe confirmed the uploaded v4.1 scaffold as the latest runtime. Its working copy and source provenance are now included under `runtime/`. The historical release files remain unchanged. See the conformance document for implemented changes and open integration work.

## Architecture

Stability Engine defines four primary runtime layers:

- **Geometry Co-Processor**  
  Structural coherence, topology, deterministic constraint evaluation, and safe manifold resolution.

- **Invariant Interposer**  
  Non-bypassable enforcement boundary for identity, memory tiers, capability envelopes, and geometry access.

- **Control Plane**  
  Deterministic task routing, cooldown handling, recovery coordination, and orchestration under Interposer authority.

- **Stability Metrics**  
  Drift, torsion, continuity, synergy, and boundary-pressure evaluation.

Three operational units are specified within the architecture:

- **AdSim Unit** - applies controlled adversarial pressure
- **Defense Unit** - enforces safe recovery and containment
- **Integrity Unit** - validates invariant health, continuity authenticity, and structural correctness

The v4.2 release begins moving the Integrity Unit from specification into runnable prototype code without claiming completion of the full unit.

## Supporting Runtime Layers

The imported v4.1 implementation scaffold includes:

- **TSRL-1** for continuous observation and evidence generation
- **TSRL-2** for deterministic routing and attribution preservation
- **TSRL-3** for recursive stability evaluation
- **QAMS** for attributed signal transport
- **Purple Orchestrator** for deterministic multi-component coordination
- mock-backed adapters for collaborator-pending components
- audit logging and runtime tests

## Stability Engine v4.2: Integrity Unit Holonomic Drift Correction Prototype

Stability Engine v4.2 was released on August 1, 2026. It is the first demonstrable Integrity Unit correction implementation increment and adds:

- residual drift evaluation
- metric-aware bounded correction
- domain admissibility checks
- Jacobian and metric validation
- structured convergence and failure outcomes
- deterministic correction limits

The canonical implementation files are:

- [`integrity_unit_v4_2.py`](releases/v4.2/integrity_unit_v4_2.py)
- [`test_integrity_unit_v4_2.py`](releases/v4.2/test_integrity_unit_v4_2.py)

Verified release test result:

- 7 tests collected
- 7 tests passed
- Python 3.14.6
- pytest 9.1.1

The architectural boundary is:

Integrity Unit owns the interface.  
URIEL owns the internal holonomy.  
Adapter mediates.  
Nothing crosses raw.

The published release is available at [Zenodo DOI 10.5281/zenodo.21752941](https://doi.org/10.5281/zenodo.21752941).

See the [v4.2 release documentation](releases/v4.2/SEv4.2_01_README.md) for the complete bounded scope, maturity posture, adapter boundary, manifest, and validation evidence.

## Current Maturity

The findings below describe the inherited release scope. The working runtime now rejects symbolic Tier 2 authorization, requires explicit memory direction, fixes geometry binding per instance, and separates operational evidence from agent memory. See [runtime notes](runtime/sentinel_vector_demo/README.md) for precise behavior and remaining gaps.

### Reported release implementation scope

- TSRL observation-routing-stability chain
- QAMS attributed transport
- Purple Orchestrator execution pipeline
- Interposer-gated geometry access
- live sanitization before geometry evaluation
- automatic Tier 0 wiping
- cross-agent isolation at the Control Plane API level
- continuity and synergy diagnostics
- deterministic refusals
- drift detection with partial graduated enforcement
- bounded Integrity Unit holonomic drift correction prototype

### Still soft, mocked, or incomplete

- Authenticated Human Prime verification is not implemented; T2 access now fails closed
- geometry, persistent memory, and Presence Engine backends remain mocked
- Python-level immutability is not hard runtime immutability
- positive T2 transactions and sanitized T2 metadata integration remain unavailable
- memory bleed detection assumes cooperative API usage
- Control Plane statelessness remains unresolved
- full dynamic envelope narrowing remains incomplete

### Specified but not fully implemented

- AdSim Unit
- Defense Unit
- full Integrity Unit
- Tri-Unit Coordination Protocol
- optimization-shortcut rejection
- full geometry drift recovery
- six-layer stack representation in code
- URIEL-3b adapter and integration
- spectral admissibility
- defect descent
- finite-state collapse enforcement

## Running the v4.2 prototype tests

Use a Python environment with NumPy and pytest installed. From the repository root:

```bash
python -m pytest releases/v4.2/test_integrity_unit_v4_2.py -v
```

The published seven-case suite tests the standalone correction prototype. It is not an integrated containment test suite. Some invalid inputs raise exceptions; domain admissibility is checked at convergence. The full behavior and remaining acceptance-policy obligations are recorded in Sections 11, 14, and 15 of the approved contract.

## Running the working runtime

From `runtime/sentinel_vector_demo`, using Python 3.11 or newer:

```bash
python -m unittest discover -s tests -v
python -m simulation.run_demo
```

The modified scaffold passes 51 tests and all 6 demo scenarios on Python 3.12.14. It uses the standard library. Keep its directory name intact for inherited package imports. These tests establish bounded API behavior, not full containment. The separate v4.2 solver has not been integrated into execution.

Tier 2 access is disabled until authenticated, scoped authorization and the required metadata integration are implemented. Geometry collaborator activation, durable audit policy, and numerical acceptance choices remain open under Section 15.

## Release Discipline

Stability Engine releases are scoped by what the artifact actually earns.

- **v4.1** remains the hostile-audited structural baseline after remediation of critical live runtime paths.
- **v4.2** is the published, narrow Integrity Unit holonomic drift correction prototype increment. It does not claim completed Integrity Unit or URIEL-3b integration.
- **v5.0** remains reserved for future repository normalization, broader operational-unit implementation, collaborator interface consolidation, expanded runtime integration, and renewed hostile audit.

## What This Project Is Not

Stability Engine is not:

- an alignment model
- a semantic evaluator
- a behavioral optimizer
- an engagement-tuning system
- a self-modifying governance layer
- a production-ready security product

Its governance is structural.

## License

MIT License. See `LICENSE` for full terms.

## Acknowledgments

Special thanks to early collaborators, reviewers, and researchers helping shape the architecture, challenge its boundaries, and test its claims.

The Stability Engine is an open project and encourages external review, analysis, and contribution.
