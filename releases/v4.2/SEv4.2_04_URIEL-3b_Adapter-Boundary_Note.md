# URIEL-3b Adapter-Boundary Note

## Purpose

This note defines the architectural boundary between the Stability Engine v4.2 Integrity Unit prototype and URIEL-3b.

Its purpose is to preserve separation of authority, prevent direct coupling to collaborator-owned internal operators, and establish the conditions required for future integration.

Boundary Statement

Integrity Unit owns the interface.
URIEL owns the internal holonomy.
Adapter mediates.
Nothing crosses raw.

This boundary is mandatory.

The Stability Engine may interact with URIEL-3b only through a defined adapter surface. The Integrity Unit must not directly invoke, expose, mutate, or depend on URIEL-3b internal operators.

Integrity Unit Responsibility

The Integrity Unit owns the Stability Engine-facing side of the integration.

Its responsibilities include:

receiving bounded state and correction inputs
evaluating residual drift
applying or requesting bounded correction
validating admissibility conditions exposed through the adapter
returning structured correction outcomes
preserving deterministic failure behavior
maintaining Stability Engine contract boundaries
preventing raw collaborator internals from entering the runtime surface

The Integrity Unit does not own URIEL-3b geometry, operator definitions, spectral internals, or holonomy state.

URIEL-3b Responsibility

URIEL-3b owns its internal holonomic and geometric behavior.

Its internal responsibility may include:

state-dependent holonomy
non-commutative operators
spectral layers
admissibility layers
defect-descent behavior
spectral residue behavior
finite-state collapse behavior

These surfaces remain internal to URIEL-3b.

They are not part of the public Stability Engine interface and must not be exposed raw to the Integrity Unit, Control Plane, Interposer, or other runtime components.

Adapter Responsibility

The adapter mediates all exchange between the Integrity Unit and URIEL-3b.

Its responsibilities include:

translating Stability Engine requests into URIEL-compatible inputs
translating URIEL outputs into Stability Engine-compatible results
preserving attribution
preserving dimensional and domain constraints
enforcing schema validation
preventing raw operator exposure
rejecting malformed or inadmissible exchange
maintaining deterministic result formatting
isolating collaborator-owned implementation details
ensuring that neither side silently inherits authority from the other

The adapter is a translation and containment boundary.

It is not an authority layer, optimization layer, or policy engine.

Prohibited Direct Access

The following are prohibited:

direct Integrity Unit calls to URIEL-3b internal operators
direct Control Plane calls to URIEL-3b
direct Interposer mutation of URIEL-3b internals
raw geometry state transfer
raw holonomy state transfer
exposure of non-commutative operator internals
runtime mutation of URIEL-3b geometric behavior
bypass of adapter validation
implicit widening of either system’s authority
shared mutable state across the boundary

No alternate path is permitted.

Reason for the Boundary

URIEL-3b internal operators are described as:

state-internal
holonomy-dependent
non-commutative
coupled to admissibility
coupled to spectral residue coherence
coupled to finite-state collapse guarantees

Direct exposure would risk breaking:

admissibility guarantees
drift-correction invariants
spectral residue coherence
finite-state collapse guarantees
separation between interface behavior and internal geometry
deterministic failure handling
collaborator ownership boundaries

The adapter exists to preserve these constraints.

v4.2 Status

In v4.2:

the Integrity Unit correction prototype exists
the adapter boundary is architecturally defined
the URIEL-3b integration direction is identified
the canonical prototype is runnable and tested
the adapter itself is not implemented
end-to-end URIEL-3b integration is not implemented
spectral admissibility is not implemented
defect descent is not implemented
spectral residue evaluation is not implemented
finite-state collapse enforcement is not implemented

v4.2 establishes the correction-side interface and the mandatory integration boundary.

It does not claim completed integration.

Expected Future Exchange Surface

A future adapter may expose bounded request and result structures such as:

Request Surface
state vector
residual vector
state metric
residual metric
tolerance
correction limit
iteration limit
domain constraints
trace identifier
invariant context
Result Surface
convergence status
corrected state
residual norm
iteration count
admissibility status
structured failure code
trace identifier
bounded diagnostic metadata

These fields are conceptual integration targets only.

The final schema is not defined in v4.2.

Authority Preservation

The adapter must preserve the existing Stability Engine hierarchy.

The Integrity Unit owns the interface.
The Interposer retains enforcement authority over Stability Engine-bound operations.
The Control Plane retains coordination responsibility only.
URIEL-3b retains ownership of its internal holonomy.
The adapter mediates without becoming an independent authority.
No component may widen its own capability through the integration.

The boundary must remain deterministic, inspectable, and non-bypassable.

Failure Behavior

If the adapter receives malformed, ambiguous, non-finite, dimensionally invalid, or inadmissible input, it must fail closed.

Expected failure behavior includes:

reject the request
return a structured failure code
preserve traceability
prevent raw state transfer
prevent partial execution
prevent fallback to direct operator access
preserve the last known admissible state
escalate through the Stability Engine-defined path where applicable

The adapter must never guess, improvise, or silently coerce invalid input.

Final Boundary Position

The Stability Engine v4.2 integration rule is:

Integrity Unit owns the interface.
URIEL owns the internal holonomy.
Adapter mediates.
Nothing crosses raw.

This boundary is the required foundation for any future URIEL-3b integration.