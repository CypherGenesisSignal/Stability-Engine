# Stability Engine

Multi-agent runtime constraint framework for structural integrity, invariant enforcement, and controlled execution.

## Project Status

Stability Engine is a deterministic runtime-constraint architecture for multi-agent AI systems. It governs the environment agents operate within rather than tuning agent behavior. Its core concern is preserving structural continuity across identity, capability, memory, geometry, and execution.

The current public implementation line is:

- **v4.0** — contract-defined architecture and runnable demo baseline
- **v4.1** — hostile-audited implementation scaffold with critical runtime-path remediation
- **v4.2** — focused Integrity Unit holonomic drift-correction increment in progress
- **v5.0** — planned larger consolidation release

The current repository posture is best described as:

**Structurally consistent implementation scaffold with cooperative enforcement boundaries.**

This is more than a proof of concept, but it is not production-ready, adversarially hardened, cryptographically enforced, or hardware-isolated.

See [VERSION_HISTORY.md](VERSION_HISTORY.md) for the release lineage.

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

- **AdSim Unit** — applies controlled adversarial pressure
- **Defense Unit** — enforces safe recovery and containment
- **Integrity Unit** — validates invariant health, continuity authenticity, and structural correctness

The v4.2 line begins moving the Integrity Unit from specification into runnable prototype code.

## Supporting Runtime Layers

The current implementation scaffold also includes:

- **TSRL-1** for continuous observation and evidence generation
- **TSRL-2** for deterministic routing and attribution preservation
- **TSRL-3** for recursive stability evaluation
- **QAMS** for attributed signal transport
- **Purple Orchestrator** for deterministic multi-component coordination
- mock-backed adapters for collaborator-pending components
- audit logging and runtime tests

## Current Maturity

### Implemented and runtime-path validated

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
- expanded runtime test coverage

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
- geometry drift recovery
- six-layer stack representation in code

## Running the Demo

Requirements:

- Python 3.11 or newer

From the implementation scaffold root:

```bash
python -m simulation.run_demo
```

Run the tests:

```bash
python -m unittest discover tests -v
```

## Release Discipline

Stability Engine releases are scoped by what the artifact actually earns.

- **v4.1** established structural consistency in the live runtime path after hostile audit and remediation.
- **v4.2** is intended as a narrow implementation increment centered on the Integrity Unit holonomic drift-correction surface and sealed adapter mediation around collaborator-owned geometry operators.
- **v5.0** is reserved for a larger convergence release involving repository normalization, broader operational-unit implementation, collaborator interface consolidation, and renewed hostile audit.

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