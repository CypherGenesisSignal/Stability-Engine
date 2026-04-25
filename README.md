# The Stability Engine

Multi-agent runtime constraint framework for structural integrity, invariant enforcement, and controlled execution.

## Introduction

Stability Engine is a deterministic runtime-constraint framework designed to enforce structural integrity, invariant boundaries, and controlled agent behavior within multi-agent AI systems. The engine provides a governed execution envelope using geometry-aligned gating, invariant interposition, refusal logic, and stability metrics.

Version 4.0 introduces a hardened Control Plane, one-way invariant enforcement, and a complete operational demo that showcases runtime behavior under adversarial and boundary-pressure scenarios.

Stability Engine is the evolutionary successor to the early Sentinel Vector architecture and formalizes a physics-style constraint layer for autonomous agent environments. The engine defines four core runtime modules:

- Geometry Co-Processor
- Invariant Interposer
- Control Plane
- Stability Metrics

These modules operate in a deterministic chain with explicit refusal paths, clamp behavior, and invariant enforcement. Included with this release is a fully runnable Python demo demonstrating event generation, boundary violations, cooldown sequencing, and logged evidence of runtime decisions.

This project focuses on correctness, determinism, and reproducibility. It is not an alignment layer, a semantic evaluator, or a behavioral optimizer. All governance is structural.

## Architecture Overview

The Stability Engine demo is organized around four primary runtime modules:

- **Geometry Co-Processor**  
  Structural coherence, curvature logic, and deterministic constraint evaluation

- **Invariant Interposer**  
  One-way enforcement boundary for identity, memory, capability, and geometry protection

- **Control Plane**  
  Authorized task routing, cooldown handling, and recovery coordination

- **Stability Metrics**  
  Drift, torsion, and boundary-pressure evaluation

Supporting runtime layers in this demo include:

- **TSRL-1** for observation
- **TSRL-2** for routing and attribution
- **TSRL-3** for recursive stability
- **Purple Orchestrator** for cross-component coordination during demo execution

This release includes runnable mock adapters for collaborator-pending components, a simulation entrypoint, audit logging, and tests covering refusals, memory boundaries, traceability, and runtime enforcement.

## Folder Structure

```
sentinel_vector_demo/
├── README.md
├── adapters/
│   ├── __init__.py
│   ├── geometry_coprocessor.py
│   ├── persistent_memory.py
│   └── presence_engine.py
├── core/
│   ├── __init__.py
│   ├── audit_log.py
│   ├── control_plane.py
│   ├── interposer.py
│   ├── qams.py
│   ├── stability_metrics.py
│   └── types.py
├── mocks/
│   ├── __init__.py
│   ├── mock_geometry_coprocessor.py
│   ├── mock_persistent_memory.py
│   └── mock_presence_engine.py
├── orchestration/
│   ├── __init__.py
│   └── purple_orchestrator.py
├── simulation/
│   ├── __init__.py
│   ├── demo_audit_log.json
│   └── run_demo.py
├── tests/
│   ├── __init__.py
│   ├── test_memory_boundaries.py
│   ├── test_qams_traceability.py
│   ├── test_refusals.py
│   └── test_runtime_enforcement.py
└── tsrl/
    ├── __init__.py
    ├── tsrl1_observation.py
    ├── tsrl2_routing.py
    └── tsrl3_stability.py
```
This repository is structured around the major runtime boundaries of the Stability Engine demo.

adapters/ contains integration interfaces for the Geometry Co-Processor, persistent memory, and Presence Engine layers
core/ contains the primary enforcement substrate, including the Control Plane, Invariant Interposer, QAMS, audit logging, shared types, and stability metrics
mocks/ provides deterministic stand-ins for collaborator-pending or external components so the demo remains runnable in isolation
orchestration/ contains the Purple Orchestrator that coordinates multi-component execution
simulation/ contains the demo runner and sample audit output
tests/ validates runtime enforcement, refusal behavior, memory boundary protection, and traceability guarantees
tsrl/ contains the three TSRL layers: observation, routing, and recursive stability
Getting Started
Requirements
Python 3.11 or newer
Run the demo

From the project root:
```
python -m simulation.run_demo
```
Run the tests

From the project root:
```
python -m unittest discover tests -v
```

Roadmap
v0.4
First functional runtime loop
Working memory boundaries
Initial holonomic stability scoring
v0.5
Multi-component runs with replay logs
Initial refusal and containment flows
Early adversarial simulation coverage
v0.6
Expanded telemetry and drift mapping
Dynamic Control Plane routing behavior
Improved audit visibility and traceability
v1.0
Full runtime constraint demonstration
Persistent memory stabilization
Exportable reports and evidence artifacts
License

MIT License.
See LICENSE for full terms.

Acknowledgments

Special thanks to early collaborators, reviewers, and researchers helping shape the architecture.

The Stability Engine is an open project and encourages external review, analysis, and contribution.
