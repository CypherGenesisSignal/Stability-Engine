# Stability Engine

Multi-agent runtime constraint framework for structural integrity, invariant enforcement, and controlled execution.

## Project Status

Stability Engine is a deterministic runtime-constraint architecture for multi-agent AI systems. It governs the environment agents operate within rather than tuning agent behavior. Its core concern is preserving structural continuity across identity, capability, memory, geometry, and execution.

The current public implementation line is:

- **v4.0** - contract-defined architecture and runnable demo baseline
- **v4.1** - hostile-audited structural baseline with critical runtime-path remediation
- **v4.2** - released Integrity Unit holonomic drift correction prototype
- **v5.0** - planned future consolidation release

The repository contains historical Sentinel Vector code and the standalone v4.2 Integrity Unit holonomic drift correction prototype. The v4.1 implementation scaffold is distributed separately and is absent from this checkout.

The project is not integration-ready, production-ready, adversarially hardened, cryptographically enforced, or hardware-isolated.

See [VERSION_HISTORY.md](VERSION_HISTORY.md) for the release lineage.

## Approved v4.2 contract

Joe Kasper approved the consolidated structural contract, including Clauses 15.1 through 15.6, on 15 September 2026.

- [Final consolidated structural contract](Docs/contracts/Stability_Engine_v4_2_Consolidated_Structural_Contract.md)
- [Conformance and implementation work](Docs/CONFORMANCE_v4_2.md)
- [Requirement register](Docs/contracts/requirements_v4_2.csv)

The contract preserves transaction-scoped Human Prime authority, separates audit evidence from agent recall, and keeps numerical convergence separate from execution permission. Approval of the contract does not certify runtime conformance. Clause 15.4 requires explicit numerical acceptance and failure-handling choices before integration; it does not select those choices.

This checkout contains the v4.2 correction pair and historical Sentinel Vector code. The v4.1 scaffold referenced below is a separate release artifact and is not present in this repository tree. Its test results and runtime features must not be attributed to the legacy modules in this checkout.

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

The separately packaged v4.1 implementation scaffold includes:

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

The following scaffold findings describe the v4.1 release artifact. The standalone v4.2 correction prototype is the current release implementation included in this checkout.

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

- Human Prime verification remains symbolic
- geometry, persistent memory, and Presence Engine backends remain mocked
- Python-level immutability is not hard runtime immutability
- some Phase 2 memory enforcement retains fallback behavior
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

## Separate v4.1 demo artifact

The v4.1 scaffold is not included in this checkout. After extracting its release archive, run these commands from the outer `sentinel_vector_demo` directory, preserving that directory name:

```bash
python -m simulation.run_demo
python -m unittest discover -s tests -v
```

The 14 September 2026 review of that separate artifact passed 35 unit tests. The demo passed 5 of 6 scenarios: Scenario 5 attempts a Tier 1 write while still in cooldown, and the guard blocks it. These are historical artifact results, not a claim that this repository contains or passes that suite. Demo sequencing remains to be corrected without weakening the guard.

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
