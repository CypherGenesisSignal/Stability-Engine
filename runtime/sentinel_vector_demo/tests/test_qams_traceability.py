"""
Test Module 3: QAMS Transport Auditability

Tests that QAMS correctly assigns trace IDs and payload hashes, maintains
a full transport log, supports message lineage lookups, performs deterministic
routing, rejects unknown destinations, dispatches to registered handlers, and
never modifies payload content.
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), ".."
))))

from core.qams import QAMS
from core.types import QAMSMessage, QAMSMessageType, ComponentID


def _make_msg(
    origin=ComponentID.DEMO_HARNESS,
    destination=ComponentID.CONTROL_PLANE,
    msg_type=QAMSMessageType.REQUEST,
    payload=None,
    trace_id=None,
):
    """Helper: construct a QAMSMessage with optional field overrides."""
    kwargs = {
        "origin": origin,
        "destination": destination,
        "msg_type": msg_type,
        "payload": payload if payload is not None else {"data": "test"},
    }
    if trace_id is not None:
        kwargs["trace_id"] = trace_id
    return QAMSMessage(**kwargs)


class TestQAMSTraceability(unittest.TestCase):
    """Tests for QAMS transport auditability and deterministic routing."""

    def setUp(self):
        self.qams = QAMS()

    # ------------------------------------------------------------------
    # Test 1: Every sent message has a trace_id
    # ------------------------------------------------------------------

    def test_message_has_trace_id(self):
        """Every QAMSMessage sent through QAMS must carry a non-empty trace_id."""
        msg = _make_msg()
        sent = self.qams.send(msg)
        self.assertTrue(
            sent.trace_id and len(sent.trace_id) > 0,
            f"Message must have a non-empty trace_id, got: {sent.trace_id!r}",
        )

    # ------------------------------------------------------------------
    # Test 2: Every sent message has a computed payload_hash
    # ------------------------------------------------------------------

    def test_message_has_payload_hash(self):
        """Every QAMSMessage must carry a non-empty payload_hash computed from
        the payload at construction time."""
        msg = _make_msg(payload={"key": "value", "count": 42})
        sent = self.qams.send(msg)
        self.assertTrue(
            sent.payload_hash and len(sent.payload_hash) > 0,
            f"Message must have a non-empty payload_hash, got: {sent.payload_hash!r}",
        )

    # ------------------------------------------------------------------
    # Test 3: Transport log records all sent messages
    # ------------------------------------------------------------------

    def test_transport_log_records_all(self):
        """After sending 3 messages, the transport log must have at least 3
        entries (one ENQUEUED record per message, possibly more for deliveries)."""
        for i in range(3):
            self.qams.send(_make_msg(payload={"i": i}))

        log = self.qams.get_transport_log()
        enqueued = [e for e in log if e["action"] == "ENQUEUED"]
        self.assertEqual(
            len(enqueued),
            3,
            f"Transport log must have exactly 3 ENQUEUED entries after 3 sends; "
            f"got {len(enqueued)}: {enqueued}",
        )

    # ------------------------------------------------------------------
    # Test 4: Message lineage by trace_id
    # ------------------------------------------------------------------

    def test_message_lineage_by_trace_id(self):
        """Messages sharing the same trace_id must all be returned by
        get_message_lineage(trace_id)."""
        shared_trace = "shared_trace_abc123"
        msg1 = _make_msg(trace_id=shared_trace, payload={"step": 1})
        msg2 = _make_msg(
            trace_id=shared_trace,
            destination=ComponentID.INTERPOSER,
            payload={"step": 2},
        )
        # msg3 has a different trace_id — should NOT appear in lineage
        msg3 = _make_msg(payload={"step": 3})

        self.qams.send(msg1)
        self.qams.send(msg2)
        self.qams.send(msg3)

        lineage = self.qams.get_message_lineage(shared_trace)
        self.assertEqual(
            len(lineage),
            2,
            f"Lineage for shared_trace should return 2 messages, got {len(lineage)}",
        )
        trace_ids_in_lineage = {m.trace_id for m in lineage}
        self.assertEqual(
            trace_ids_in_lineage,
            {shared_trace},
            "All messages in lineage must share the queried trace_id",
        )

    # ------------------------------------------------------------------
    # Test 5: Deterministic routing — route() returns msg.destination verbatim
    # ------------------------------------------------------------------

    def test_deterministic_routing(self):
        """route() must return msg.destination exactly as declared by the sender,
        without any adaptive rerouting or payload inspection."""
        for dest in (
            ComponentID.CONTROL_PLANE,
            ComponentID.INTERPOSER,
            ComponentID.GEOMETRY,
            ComponentID.STABILITY_METRICS,
        ):
            msg = _make_msg(destination=dest)
            routed_dest = self.qams.route(msg)
            self.assertEqual(
                routed_dest,
                dest,
                f"route() must return declared destination {dest}, got {routed_dest}",
            )

    # ------------------------------------------------------------------
    # Test 6: Unknown destination raises ValueError
    # ------------------------------------------------------------------

    def test_unknown_destination_rejected(self):
        """Routing a message to an unknown (non-ComponentID) destination must
        raise a ValueError — QAMS enforces deterministic routing (no silent
        rerouting to unknown targets)."""
        # QAMSMessage is frozen; patch destination via object.__setattr__ to
        # inject an invalid value without constructing with invalid args.
        msg = _make_msg()
        object.__setattr__(msg, "destination", "totally_unknown_destination")

        # route() is the public routing surface that validates the destination
        # and raises ValueError for unknown targets.
        with self.assertRaises(ValueError):
            self.qams.route(msg)

    # ------------------------------------------------------------------
    # Test 7: Handler registration and dispatch
    # ------------------------------------------------------------------

    def test_handler_registration_and_dispatch(self):
        """After registering a handler for a component and sending a message to
        that component, dispatch() must invoke the handler with the message."""
        received = []

        def my_handler(msg: QAMSMessage):
            received.append(msg)

        self.qams.register_handler(ComponentID.INTERPOSER, my_handler)

        msg = _make_msg(destination=ComponentID.INTERPOSER, payload={"cmd": "check"})
        self.qams.send(msg)

        # Handler must not have fired yet (dispatch is explicit)
        self.assertEqual(len(received), 0, "Handler must not fire before dispatch()")

        delivered = self.qams.dispatch()

        self.assertEqual(delivered, 1, f"dispatch() must return 1, got {delivered}")
        self.assertEqual(len(received), 1, "Handler must have received exactly 1 message")
        self.assertEqual(
            received[0].msg_id,
            msg.msg_id,
            "Handler must receive the exact message that was sent",
        )

    # ------------------------------------------------------------------
    # Test 8: QAMS does not modify payload
    # ------------------------------------------------------------------

    def test_qams_does_not_modify_payload(self):
        """The payload_hash recorded in the transport log must match the
        payload_hash on the message (QAMS must not alter payload content)."""
        payload = {"important": "data", "value": 99, "nested": {"x": 1}}
        msg = _make_msg(payload=payload)
        original_hash = msg.payload_hash

        self.qams.send(msg)

        log = self.qams.get_transport_log()
        enqueued_entries = [e for e in log if e["action"] == "ENQUEUED"]
        self.assertEqual(len(enqueued_entries), 1)

        logged_hash = enqueued_entries[0]["payload_hash"]
        self.assertEqual(
            logged_hash,
            original_hash,
            f"Transport log payload_hash ({logged_hash!r}) must match the original "
            f"message payload_hash ({original_hash!r}); QAMS must not alter payloads",
        )


if __name__ == "__main__":
    unittest.main()
