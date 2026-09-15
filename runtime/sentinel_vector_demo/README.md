# Stability Engine runtime scaffold

This working copy derives from the outer `sentinel_vector_demo` in Joe Kasper's uploaded v4.1 demo archive, confirmed as the latest runtime on 15 September 2026. It applies a bounded set of approved v4.2 contract requirements. It is a cooperative Python prototype, not a production containment boundary.

From this directory, with Python 3.11 or newer:

```bash
python -m unittest discover -s tests -v
python -m simulation.run_demo
```

The scaffold uses the standard library. Keep the directory name `sentinel_vector_demo`: inherited mocks import through that package name. The demo writes an operator audit export to `simulation/demo_audit_log.json`. Generated logs and bytecode are not source artifacts.

## Implemented changes

- Memory requests declare their operation and data direction explicitly. Missing or invalid tier fields are refused, with no guessed direction or fallback to Tier 0.
- Raw T0/T2 exchange is refused both ways. Upward writes are refused. All T2 requests remain disabled because the supplied runtime has no authenticated, transaction-scoped authority provider or sanitized T2 metadata integration. A signature-shaped string cannot open that gate.
- The orchestrator cannot dispatch memory, audit, geometry, or unknown adapter methods through its generic adapter path. Geometry uses the Interposer handoff; only the existing presence-summary call remains on the generic path. Missing gates and unsuccessful geometry assessments fail closed.
- Geometry adapter binding is fixed for an Interposer instance. Sanitization strips known restricted keys recursively through dictionaries and sequences.
- Audit entries and local memory values are copied at ingress and egress. Callers cannot mutate retained evidence or frozen Tier 1 data through returned nested references.
- Operational evidence is recorded in the existing in-process AuditLog rather than automatically appended to agent memory. Request responses no longer include cross-request execution history; the legacy `execution_trace_snapshot` response field is empty. Operator inspection remains separate.
- The recovery demo uses a fresh fixture. It never resets the operational mode of the previously cooled-down runtime. Symbolic T2 tokens are demonstrated as refusals.

## Memory request schema

Define direction from the data, not from which component initiated a read:

| Field | Meaning |
| --- | --- |
| `agent_id` | Required nonempty requester label, supplied by the trusted caller |
| `requesting_agent_id` | Optional consistency check; must equal `agent_id` when supplied |
| `memory_access` | Exactly `read` or `write` |
| `source_tier` | Data origin, integer 0, 1, or 2, or the canonical `MemoryTier` enum |
| `target_tier` | Data recipient/destination, with the same valid values |
| `action` | Descriptive label; never an authorization source or direction inference |

These labels are not authenticated identities. Same-process Python callers are still trusted. Local T0/T1 operations remain available through the scaffold API. Direct mock storage accepts only explicit tiers, filters recall by actor, and refuses T2 regardless of token content. Direct mock APIs are test fixtures, not production agent interfaces.

## Open integration work

Authorized T2 transactions need an agreed authority verifier, payload/scope binding, expiration and replay control, Interposer-mediated execution, and sanitized metadata schema. This patch removes false authorization; it does not implement that positive authorization path.

No new durable evidence store, retention lifetime, or audit access authority is introduced. Those choices require explicit authorization under Clause 15.3. Existing operator inspection methods must not be exposed as agent tools.

Collaborator configuration activation and backend state transitions remain open under 15.2. Numerical acceptance, domain timing, exception normalization, callback budgets, and final-step acceptance remain open under 15.4. The standalone v4.2 solver is not wired into execution and its published files are unchanged.

The inherited modules still contain broader architectural aspirations. Python reflection, internal attributes, caller identity spoofing, full Control Plane state ownership, dynamic envelope narrowing, complete sanitization schemas, and authenticated configuration are not hardened by this patch. Passing these tests establishes specific API behavior, not full contract conformance.

See [conformance evidence](../../Docs/CONFORMANCE_v4_2.md) and [source provenance](../SOURCE_PROVENANCE.json).
