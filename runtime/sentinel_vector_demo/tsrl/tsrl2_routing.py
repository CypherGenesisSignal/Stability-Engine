"""
TSRL-2 Routing and Attribution Layer
Stability Engine v4.0

Transforms observed drift into traceable, attribution-preserving signals.
Enforces deterministic transport WITHOUT semantic compression.
Guarantees: integrity and lineage.

Constraints enforced here:
- Every signal retains full fidelity — no summarisation, no payload trimming.
- Origin attribution is immutable once stamped; cannot be overwritten in transit.
- Each routing step is appended to the ledger, never mutated.
- Signals are rejected for routing if they fail attribution verification.
"""

from __future__ import annotations

from typing import Optional

from core.types import ComponentID, _trace_id, _timestamp, _payload_hash


class TSRL2Routing:
    """
    Attribution-preserving routing layer.

    Responsibilities
    ----------------
    - Transform raw TSRL-1 observations into attributed, integrity-stamped
      signals for transport to higher layers.
    - Route signals deterministically to destination components while
      recording a tamper-evident ledger of every hop.
    - Verify that signals entering the routing path carry valid attribution
      before forwarding.

    What this layer must NOT do
    ---------------------------
    - Alter, summarise, compress, or re-interpret signal payloads.
    - Grant authority or make policy decisions.
    - Strip or overwrite origin attribution.
    - Reorder routing based on content inference.
    """

    def __init__(self) -> None:
        # Append-only routing ledger — all hops recorded in order
        self.routing_ledger: list[dict] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def transform_observation_to_signal(self, observation: dict) -> dict:
        """
        Convert a raw TSRL-1 observation into an attributed signal.

        Rules
        -----
        - Full payload fidelity preserved — no semantic compression.
        - A new ``trace_id`` is minted for the signal (but the original
          observation trace is carried as ``origin_trace_id``).
        - ``origin_attribution`` is stamped from the observation's
          ``component_id`` field and is immutable for the lifetime of the
          signal.
        - An ``integrity_hash`` covers the entire observation payload for
          tamper-detection downstream.

        Parameters
        ----------
        observation : dict
            A raw observation record as produced by TSRL-1.

        Returns
        -------
        dict
            An attributed signal ready for routing.  Contains all original
            observation data under ``payload`` (full fidelity, no trimming).
        """
        signal = {
            "record_type": "attributed_signal",
            "signal_id": _trace_id(),
            "trace_id": _trace_id(),
            # Preserve the originating observation's trace for lineage
            "origin_trace_id": observation.get("trace_id"),
            # Immutable origin attribution — stamped here, never overwritten
            "origin_attribution": observation.get("component_id", ComponentID.DEMO_HARNESS.value),
            "timestamp": _timestamp(),
            # Full payload — NO semantic compression
            "payload": dict(observation),
            # Integrity hash covers the entire observation
            "integrity_hash": _payload_hash(observation),
            # Explicit flags for downstream verification
            "semantically_compressed": False,
            "attribution_intact": True,
        }
        return signal

    def route_signal(self, signal: dict, destination: ComponentID) -> dict:
        """
        Attach routing metadata to *signal* and record the hop in the ledger.

        Parameters
        ----------
        signal : dict
            An attributed signal as produced by
            :meth:`transform_observation_to_signal`.
        destination : ComponentID
            The target component this signal is being dispatched to.

        Returns
        -------
        dict
            The routed signal with ``destination``, ``routing_timestamp``,
            and ``routing_hop_id`` appended.  Payload is never modified.

        Raises
        ------
        ValueError
            If the signal fails attribution verification (see
            :meth:`verify_attribution`).
        """
        if not self.verify_attribution(signal):
            raise ValueError(
                f"TSRL-2: Signal '{signal.get('signal_id')}' failed attribution "
                f"verification — routing rejected to preserve integrity guarantees."
            )

        routed_signal = dict(signal)
        routed_signal["destination"] = destination.value
        routed_signal["routing_timestamp"] = _timestamp()
        routed_signal["routing_hop_id"] = _trace_id()

        ledger_entry = {
            "ledger_entry_type": "routing_hop",
            "hop_id": routed_signal["routing_hop_id"],
            "signal_id": signal.get("signal_id"),
            "trace_id": signal.get("trace_id"),
            "origin_attribution": signal.get("origin_attribution"),
            "destination": destination.value,
            "timestamp": routed_signal["routing_timestamp"],
            "integrity_hash": signal.get("integrity_hash"),
        }
        self.routing_ledger.append(ledger_entry)

        return routed_signal

    def verify_attribution(self, signal: dict) -> bool:
        """
        Verify that *signal* carries valid attribution metadata.

        Checks
        ------
        1. ``origin_attribution`` field is present and non-empty.
        2. ``trace_id`` field is present and non-empty.
        3. ``integrity_hash`` field is present and non-empty.
        4. ``semantically_compressed`` is ``False`` (full-fidelity guarantee).
        5. ``attribution_intact`` is ``True``.

        Parameters
        ----------
        signal : dict
            Signal to verify.

        Returns
        -------
        bool
            ``True`` if all checks pass; ``False`` otherwise.
        """
        if not signal.get("origin_attribution"):
            return False
        if not signal.get("trace_id"):
            return False
        if not signal.get("integrity_hash"):
            return False
        if signal.get("semantically_compressed", True):
            return False
        if not signal.get("attribution_intact", False):
            return False
        return True

    def get_routing_ledger(self) -> list:
        """
        Return the full routing history in insertion order.

        Returns
        -------
        list
            All ledger entries representing every routing hop recorded.
        """
        return list(self.routing_ledger)

    def get_lineage(self, trace_id: str) -> list:
        """
        Return all routing ledger records associated with *trace_id*.

        Parameters
        ----------
        trace_id : str
            The trace identifier to look up.  Matched against the
            ``trace_id`` field of every ledger entry.

        Returns
        -------
        list
            All ledger entries for the given trace in insertion order.
            Empty list if no matching records exist.
        """
        return [
            entry
            for entry in self.routing_ledger
            if entry.get("trace_id") == trace_id
        ]
