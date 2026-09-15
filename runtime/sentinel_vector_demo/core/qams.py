"""
Stability Engine v4.0 — QAMS (Queue-and-Attribute Message Service)

Internal message transport layer.  QAMS is a TRANSPORT layer, NOT a decision
layer.  It carries messages between components, maintains a deterministic
routing table, and records a full audit trail of every transport action.

Hard constraints (from build_specs.md):
  - Routing is deterministic, subordinate to Control Plane and Interposer
    constraints.  It is NOT adaptive or emergent.
  - QAMS never alters payload semantics and never infers intent from content.
  - QAMS never decides policy and never grants authority.
  - All transport actions are logged for post-mortem inspection.
"""

from __future__ import annotations

import time
import uuid
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional

from core.types import AuditEntry, ComponentID, QAMSMessage, QAMSMessageType


# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------
HandlerFn = Callable[[QAMSMessage], Any]
TransportRecord = Dict[str, Any]


# ---------------------------------------------------------------------------
# Known (valid) destinations — all ComponentIDs are valid destinations.
# This set is fixed at class definition time and never mutated at runtime.
# ---------------------------------------------------------------------------
_VALID_DESTINATIONS: frozenset[ComponentID] = frozenset(ComponentID)


class QAMS:
    """
    Queue-and-Attribute Message Service.

    Responsibilities
    ----------------
    - Accept QAMSMessage objects and place them on the appropriate
      per-destination queue.
    - Provide deterministic routing via :meth:`route`.
    - Deliver queued messages to registered component handlers via
      :meth:`dispatch`.
    - Maintain an append-only transport audit trail.
    - Expose message lineage lookups via :meth:`get_message_lineage`.

    Non-responsibilities
    --------------------
    - QAMS does NOT decide policy.
    - QAMS does NOT interpret, transform, or infer anything from payload
      content.
    - QAMS does NOT grant, revoke, or modify authority.
    """

    def __init__(self) -> None:
        # Per-destination message queues (component_id → list of messages)
        self._queues: Dict[ComponentID, List[QAMSMessage]] = defaultdict(list)

        # Registered delivery callbacks (component_id → callable)
        self._handlers: Dict[ComponentID, HandlerFn] = {}

        # Flat, append-only transport audit trail
        self._transport_log: List[TransportRecord] = []

        # All messages ever accepted, keyed by trace_id, for lineage lookups
        self._trace_index: Dict[str, List[QAMSMessage]] = defaultdict(list)

        # All messages ever accepted, keyed by msg_id
        self._msg_index: Dict[str, QAMSMessage] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def send(self, msg: QAMSMessage) -> QAMSMessage:
        """
        Accept *msg* into the transport layer.

        Validates that the destination is a known ComponentID, enqueues the
        message on the destination queue, indexes it for lineage lookups, and
        records a transport log entry.

        Returns the message unchanged (QAMS never mutates payload semantics).

        Raises
        ------
        ValueError
            If ``msg.destination`` is not a known ComponentID.
        """
        if msg.destination not in _VALID_DESTINATIONS:
            self._record_transport_action(
                msg=msg,
                action="REJECTED",
                note=f"Unknown destination: {msg.destination!r}",
            )
            raise ValueError(
                f"QAMS: unknown destination '{msg.destination}'. "
                "Route validation failed — message rejected."
            )

        # Enqueue
        self._queues[msg.destination].append(msg)

        # Index for lineage / lookup
        self._trace_index[msg.trace_id].append(msg)
        self._msg_index[msg.msg_id] = msg

        # Audit trail
        self._record_transport_action(msg=msg, action="ENQUEUED")

        return msg

    def route(self, msg: QAMSMessage) -> ComponentID:
        """
        Return the deterministic destination for *msg*.

        Routing is purely a function of ``msg.destination`` as declared by the
        sender.  QAMS does not inspect payload content to override or adjust
        routing.  If the declared destination is unknown, a ``ValueError`` is
        raised rather than silently rerouting.

        Priority order (CPC 4.9 / build_specs): determinism → safety →
        latency → throughput.  In a transport-only layer determinism means
        honouring the declared destination without modification.

        Raises
        ------
        ValueError
            If ``msg.destination`` is not a known ComponentID.
        """
        if msg.destination not in _VALID_DESTINATIONS:
            raise ValueError(
                f"QAMS.route: cannot route to unknown destination "
                f"'{msg.destination}'."
            )
        return msg.destination

    def register_handler(
        self, component_id: ComponentID, handler_fn: HandlerFn
    ) -> None:
        """
        Register *handler_fn* to receive messages delivered to
        *component_id*.

        Only one handler per component is supported.  Registering a second
        time silently replaces the previous handler.
        """
        if not isinstance(component_id, ComponentID):
            raise TypeError(
                f"component_id must be a ComponentID, got {type(component_id)}"
            )
        if not callable(handler_fn):
            raise TypeError("handler_fn must be callable")
        self._handlers[component_id] = handler_fn

    def dispatch(self) -> int:
        """
        Deliver all queued messages to their registered handlers.

        Messages are delivered in FIFO order per destination.  If no handler
        is registered for a destination the messages remain queued (they are
        NOT dropped).

        Returns the total number of messages delivered in this pass.
        """
        delivered = 0
        for component_id, handler_fn in list(self._handlers.items()):
            queue = self._queues[component_id]
            while queue:
                msg = queue.pop(0)
                self._record_transport_action(msg=msg, action="DELIVERED")
                handler_fn(msg)
                delivered += 1
        return delivered

    def get_transport_log(self) -> List[TransportRecord]:
        """
        Return the full, append-only transport audit trail.

        Each entry is a dict with the following keys:
            log_id          — unique ID for this log entry
            timestamp       — wall-clock time of transport action
            msg_id          — ID of the transported message
            trace_id        — trace ID from the message envelope
            origin          — ComponentID string of the sender
            destination     — ComponentID string of the declared destination
            msg_type        — QAMSMessageType string
            payload_hash    — SHA-256 prefix of the payload at send time
            action          — one of: ENQUEUED, DELIVERED, REJECTED
            note            — optional free-text note (e.g. rejection reason)

        The returned list is a shallow copy; callers cannot mutate internal
        state.
        """
        return list(self._transport_log)

    def get_message_lineage(self, trace_id: str) -> List[QAMSMessage]:
        """
        Return all messages sharing *trace_id*, in arrival order.

        This supports post-mortem tracing: given the trace ID of any message
        in a causal chain, callers can reconstruct the full sequence of
        transport hops for that chain.

        Returns an empty list if *trace_id* is unknown.
        """
        return list(self._trace_index.get(trace_id, []))

    def get_queue_depth(self, component_id: ComponentID) -> int:
        """Return the number of messages currently queued for *component_id*."""
        return len(self._queues[component_id])

    def get_queued_messages(
        self, component_id: ComponentID
    ) -> List[QAMSMessage]:
        """
        Return a copy of the current queue for *component_id* without
        consuming it.
        """
        return list(self._queues[component_id])

    def build_audit_entry(self, msg: QAMSMessage, action: str) -> AuditEntry:
        """
        Construct an :class:`~core.types.AuditEntry` from a transport event.

        This is a convenience helper used by other components that wish to
        record QAMS transport actions in the system audit log.
        """
        return AuditEntry(
            component=ComponentID.AUDIT_LOG,
            action=f"QAMS:{action}",
            trace_id=msg.trace_id,
            result_code="OK" if action != "REJECTED" else "REJECTED",
            details={
                "msg_id": msg.msg_id,
                "origin": msg.origin.value,
                "destination": msg.destination.value,
                "msg_type": msg.msg_type.value,
                "payload_hash": msg.payload_hash,
                "timestamp": msg.timestamp,
            },
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _record_transport_action(
        self,
        msg: QAMSMessage,
        action: str,
        note: Optional[str] = None,
    ) -> None:
        """
        Append a structured record to the internal transport audit trail.

        This method is the ONLY path through which entries are added; it is
        called unconditionally for every accept, delivery, and rejection event.
        """
        record: TransportRecord = {
            "log_id": uuid.uuid4().hex[:16],
            "timestamp": time.time(),
            "msg_id": msg.msg_id,
            "trace_id": msg.trace_id,
            "origin": msg.origin.value,
            "destination": msg.destination.value,
            "msg_type": msg.msg_type.value,
            "payload_hash": msg.payload_hash,
            "action": action,
            "note": note or "",
        }
        self._transport_log.append(record)
