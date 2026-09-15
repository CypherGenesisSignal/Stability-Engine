"""
Stability Engine v4.0 — Shared Types, Enums, and Data Structures

All modules import from here to maintain a single source of truth
for message formats, tier identifiers, refusal codes, and routing enums.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Memory Tiers  (MTS 4)
# ---------------------------------------------------------------------------
class MemoryTier(Enum):
    """Three hard memory tiers — no soft tiers, no in-between."""
    TIER_0 = 0   # Ephemeral: local to a single operation cycle
    TIER_1 = 1   # Session: persists only for active session
    TIER_2 = 2   # Long-Term Store: human-prime gated, immutable w/o signature


# ---------------------------------------------------------------------------
# System Operational Modes
# ---------------------------------------------------------------------------
class OperationalMode(Enum):
    NORMAL = auto()
    DEGRADED = auto()
    COOLDOWN = auto()
    RECOVERY = auto()
    LOCKDOWN = auto()


# ---------------------------------------------------------------------------
# Drift Severity Levels
# ---------------------------------------------------------------------------
class DriftSeverity(Enum):
    NONE = 0
    LOW = 1
    MODERATE = 2
    HIGH = 3
    CRITICAL = 4


# ---------------------------------------------------------------------------
# Refusal Reason Codes  (IC 4.9 — deterministic refusal surface)
# ---------------------------------------------------------------------------
class RefusalCode(Enum):
    IDENTITY_MODIFICATION = "REFUSAL_IDENTITY_MODIFICATION"
    IDENTITY_DRIFT = "REFUSAL_IDENTITY_DRIFT"
    MEMORY_TIER_VIOLATION = "REFUSAL_MEMORY_TIER_VIOLATION"
    MEMORY_CROSS_TIER_WRITE = "REFUSAL_CROSS_TIER_WRITE"
    MEMORY_UNAUTHORIZED_T2_WRITE = "REFUSAL_UNAUTHORIZED_T2_WRITE"
    MEMORY_EMERGENT = "REFUSAL_EMERGENT_MEMORY"
    GEOMETRY_MUTATION = "REFUSAL_GEOMETRY_MUTATION"
    GEOMETRY_UNSANITIZED_INPUT = "REFUSAL_GEOMETRY_UNSANITIZED"
    CAPABILITY_ESCALATION = "REFUSAL_CAPABILITY_ESCALATION"
    ENVELOPE_EXCEEDED = "REFUSAL_ENVELOPE_EXCEEDED"
    INVARIANT_VIOLATION = "REFUSAL_INVARIANT_VIOLATION"
    OPTIMIZATION_SHORTCUT = "REFUSAL_OPTIMIZATION_SHORTCUT"
    COOLDOWN_ACTIVE = "REFUSAL_COOLDOWN_ACTIVE"
    DRIFT_ESCALATION = "REFUSAL_DRIFT_ESCALATION"


# ---------------------------------------------------------------------------
# QAMS Message Types
# ---------------------------------------------------------------------------
class QAMSMessageType(Enum):
    REQUEST = "request"
    DRIFT_SIGNAL = "drift_signal"
    ENFORCEMENT_RESULT = "enforcement_result"
    ROUTING_METADATA = "routing_metadata"
    COOLDOWN_INSTRUCTION = "cooldown_instruction"
    GEOMETRY_HANDOFF = "geometry_handoff"
    REFUSAL = "refusal"
    RECOVERY = "recovery"
    ADAPTER_CALL = "adapter_call"
    ADAPTER_RESPONSE = "adapter_response"
    AUDIT = "audit"


# ---------------------------------------------------------------------------
# Component IDs
# ---------------------------------------------------------------------------
class ComponentID(Enum):
    CONTROL_PLANE = "control_plane"
    STABILITY_METRICS = "stability_metrics"
    INTERPOSER = "interposer"
    GEOMETRY = "geometry_coprocessor"
    PURPLE_ORCHESTRATOR = "purple_orchestrator"
    TSRL_1 = "tsrl_1_observation"
    TSRL_2 = "tsrl_2_routing"
    TSRL_3 = "tsrl_3_stability"
    PRESENCE_ENGINE = "presence_engine"
    PERSISTENT_MEMORY = "persistent_memory"
    AUDIT_LOG = "audit_log"
    HUMAN_PRIME = "human_prime"
    AGENT_RED = "agent_red"
    AGENT_BLUE = "agent_blue"
    AGENT_GREEN = "agent_green"
    DEMO_HARNESS = "demo_harness"


# ---------------------------------------------------------------------------
# TSRL Layer IDs
# ---------------------------------------------------------------------------
class TSRLLayer(Enum):
    OBSERVATION = 1   # TSRL-1: continuous state monitoring
    ROUTING = 2       # TSRL-2: attribution-preserving transport
    STABILITY = 3     # TSRL-3: recursive stability enforcement


# ---------------------------------------------------------------------------
# Interposer Check Phases  (IC 4.3)
# ---------------------------------------------------------------------------
class InterposerPhase(Enum):
    IDENTITY_CHECK = "phase_1_identity"
    MEMORY_TIER_CHECK = "phase_2_memory_tier"
    GEOMETRY_CHECK = "phase_3_geometry"


# ---------------------------------------------------------------------------
# Geometry Resolution Priority  (GC 4.7)
# ---------------------------------------------------------------------------
GEOMETRY_RESOLUTION_ORDER = [
    "invariant_protection",
    "continuity_preservation",
    "capability_limitation",
    "task_resolution",
]

# Control Plane routing priority  (CPC 4.9)
ROUTING_PRIORITY_ORDER = [
    "determinism",
    "safety",
    "latency",
    "throughput",
]


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------
def _trace_id() -> str:
    return uuid.uuid4().hex[:16]


def _timestamp() -> float:
    return time.time()


def _payload_hash(payload: Any) -> str:
    return hashlib.sha256(repr(payload).encode()).hexdigest()[:16]


@dataclass(frozen=True)
class QAMSMessage:
    """Immutable QAMS transport envelope — attribution-preserving."""
    msg_id: str = field(default_factory=_trace_id)
    trace_id: str = field(default_factory=_trace_id)
    origin: ComponentID = ComponentID.DEMO_HARNESS
    destination: ComponentID = ComponentID.CONTROL_PLANE
    msg_type: QAMSMessageType = QAMSMessageType.REQUEST
    payload: dict = field(default_factory=dict)
    payload_hash: str = ""
    timestamp: float = field(default_factory=_timestamp)
    parent_msg_id: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.payload_hash:
            object.__setattr__(self, "payload_hash", _payload_hash(self.payload))


@dataclass
class InterposerVerdict:
    """Result of the three-phase Interposer check."""
    allowed: bool
    phase_results: dict = field(default_factory=dict)
    refusal_code: Optional[RefusalCode] = None
    invariant_violated: Optional[str] = None
    capability_boundary: Optional[str] = None
    safe_alternative: Optional[str] = None
    trace_hash: str = field(default_factory=_trace_id)


@dataclass
class DriftReport:
    """Stability Metrics drift assessment."""
    severity: DriftSeverity = DriftSeverity.NONE
    radial_drift: float = 0.0        # |ΔR| from Fibonacci projection
    phase_noise: float = 0.0         # |Δθ| angle misalignment
    vector_magnitude: float = 0.0    # ||[x,y]||
    sequence_index: int = 0
    memory_bleed_detected: bool = False
    synergy_violation: bool = False
    continuity_fault: bool = False
    details: str = ""
    trace_hash: str = field(default_factory=_trace_id)


@dataclass
class GeometryAssessment:
    """Deterministic geometry evaluation result."""
    coherent: bool = True
    topology: str = "fibonacci_spiral"
    curvature_metrics: dict = field(default_factory=dict)
    constraint_resolution: str = "nominal"
    trace_hash: str = field(default_factory=_trace_id)


@dataclass
class AuditEntry:
    """Immutable audit log record."""
    entry_id: str = field(default_factory=_trace_id)
    timestamp: float = field(default_factory=_timestamp)
    component: ComponentID = ComponentID.AUDIT_LOG
    action: str = ""
    agent_involved: Optional[str] = None
    invariant_references: list = field(default_factory=list)
    geometry_surface: Optional[str] = None
    result_code: str = "OK"
    trace_id: Optional[str] = None
    details: dict = field(default_factory=dict)


@dataclass(frozen=True)
class CapabilityEnvelope:
    """Hard-gated capability boundary — cannot widen at runtime."""
    envelope_id: str = field(default_factory=_trace_id)
    allowed_tiers: tuple = (MemoryTier.TIER_0, MemoryTier.TIER_1)
    max_drift_tolerance: float = 0.5
    can_write_geometry: bool = False
    can_modify_identity: bool = False
    can_escalate_capability: bool = False
    frozen: bool = True    # Immutable after instantiation
