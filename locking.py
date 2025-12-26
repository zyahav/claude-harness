"""
Harness Commander - Concurrency Control
========================================

Controller lock with PID liveness and heartbeat for crash recovery.
Ensures only one controller session can mutate state at a time.
"""

import os
import json
import fcntl
import uuid
import atexit
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# Lock file paths
from state import COMMANDER_HOME

LOCKS_DIR = COMMANDER_HOME / "locks"
LOCK_FILE = LOCKS_DIR / "commander.lock"
HEARTBEAT_FILE = LOCKS_DIR / "commander.heartbeat"

# Heartbeat timeout (5 minutes)
HEARTBEAT_TIMEOUT = timedelta(minutes=5)


@dataclass
class LockInfo:
    """Information stored in lock file."""

    pid: int
    startTime: str
    sessionId: str

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "LockInfo":
        """Create from dictionary."""
        return cls(
            pid=data["pid"],
            startTime=data["startTime"],
            sessionId=data["sessionId"],
        )


@dataclass
class HeartbeatInfo:
    """Information stored in heartbeat file."""

    sessionId: str
    lastBeatAt: str

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "HeartbeatInfo":
        """Create from dictionary."""
        return cls(
            sessionId=data["sessionId"],
            lastBeatAt=data["lastBeatAt"],
        )


