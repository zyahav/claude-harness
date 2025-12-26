"""
Unit tests for Harness Commander event logging.
"""

import unittest
import tempfile
import json
from pathlib import Path
from uuid import uuid4

from events import (
    EventLogger,
    Event,
    EventType,
    read_events,
    get_session_events,
    EVENTS_LOG,
)


class TestEvent(unittest.TestCase):
    """Test Event dataclass."""

    def test_event_to_json_line(self):
        """Test Event serializes to JSON line correctly."""
        event = Event(
            timestamp="2025-01-01T00:00:00Z",
            type="TEST_EVENT",
            sessionId=str(uuid4()),
            data={"key": "value"},
        )

        json_line = event.to_json_line()
        data = json.loads(json_line)

        self.assertEqual(data["timestamp"], "2025-01-01T00:00:00Z")
        self.assertEqual(data["type"], "TEST_EVENT")
        self.assertEqual(data["data"]["key"], "value")


class TestEventLogger(unittest.TestCase):
    """Test EventLogger class."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.log_path = Path(self.temp_dir) / "events.log"
        self.logger = EventLogger(log_path=self.log_path)

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_log_event_creates_file(self):
        """Test log_event creates log file."""
        self.logger.log_event("TEST_EVENT", {})

        self.assertTrue(self.log_path.exists())

    def test_log_event_appends(self):
        """Test log_event appends multiple events."""
        self.logger.log_event("EVENT_1", {})
        self.logger.log_event("EVENT_2", {})

        with open(self.log_path, "r") as f:
            lines = f.readlines()

        self.assertEqual(len(lines), 2)

    def test_log_event_with_enum(self):
        """Test log_event works with EventType enum."""
        self.logger.log_event(EventType.SESSION_STARTED, {})

        events = read_events(self.log_path)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].type, "SESSION_STARTED")

    def test_log_event_with_string(self):
        """Test log_event works with string type."""
        self.logger.log_event("CUSTOM_EVENT", {"key": "value"})

        events = read_events(self.log_path)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].type, "CUSTOM_EVENT")
        self.assertEqual(events[0].data["key"], "value")

    def test_log_session_start(self):
        """Test log_session_start convenience method."""
        self.logger.log_session_start(mode="controller")

        events = read_events(self.log_path)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].type, "SESSION_STARTED")
        self.assertEqual(events[0].data["mode"], "controller")

    def test_log_session_end(self):
        """Test log_session_end convenience method."""
        self.logger.log_session_end()

        events = read_events(self.log_path)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].type, "SESSION_ENDED")

    def test_log_lock_acquired(self):
        """Test log_lock_acquired convenience method."""
        self.logger.log_lock_acquired()

        events = read_events(self.log_path)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].type, "LOCK_ACQUIRED")

    def test_log_lock_denied(self):
        """Test log_lock_denied convenience method."""
        self.logger.log_lock_denied(controller_pid=12345)

        events = read_events(self.log_path)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].type, "LOCK_DENIED")
        self.assertEqual(events[0].data["controllerPid"], 12345)

    def test_log_lock_released(self):
        """Test log_lock_released convenience method."""
        self.logger.log_lock_released()

        events = read_events(self.log_path)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].type, "LOCK_RELEASED")

    def test_log_lock_stale_takeover(self):
        """Test log_lock_stale_takeover convenience method."""
        self.logger.log_lock_stale_takeover(reason="PID_DEAD")

        events = read_events(self.log_path)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].type, "LOCK_STALE_TAKEOVER")
        self.assertEqual(events[0].data["reason"], "PID_DEAD")

    def test_log_reconcile_start(self):
        """Test log_reconcile_start convenience method."""
        self.logger.log_reconcile_start()

        events = read_events(self.log_path)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].type, "RECONCILE_START")

    def test_log_reconcile_result(self):
        """Test log_reconcile_result convenience method."""
        self.logger.log_reconcile_result(changes={"runsAdded": 2})

        events = read_events(self.log_path)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].type, "RECONCILE_RESULT")
        self.assertEqual(events[0].data["runsAdded"], 2)

    def test_log_command_plan(self):
        """Test log_command_plan convenience method."""
        self.logger.log_command_plan("start", {"runName": "test"})

        events = read_events(self.log_path)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].type, "COMMAND_PLAN")
        self.assertEqual(events[0].data["command"], "start")

    def test_log_command_execute(self):
        """Test log_command_execute convenience method."""
        self.logger.log_command_execute("finish")

        events = read_events(self.log_path)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].type, "COMMAND_EXECUTE")

    def test_log_command_verify_ok(self):
        """Test log_command_verify_ok convenience method."""
        self.logger.log_command_verify_ok("start")

        events = read_events(self.log_path)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].type, "COMMAND_VERIFY_OK")

    def test_log_command_verify_fail(self):
        """Test log_command_verify_fail convenience method."""
        self.logger.log_command_verify_fail("start", "Worktree not found")

        events = read_events(self.log_path)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].type, "COMMAND_VERIFY_FAIL")
        self.assertEqual(events[0].data["error"], "Worktree not found")

    def test_log_state_updated(self):
        """Test log_state_updated convenience method."""
        self.logger.log_state_updated({"focusProjectId": "proj-123"})

        events = read_events(self.log_path)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].type, "STATE_UPDATED")
        self.assertEqual(events[0].data["focusProjectId"], "proj-123")

    def test_session_id_persistence(self):
        """Test that sessionId is included in all events."""
        session_id = self.logger.sessionId

        self.logger.log_event("TEST_1", {})
        self.logger.log_event("TEST_2", {})

        events = read_events(self.log_path)

        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].sessionId, session_id)
        self.assertEqual(events[1].sessionId, session_id)

    def test_session_id_generated_if_not_provided(self):
        """Test that sessionId is generated if not provided."""
        logger = EventLogger(log_path=self.log_path)
        self.assertIsNotNone(logger.sessionId)
        self.assertTrue(len(logger.sessionId) > 0)


class TestReadEvents(unittest.TestCase):
    """Test read_events function."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.log_path = Path(self.temp_dir) / "events.log"

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_read_events_returns_empty_list_if_file_missing(self):
        """Test read_events returns empty list if file doesn't exist."""
        events = read_events(self.log_path)
        self.assertEqual(len(events), 0)

    def test_read_events_parses_json_lines(self):
        """Test read_events parses JSON lines correctly."""
        logger = EventLogger(log_path=self.log_path)
        logger.log_event("TEST_1", {"key": "value1"})
        logger.log_event("TEST_2", {"key": "value2"})

        events = read_events(self.log_path)

        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].type, "TEST_1")
        self.assertEqual(events[1].type, "TEST_2")

    def test_read_events_with_limit(self):
        """Test read_events respects limit parameter."""
        logger = EventLogger(log_path=self.log_path)
        for i in range(10):
            logger.log_event(f"EVENT_{i}", {})

        events = read_events(self.log_path, limit=5)

        # Should return most recent 5
        self.assertEqual(len(events), 5)

    def test_read_events_skips_empty_lines(self):
        """Test read_events skips empty lines."""
        self.log_path.write_text("\n\n\n")
        events = read_events(self.log_path)
        self.assertEqual(len(events), 0)

    def test_read_events_skips_malformed_lines(self):
        """Test read_events skips malformed JSON lines."""
        logger = EventLogger(log_path=self.log_path)
        logger.log_event("VALID_EVENT", {})

        # Append malformed line
        with open(self.log_path, "a") as f:
            f.write("this is not json\n")

        events = read_events(self.log_path)

        # Should only return valid event
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].type, "VALID_EVENT")


