# Stability Engine v4.2 conformance and implementation work

Joe Kasper approved the [consolidated structural contract](contracts/Stability_Engine_v4_2_Consolidated_Structural_Contract.md), including Clauses 15.1 through 15.6, on 15 September 2026. Approval establishes the requirements. Runtime conformance remains an engineering and verification obligation.

## Repository baseline

This assessment uses `main` at `d258766c1d81d8b95fea3f9953a51d9dc445c8e9`. The tree contains historical Sentinel Vector modules and the canonical correction pair under `releases/v4.2/`. It does not contain the v4.1 `sentinel_vector_demo` scaffold, its Interposer or Control Plane implementation, or its 35-test suite. No `AGENTS.md` or CI workflow is present in that baseline tree.

The contract records a separate review of uploaded v4.1 and v4.2 release artifacts. Its 35-test scaffold result must not be represented as a result from this checkout. Its Appendix B scaffold commands require that separately extracted artifact.

The Markdown contract transcribes the approved final document. Its approval record, source fingerprints, maturity qualifications, and historical test dates are retained. The Pages copy uses the date line Joe Kasper | 15 September 2026, which is preserved here.

## Approved clause disposition

| Clause | Approved rule or obligation | Implementation status and next evidence |
| --- | --- | --- |
| 15.1 | Deny autonomous upward promotion; permit only separately authorized, Interposer-mediated Tier 2 transactions. Block raw T0/T2 exchange both ways. | OPEN MEMORY: establish the working scaffold and explicit requester/source/destination schema. Test transaction scope, replay or reuse, cross-agent access, both raw-read directions, and allowed sanitized reads. Approval alone is not a signature verifier. |
| 15.2 | Separate fixed geometry rules, private collaborator computation, and committed state. | OPEN GEOMETRY: agree configuration activation and allowed backend transitions with the collaborator. Demonstrate that correction and recovery cannot mutate rules or bypass the Interposer. |
| 15.3 | Preserve audit evidence without creating an agent recall channel or a fourth memory tier. | OPEN AUDIT: authorize record schema, retention authority, access policy, lifetime, and storage placement. Test evidence retention across resets and denial of unauthorized agent recall. |
| 15.4 | Specify numerical acceptance, domain-check timing, exception normalization, callback limits, and final-iteration acceptance before integration. | OPEN NUMERICS: the alternatives remain to be selected explicitly. The released prototype is preserved. Do not silently choose a singular-metric policy, endpoint-only policy, timeout, or budget rule. |
| 15.5 | Keep historical layer maps distinct; preserve naming and R = 4 provenance without an unproved universal guarantee. | DOCUMENTED: contract Section 10 preserves both maps and their boundaries. Historical releases remain intact. No repository-wide renaming or v5 reorganization is included. |
| 15.6 | Trace requirements and require evidence before conformance or hardening claims. | REGISTERED, NOT CERTIFIED: the requirement register links each normative paragraph to its clause and an open conformance record. Runtime evidence must be attached before any record is closed. |

## Requirement register

[requirements_v4_2.csv](contracts/requirements_v4_2.csv) records every contract paragraph containing uppercase MUST, including MUST NOT. A record retains the full paragraph, which can contain multiple obligations. Clause numbers remain the authoritative identifiers; REQ numbers are register keys only.

OPEN means the paragraph has not received a complete conformance determination. It does not mean every behavior in it is absent. An existing test may support part of a paragraph without demonstrating its full authority boundary. Each record must eventually link to implementation and meaningful tests or a tracked open issue. The open work groups above provide the initial disposition; they are not GitHub issue numbers.

## Validation performed for this repository update

The repository copy of the canonical v4.2 suite passed 7 tests on 15 September 2026 with Python 3.12.14, NumPy 2.3.5, and pytest 9.1.1. The command was run from the repository root:

```bash
python -m pytest releases/v4.2/test_integrity_unit_v4_2.py -v
```

This validates the existing prototype cases only. No runtime code changes accompany this contract import. The v4.1 scaffold tests were not rerun as repository tests because their source tree is absent. Its previously observed demo sequencing failure remains open.

## Runtime implementation dependency

The next runtime change requires an agreed working location for the v4.1 scaffold or confirmation of a newer implementation branch. Once that source is established, apply the settled contract requirements there and verify the enforcement paths. Preserve the published v4.2 correction pair as release provenance. Resolve the numerical choices in 15.4 and collaborator details in 15.2 before integrating correction into execution.

The historical agent and export modules in this repository must not be relabeled as an implementation of the approved Interposer, memory-tier, or audit contracts without tracing and testing their actual behavior.