class LockManager:
    """Manages controller lock with crash and hang recovery."""

    def __init__(
        self,
        lock_path: Path = LOCK_FILE,
        heartbeat_path: Path = HEARTBEAT_FILE,
    ):
        """Initialize lock manager.

        Args:
            lock_path: Path to lock file
            heartbeat_path: Path to heartbeat file
        """
        self.lock_path = lock_path
        self.heartbeat_path = heartbeat_path
        self.sessionId: Optional[str] = None
        self.lock_fd: Optional[int] = None
        self._heartbeat_active = False
        self._release_registered = False

    def ensure_directories(self) -> None:
        """Ensure locks directory exists."""
        LOCKS_DIR.mkdir(parents=True, exist_ok=True)

    def check_pid_alive(self, pid: int) -> bool:
        """Check if a PID is alive.

        Args:
            pid: Process ID to check

        Returns:
            True if PID is alive, False otherwise
        """
        try:
            os.kill(pid, 0)  # Signal 0 just checks if process exists
            return True
        except (OSError, ProcessLookupError):
            return False

    def read_lock_info(self) -> Optional[LockInfo]:
        """Read current lock file.

        Returns:
            LockInfo if lock file exists, None otherwise
        """
        if not self.lock_path.exists():
            return None

        try:
            with open(self.lock_path, "r") as f:
                data = json.load(f)
            return LockInfo.from_dict(data)
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Invalid lock file: {e}")
            return None

    def read_heartbeat_info(self) -> Optional[HeartbeatInfo]:
        """Read current heartbeat file.

        Returns:
            HeartbeatInfo if heartbeat file exists, None otherwise
        """
        if not self.heartbeat_path.exists():
            return None

        try:
            with open(self.heartbeat_path, "r") as f:
                data = json.load(f)
            return HeartbeatInfo.from_dict(data)
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Invalid heartbeat file: {e}")
            return None

    def is_heartbeat_stale(self, heartbeat: HeartbeatInfo) -> bool:
        """Check if heartbeat is stale (older than 5 minutes).

        Args:
            heartbeat: HeartbeatInfo to check

        Returns:
            True if stale, False if fresh
        """
        try:
            last_beat = datetime.fromisoformat(heartbeat.lastBeatAt.replace("Z", "+00:00"))
            now = datetime.utcnow().replace(tzinfo=last_beat.tzinfo)
            age = now - last_beat
            return age > HEARTBEAT_TIMEOUT
        except (ValueError, TypeError) as e:
            logger.error(f"Error parsing heartbeat time: {e}")
            return True  # Assume stale if we can't parse

    def write_lock(self, lock_info: LockInfo) -> None:
        """Write lock file atomically.

        Args:
            lock_info: LockInfo to write
        """
        self.ensure_directories()
        temp_path = self.lock_path.with_suffix(".lock.tmp")

        with open(temp_path, "w") as f:
            json.dump(lock_info.to_dict(), f, indent=2)
            f.flush()
            os.fsync(f.fileno())

        temp_path.replace(self.lock_path)

    def write_heartbeat(self, heartbeat_info: HeartbeatInfo) -> None:
        """Write heartbeat file.

        Args:
            heartbeat_info: HeartbeatInfo to write
        """
        self.ensure_directories()
        temp_path = self.heartbeat_path.with_suffix(".heartbeat.tmp")

        with open(temp_path, "w") as f:
            json.dump(heartbeat_info.to_dict(), f, indent=2)
            f.flush()
            os.fsync(f.fileno())

        temp_path.replace(self.heartbeat_path)

    def acquire_lock(
        self, force_takeover: bool = False
    ) -> tuple[bool, Optional[str]]:
        """Attempt to acquire controller lock.

        Args:
            force_takeover: If True, acquire lock even if held by alive process

        Returns:
            Tuple of (success, reason_string)
            - success: True if lock acquired, False otherwise
            - reason: "ACQUIRED", "LOCK_DENIED", or "STALE_TAKEOVER"
        """
        self.ensure_directories()
        self.sessionId = str(uuid.uuid4())

        # Check if lock exists
        existing_lock = self.read_lock_info()
        if existing_lock:
            # Check if PID is alive
            pid_alive = self.check_pid_alive(existing_lock.pid)

            if not pid_alive:
                # Stale lock - PID is dead
                logger.info(
                    f"Lock held by dead PID {existing_lock.pid}, taking over"
                )
                self._do_acquire()
                return True, "STALE_TAKEOVER_PID_DEAD"

            # PID is alive, check heartbeat
            heartbeat = self.read_heartbeat_info()
            if not heartbeat:
                # No heartbeat file - might be old version
                if not force_takeover:
                    logger.warning(
                        f"Lock held by alive PID {existing_lock.pid}, no heartbeat found"
                    )
                    return False, "LOCK_DENIED"
                else:
                    logger.info("Force takeover: no heartbeat file")
                    self._do_acquire()
                    return True, "STALE_TAKEOVER"

            if heartbeat.sessionId != existing_lock.sessionId:
                # Inconsistent state - heartbeat doesn't match lock
                if not force_takeover:
                    logger.warning("Inconsistent lock/heartbeat state")
                    return False, "LOCK_DENIED_INCONSISTENT"
                else:
                    logger.info("Force takeover: inconsistent state")
                    self._do_acquire()
                    return True, "STALE_TAKEOVER"

            # Check if heartbeat is stale
            if self.is_heartbeat_stale(heartbeat):
                if not force_takeover:
                    logger.warning(
                        f"Lock held by alive PID {existing_lock.pid} but heartbeat is stale"
                    )
                    return False, "LOCK_DENIED_STALE_HEARTBEAT"
                else:
                    logger.info("Force takeover: stale heartbeat")
                    self._do_acquire()
                    return True, "STALE_TAKEOVER_HEARTBEAT_TIMEOUT"

            # Lock is active and fresh
            if not force_takeover:
                logger.info(f"Lock held by active PID {existing_lock.pid}")
                return False, "LOCK_DENIED"
            else:
                logger.info(f"Force takeover of active lock held by PID {existing_lock.pid}")
                self._do_acquire()
                return True, "FORCE_TAKEOVER"

        # No lock exists, acquire it
        self._do_acquire()
        return True, "ACQUIRED"

    def _do_acquire(self) -> None:
        """Actually acquire the lock (internal method)."""
        lock_info = LockInfo(
            pid=os.getpid(),
            startTime=datetime.utcnow().isoformat() + "Z",
            sessionId=self.sessionId,
        )
        self.write_lock(lock_info)

        # Write initial heartbeat
        heartbeat_info = HeartbeatInfo(
            sessionId=self.sessionId,
            lastBeatAt=datetime.utcnow().isoformat() + "Z",
        )
        self.write_heartbeat(heartbeat_info)

        # Register cleanup on exit
        if not self._release_registered:
            atexit.register(self.release_lock)
            self._release_registered = True

        logger.info(f"Lock acquired: PID {lock_info.pid}, Session {self.sessionId}")

    def update_heartbeat(self) -> None:
        """Update heartbeat file (should be called every 60s during session)."""
        if not self.sessionId:
            logger.warning("No active session, cannot update heartbeat")
            return

        heartbeat_info = HeartbeatInfo(
            sessionId=self.sessionId,
            lastBeatAt=datetime.utcnow().isoformat() + "Z",
        )
        self.write_heartbeat(heartbeat_info)
        logger.debug("Heartbeat updated")

    def release_lock(self) -> None:
        """Release the controller lock.

        This is called automatically on exit via atexit.
        """
        if not self.sessionId:
            return  # No lock to release

        try:
            # Only delete if we own the lock
            existing_lock = self.read_lock_info()
            if existing_lock and existing_lock.sessionId == self.sessionId:
                self.lock_path.unlink(missing_ok=True)
                logger.info("Lock file deleted")

            # Only delete heartbeat if it's ours
            if self.heartbeat_path.exists():
                existing_heartbeat = self.read_heartbeat_info()
                if existing_heartbeat and existing_heartbeat.sessionId == self.sessionId:
                    self.heartbeat_path.unlink(missing_ok=True)
                    logger.info("Heartbeat file deleted")

        except Exception as e:
            logger.error(f"Error releasing lock: {e}")
        finally:
            self.sessionId = None
            self._heartbeat_active = False

    def is_controller(self) -> bool:
        """Check if this process is the controller.

        Returns:
            True if this process holds the lock, False otherwise
        """
        if not self.sessionId:
            return False

        existing_lock = self.read_lock_info()
        return existing_lock is not None and existing_lock.sessionId == self.sessionId
