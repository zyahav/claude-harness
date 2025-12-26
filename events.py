"""
Harness Commander - Event Logging
==================================

Append-only event logging system for audit trail and debugging.
"""

import json
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, Any
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)

# Event log file path
from state import COMMANDER_HOME

EVENTS_LOG = COMMANDER_HOME / "events.log"


class EventType(str, Enum):
    """Event types for Commander."""

    # Session lifecycle
    SESSION_STARTED = "SESSION_STARTED"
    SESSION_ENDED = "SESSION_ENDED"

    # Lock events
    LOCK_ACQUIRED = "LOCK_ACQUIRED"
    LOCK_DENIED = "LOCK_DENIED"
    LOCK_RELEASED = "LOCK_RELEASED"
    LOCK_STALE_TAKEOVER = "LOCK_STALE_TAKEOVER"

    # Reconciliation
    RECONCILE_START = "RECONCILE_START"
    RECONCILE_RESULT = "RECONCILE_RESULT"

    # Commands
    COMMAND_PLAN = "COMMAND_PLAN"
    COMMAND_EXECUTE = "COMMAND_EXECUTE"
    COMMAND_VERIFY_OK = "COMMAND_VERIFY_OK"
    COMMAND_VERIFY_FAIL = "COMMAND_VERIFY_FAIL"

    # State changes
    STATE_UPDATED = "STATE_UPDATED"


@dataclass
class Event:
    """A single event in the log."""

    timestamp: str
    type: str
    sessionId: str
    data: dict[str, Any]

    def to_json_line(self) -> str:
        """Convert to JSON line for logging."""
        return json.dumps(asdict(self))


class EventLogger:
    """Append-only event logger for Commander."""

    def __init__(self, log_path: Path = EVENTS_LOG, session_id: Optional[str] = None):
        """Initialize event logger.

        Args:
            log_path: Path to events log file
            session_id: Session ID for this logger (generates UUID if None)
        """
        self.log_path = log_path
        self.sessionId = session_id or str(uuid.uuid4())

    def ensure_directories(self) -> None:
        """Ensure log directory exists."""
        COMMANDER_HOME.mkdir(parents=True, exist_ok=True)

    def log_event(
        self, event_type: str | EventType, data: dict[str, Any]
    ) -> None:
        """Log an event to the append-only log.

        Args:
            event_type: Type of event (EventType enum or string)
            data: Additional event data
        """
        self.ensure_directories()

        # Convert enum to string if needed
        if isinstance(event_type, EventType):
            event_type = event_type.value

        event = Event(
            timestamp=datetime.utcnow().isoformat() + "Z",
            type=event_type,
            sessionId=self.sessionId,
            data=data,
        )

        # Append to log file
        with open(self.log_path, "a") as f:
            f.write(event.to_json_line())
            f.write("\n")

        logger.debug(f"Logged event: {event_type}")

    def log_session_start(self, mode: str = "controller") -> None:
        """Log session start.

        Args:
            mode: "controller" or "observer"
        """
        self.log_event(
            EventType.SESSION_STARTED,
            {"mode": mode, "sessionId": self.sessionId},
        )

    def log_session_end(self) -> None:
        """Log session end."""
        self.log_event(EventType.SESSION_ENDED, {})

    def log_lock_acquired(self) -> None:
        """Log lock acquisition."""
        self.log_event(EventType.LOCK_ACQUIRED, {"sessionId": self.sessionId})

    def log_lock_denied(self, controller_pid: int) -> None:
        """Log lock denial.

        Args:
            controller_pid: PID of the controller holding the lock
        """
        self.log_event(
            EventType.LOCK_DENIED, {"controllerPid": controller_pid}
        )

    def log_lock_released(self) -> None:
        """Log lock release."""
        self.log_event(EventType.LOCK_RELEASED, {})

    def log_lock_stale_takeover(self, reason: str) -> None:
        """Log stale lock takeover.

        Args:
            reason: "PID_DEAD" or "HEARTBEAT_TIMEOUT"
        """
        self.log_event(EventType.LOCK_STALE_TAKEOVER, {"reason": reason})

    def log_reconcile_start(self) -> None:
        """Log reconciliation start."""
        self.log_event(EventType.RECONCILE_START, {})

    def log_reconcile_result(self, changes: dict[str, int]) -> None:
        """Log reconciliation result.

        Args:
            changes: Dict with change counts (e.g., {"projectsAdded": 1, "runsRemoved": 2})
        """
        self.log_event(EventType.RECONCILE_RESULT, changes)

    def log_command_plan(self, command: str, plan: dict[str, Any]) -> None:
        """Log command plan.

        Args:
            command: Command name
            plan: Plan details
        """
        self.log_event(EventType.COMMAND_PLAN, {"command": command, "plan": plan})

    def log_command_execute(self, command: str) -> None:
        """Log command execution.

        Args:
            command: Command name
        """
        self.log_event(EventType.COMMAND_EXECUTE, {"command": command})

    def log_command_verify_ok(self, command: str) -> None:
        """Log successful command verification.

        Args:
            command: Command name
        """
        self.log_event(EventType.COMMAND_VERIFY_OK, {"command": command})

    def log_command_verify_fail(self, command: str, error: str) -> None:
        """Log failed command verification.

        Args:
            command: Command name
            error: Error message
        """
        self.log_event(
            EventType.COMMAND_VERIFY_FAIL, {"command": command, "error": error}
        )

    def log_state_updated(self, changes: dict[str, Any]) -> None:
        """Log state update.

        Args:
            changes: Description of changes (e.g., {"focusProjectId": "proj-123"})
        """
        self.log_event(EventType.STATE_UPDATED, changes)


def read_events(
    log_path: Path = EVENTS_LOG, limit: Optional[int] = None
) -> list[Event]:
    """Read events from log file.

    Args:
        log_path: Path to events log
        limit: Maximum number of events to read (most recent first)

    Returns:
        List of Event objects (empty if file doesn't exist)
    """
    if not log_path.exists():
        return []

    events = []

    try:
        with open(log_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    data = json.loads(line)
                    event = Event(**data)
                    events.append(event)
                except (json.JSONDecodeError, TypeError) as e:
                    logger.warning(f"Skipping malformed event log line: {e}")

        # If limit specified, return most recent events
        if limit and len(events) > limit:
            events = events[-limit:]

        return events

    except Exception as e:
        logger.error(f"Error reading event log: {e}")
        return []


def get_session_events(
    session_id: str, log_path: Path = EVENTS_LOG
) -> list[Event]:
    """Get all events for a specific session.

    Args:
        session_id: Session ID to filter by
        log_path: Path to events log

    Returns:
        List of events for the session
    """
    all_events = read_events(log_path)
    return [e for e in all_events if e.sessionId == session_id]
