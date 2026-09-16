"""
Stability Engine v4.0 — Deterministic Audit Log

Traceable, deterministic, externally-inspectable action logging for all
Sentinel Vector / Stability Engine v4 components.

Design constraints (from build_specs.md):
  - Append-only: entries cannot be modified or deleted after recording.
  - All Control Plane actions produce: action ID, agent involved, invariant
    references, timestamp, geometry surface used, result code.
  - All writes to Tier 2 generate: hash lineage, invariants justification,
    capability envelope reference, timestamp, actor identifier.
  - Must be auditable from outside the system (JSON export, human-readable
    export).
  - stdlib only — no external dependencies.
"""

from __future__ import annotations

from copy import deepcopy
import json
import time
from datetime import datetime, timezone
from typing import List, Optional

from core.types import AuditEntry, ComponentID


class AuditLog:
    """
    Append-only deterministic audit log.

    All Stability Engine components write :class:`~core.types.AuditEntry`
    objects here.  Once an entry is recorded it can never be modified or
    removed.  The log is externally inspectable via :meth:`export_json` and
    :meth:`export_human_readable`.

    Thread-safety
    -------------
    The current implementation is not thread-safe.  If concurrent access is
    required, wrap calls to :meth:`record` in an external lock.  Internal
    state is intentionally kept simple because the demo runs single-threaded.
    """

    def __init__(self) -> None:
        # The single backing store.  A tuple is used as the container type to
        # signal immutability intent; entries are accumulated via list
        # internally and exposed as tuples to callers.
        self._entries: List[AuditEntry] = []

    # ------------------------------------------------------------------
    # Write path
    # ------------------------------------------------------------------

    def record(self, entry: AuditEntry) -> None:
        """
        Append *entry* to the audit log.

        This is the ONLY write path.  There is no update, patch, or delete
        operation.  Attempting to modify a previously recorded entry from
        outside this class will have no effect because :class:`AuditEntry`
        objects are copied on ingress and egress.

        Raises
        ------
        TypeError
            If *entry* is not an :class:`~core.types.AuditEntry`.
        """
        if not isinstance(entry, AuditEntry):
            raise TypeError(
                f"AuditLog.record expects an AuditEntry, got {type(entry)}"
            )
        self._entries.append(deepcopy(entry))

    # ------------------------------------------------------------------
    # Read paths
    # ------------------------------------------------------------------

    def get_entries(self) -> List[AuditEntry]:
        """
        Return independent snapshots of all entries in insertion order.

        Callers receive a copy so they cannot accidentally mutate the internal
        list or nested values. This is a cooperative Python boundary.
        """
        return deepcopy(self._entries)

    def get_entries_by_component(
        self, comp: ComponentID
    ) -> List[AuditEntry]:
        """
        Return all entries whose ``component`` field matches *comp*.

        Parameters
        ----------
        comp:
            The :class:`~core.types.ComponentID` to filter by.
        """
        if not isinstance(comp, ComponentID):
            raise TypeError(
                f"comp must be a ComponentID, got {type(comp)}"
            )
        return deepcopy([e for e in self._entries if e.component == comp])

    def get_entries_by_trace(self, trace_id: str) -> List[AuditEntry]:
        """
        Return all entries whose ``trace_id`` matches *trace_id*.

        Parameters
        ----------
        trace_id:
            Hex string trace identifier from the QAMSMessage envelope.
        """
        return deepcopy([e for e in self._entries if e.trace_id == trace_id])

    def get_entries_by_result_code(self, result_code: str) -> List[AuditEntry]:
        """Return all entries with the given *result_code* (e.g. ``"OK"``)."""
        return deepcopy([e for e in self._entries if e.result_code == result_code])

    def get_entries_by_action(self, action: str) -> List[AuditEntry]:
        """Return all entries whose ``action`` field matches *action*."""
        return deepcopy([e for e in self._entries if e.action == action])

    def __len__(self) -> int:
        return len(self._entries)

    # ------------------------------------------------------------------
    # Export / inspection
    # ------------------------------------------------------------------

    def format_entry(self, entry: AuditEntry) -> str:
        """
        Render a single :class:`~core.types.AuditEntry` as a human-readable
        string suitable for terminal output or log files.

        Format::

            [2025-01-01T00:00:00Z] [entry_id] COMPONENT | ACTION
              agent        : <agent_involved or —>
              trace_id     : <trace_id or —>
              result       : <result_code>
              invariants   : [<list>]
              geometry     : <geometry_surface or —>
              details      : <details dict>
        """
        ts_str = _format_timestamp(entry.timestamp)
        component_str = (
            entry.component.value
            if isinstance(entry.component, ComponentID)
            else str(entry.component)
        )
        lines = [
            f"[{ts_str}] [{entry.entry_id}] {component_str} | {entry.action}",
            f"  agent        : {entry.agent_involved or '—'}",
            f"  trace_id     : {entry.trace_id or '—'}",
            f"  result       : {entry.result_code}",
            f"  invariants   : {entry.invariant_references or []}",
            f"  geometry     : {entry.geometry_surface or '—'}",
            f"  details      : {entry.details or {}}",
        ]
        return "\n".join(lines)

    def export_json(self) -> str:
        """
        Serialise the entire audit log to a JSON string.

        Each entry is serialised as a dict with the following keys:
            entry_id, timestamp, timestamp_iso, component, action,
            agent_involved, invariant_references, geometry_surface,
            result_code, trace_id, details

        The JSON is formatted with 2-space indentation for readability.
        """
        records = []
        for entry in self._entries:
            component_val = (
                entry.component.value
                if isinstance(entry.component, ComponentID)
                else str(entry.component)
            )
            records.append(
                {
                    "entry_id": entry.entry_id,
                    "timestamp": entry.timestamp,
                    "timestamp_iso": _format_timestamp(entry.timestamp),
                    "component": component_val,
                    "action": entry.action,
                    "agent_involved": entry.agent_involved,
                    "invariant_references": entry.invariant_references,
                    "geometry_surface": entry.geometry_surface,
                    "result_code": entry.result_code,
                    "trace_id": entry.trace_id,
                    "details": entry.details,
                }
            )
        return json.dumps(
            {"audit_log": records, "total_entries": len(records)},
            indent=2,
            default=str,
        )

    def export_human_readable(self) -> str:
        """
        Produce a human-readable, line-oriented text representation of the
        full audit log.

        Suitable for writing to a log file or printing to a terminal during
        post-mortem inspection.
        """
        if not self._entries:
            return "=== AUDIT LOG (empty) ===\n"

        header = (
            "=== STABILITY ENGINE v4 — AUDIT LOG ===\n"
            f"Exported : {_format_timestamp(time.time())}\n"
            f"Entries  : {len(self._entries)}\n"
            + "=" * 60
        )
        body_parts = [self.format_entry(e) for e in self._entries]
        footer = "=" * 60 + f"\n[END OF LOG — {len(self._entries)} entries]\n"
        return "\n".join([header] + body_parts) + "\n" + footer


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _format_timestamp(ts: float) -> str:
    """Return ISO-8601 UTC string for a POSIX timestamp."""
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