class TestGetSessionEvents(unittest.TestCase):
    """Test get_session_events function."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.log_path = Path(self.temp_dir) / "events.log"
        self.session_id_1 = str(uuid4())
        self.session_id_2 = str(uuid4())

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_session_events_filters_by_session_id(self):
        """Test get_session_events filters correctly."""
        logger1 = EventLogger(log_path=self.log_path, session_id=self.session_id_1)
        logger2 = EventLogger(log_path=self.log_path, session_id=self.session_id_2)

        logger1.log_event("SESSION_1_EVENT", {})
        logger2.log_event("SESSION_2_EVENT", {})
        logger1.log_event("SESSION_1_EVENT_2", {})

        events_session1 = get_session_events(self.session_id_1, self.log_path)
        events_session2 = get_session_events(self.session_id_2, self.log_path)

        self.assertEqual(len(events_session1), 2)
        self.assertEqual(len(events_session2), 1)
        self.assertEqual(events_session2[0].type, "SESSION_2_EVENT")

    def test_get_session_events_returns_empty_for_unknown_session(self):
        """Test get_session_events returns empty list for unknown session."""
        logger = EventLogger(log_path=self.log_path)
        logger.log_event("TEST", {})

        events = get_session_events("unknown-session-id", self.log_path)

        self.assertEqual(len(events), 0)


class TestEventType(unittest.TestCase):
    """Test EventType enum."""

    def test_event_type_values(self):
        """Test EventType enum has correct values."""
        self.assertEqual(EventType.SESSION_STARTED, "SESSION_STARTED")
        self.assertEqual(EventType.LOCK_ACQUIRED, "LOCK_ACQUIRED")
        self.assertEqual(EventType.COMMAND_PLAN, "COMMAND_PLAN")

    def test_event_type_in_string_context(self):
        """Test EventType works as string."""
        event_type = EventType.SESSION_STARTED
        self.assertEqual(str(event_type), "SESSION_STARTED")
        self.assertEqual(event_type.value, "SESSION_STARTED")


if __name__ == "__main__":
    unittest.main()
