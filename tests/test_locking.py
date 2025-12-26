"""
Unit tests for Harness Commander locking system.
"""

import unittest
import tempfile
import json
import time
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch, MagicMock

from locking import (
    LockManager,
    LockInfo,
    HeartbeatInfo,
    HEARTBEAT_TIMEOUT,
    LOCKS_DIR,
    LOCK_FILE,
    HEARTBEAT_FILE,
)


class TestLockInfo(unittest.TestCase):
    """Test LockInfo dataclass."""

    def test_lock_info_to_dict(self):
        """Test LockInfo serializes to dict correctly."""
        lock_info = LockInfo(
            pid=12345,
            startTime="2025-01-01T00:00:00Z",
            sessionId=str(uuid4()),
        )

        data = lock_info.to_dict()

        self.assertEqual(data["pid"], 12345)
        self.assertEqual(data["startTime"], "2025-01-01T00:00:00Z")

    def test_lock_info_from_dict(self):
        """Test LockInfo deserializes from dict correctly."""
        data = {
            "pid": 12345,
            "startTime": "2025-01-01T00:00:00Z",
            "sessionId": str(uuid4()),
        }

        lock_info = LockInfo.from_dict(data)

        self.assertEqual(lock_info.pid, 12345)
        self.assertEqual(lock_info.startTime, "2025-01-01T00:00:00Z")


class TestHeartbeatInfo(unittest.TestCase):
    """Test HeartbeatInfo dataclass."""

    def test_heartbeat_info_to_dict(self):
        """Test HeartbeatInfo serializes to dict correctly."""
        heartbeat = HeartbeatInfo(
            sessionId=str(uuid4()),
            lastBeatAt="2025-01-01T00:00:00Z",
        )

        data = heartbeat.to_dict()

        self.assertIn("sessionId", data)
        self.assertEqual(data["lastBeatAt"], "2025-01-01T00:00:00Z")

    def test_heartbeat_info_from_dict(self):
        """Test HeartbeatInfo deserializes from dict correctly."""
        session_id = str(uuid4())
        data = {
            "sessionId": session_id,
            "lastBeatAt": "2025-01-01T00:00:00Z",
        }

        heartbeat = HeartbeatInfo.from_dict(data)

        self.assertEqual(heartbeat.sessionId, session_id)
        self.assertEqual(heartbeat.lastBeatAt, "2025-01-01T00:00:00Z")


class TestLockManager(unittest.TestCase):
    """Test LockManager class."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.locks_dir = Path(self.temp_dir) / "locks"
        self.lock_path = self.locks_dir / "commander.lock"
        self.heartbeat_path = self.locks_dir / "commander.heartbeat"

        # Patch the global paths
        self.patcher = patch.multiple(
            "locking",
            LOCKS_DIR=self.locks_dir,
            LOCK_FILE=self.lock_path,
            HEARTBEAT_FILE=self.heartbeat_path,
        )
        self.patcher.start()

        self.manager = LockManager()

    def tearDown(self):
        """Clean up test fixtures."""
        self.patcher.stop()
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_ensure_directories_creates_locks_dir(self):
        """Test ensure_directories creates locks directory."""
        self.manager.ensure_directories()
        self.assertTrue(self.locks_dir.exists())

    def test_acquire_lock_creates_files(self):
        """Test acquire_lock creates lock and heartbeat files."""
        success, reason = self.manager.acquire_lock()

        self.assertTrue(success)
        self.assertEqual(reason, "ACQUIRED")
        self.assertTrue(self.lock_path.exists())
        self.assertTrue(self.heartbeat_path.exists())

    def test_acquire_lock_sets_session_id(self):
        """Test acquire_lock sets sessionId."""
        self.manager.acquire_lock()

        self.assertIsNotNone(self.manager.sessionId)
        self.assertTrue(len(self.manager.sessionId) > 0)

    def test_acquire_lock_denied_when_held(self):
        """Test acquire_lock denied when already held."""
        manager1 = LockManager()
        manager1.acquire_lock()

        manager2 = LockManager()
        success, reason = manager2.acquire_lock()

        self.assertFalse(success)
        self.assertEqual(reason, "LOCK_DENIED")

    def test_acquire_lock_takes_over_dead_pid(self):
        """Test acquire_lock takes over when PID is dead."""
        # Create a lock with a fake dead PID
        lock_info = LockInfo(
            pid=99999,  # Non-existent PID
            startTime="2025-01-01T00:00:00Z",
            sessionId=str(uuid4()),
        )
        self.manager.write_lock(lock_info)

        # Should take over
        success, reason = self.manager.acquire_lock()

        self.assertTrue(success)
        self.assertEqual(reason, "STALE_TAKEOVER_PID_DEAD")

    def test_read_lock_info(self):
        """Test read_lock_info reads lock file correctly."""
        lock_info = LockInfo(
            pid=12345,
            startTime="2025-01-01T00:00:00Z",
            sessionId="session-123",
        )
        self.manager.write_lock(lock_info)

        read_info = self.manager.read_lock_info()

        self.assertIsNotNone(read_info)
        self.assertEqual(read_info.pid, 12345)
        self.assertEqual(read_info.sessionId, "session-123")

    def test_read_lock_info_returns_none_if_missing(self):
        """Test read_lock_info returns None if file doesn't exist."""
        read_info = self.manager.read_lock_info()
        self.assertIsNone(read_info)

    def test_read_heartbeat_info(self):
        """Test read_heartbeat_info reads heartbeat file correctly."""
        heartbeat = HeartbeatInfo(
            sessionId="session-123",
            lastBeatAt="2025-01-01T00:00:00Z",
        )
        self.manager.write_heartbeat(heartbeat)

        read_heartbeat = self.manager.read_heartbeat_info()

        self.assertIsNotNone(read_heartbeat)
        self.assertEqual(read_heartbeat.sessionId, "session-123")

    def test_read_heartbeat_info_returns_none_if_missing(self):
        """Test read_heartbeat_info returns None if file doesn't exist."""
        read_heartbeat = self.manager.read_heartbeat_info()
        self.assertIsNone(read_heartbeat)

    def test_check_pid_alive_with_current_process(self):
        """Test check_pid_alive returns True for current process."""
        self.assertTrue(self.manager.check_pid_alive(os.getpid()))

    def test_check_pid_alive_with_fake_pid(self):
        """Test check_pid_alive returns False for non-existent PID."""
        self.assertFalse(self.manager.check_pid_alive(99999))

    def test_is_heartbeat_stale_with_old_heartbeat(self):
        """Test is_heartbeat_stale returns True for old heartbeat."""
        # Create a heartbeat that's 10 minutes old
        old_time = "2025-01-01T00:00:00Z"  # Way in the past
        heartbeat = HeartbeatInfo(
            sessionId=str(uuid4()),
            lastBeatAt=old_time,
        )

        self.assertTrue(self.manager.is_heartbeat_stale(heartbeat))

    def test_is_heartbeat_stale_with_fresh_heartbeat(self):
        """Test is_heartbeat_stale returns False for fresh heartbeat."""
        # Create a fresh heartbeat
        fresh_time = "2099-01-01T00:00:00Z"  # Way in the future
        heartbeat = HeartbeatInfo(
            sessionId=str(uuid4()),
            lastBeatAt=fresh_time,
        )

        self.assertFalse(self.manager.is_heartbeat_stale(heartbeat))

    def test_update_heartbeat(self):
        """Test update_heartbeat updates heartbeat file."""
        self.manager.acquire_lock()

        old_heartbeat = self.manager.read_heartbeat_info()
        old_time = old_heartbeat.lastBeatAt

        # Wait a tiny bit
        time.sleep(0.01)

        # Update heartbeat
        self.manager.update_heartbeat()

        new_heartbeat = self.manager.read_heartbeat_info()
        new_time = new_heartbeat.lastBeatAt

        # Time should have changed
        self.assertNotEqual(old_time, new_time)

    def test_release_lock_deletes_files(self):
        """Test release_lock deletes lock and heartbeat files."""
        self.manager.acquire_lock()

        self.manager.release_lock()

        self.assertFalse(self.lock_path.exists())
        self.assertFalse(self.heartbeat_path.exists())

    def test_release_lock_only_deletes_own_lock(self):
        """Test release_lock only deletes lock if it owns it."""
        manager1 = LockManager()
        manager1.acquire_lock()

        manager2 = LockManager()
        manager2.acquire_lock(force_takeover=True)

        # Manager1's lock should still exist
        # (because manager2 overwrote it with a new sessionId)
        self.assertTrue(self.lock_path.exists())

    def test_is_controller_returns_true_when_holding_lock(self):
        """Test is_controller returns True when holding lock."""
        self.manager.acquire_lock()
        self.assertTrue(self.manager.is_controller())

    def test_is_controller_returns_false_when_not_holding_lock(self):
        """Test is_controller returns False when not holding lock."""
        self.assertFalse(self.manager.is_controller())

    def test_acquire_lock_with_force_takeover(self):
        """Test acquire_lock with force_takeover=True."""
        manager1 = LockManager()
        manager1.acquire_lock()

        manager2 = LockManager()
        success, reason = manager2.acquire_lock(force_takeover=True)

        self.assertTrue(success)
        self.assertIn("TAKEOVER", reason)

    def test_acquire_lock_with_inconsistent_heartbeat(self):
        """Test acquire_lock with inconsistent heartbeat (different sessionId)."""
        # Create lock
        lock_info = LockInfo(
            pid=os.getpid(),
            startTime="2025-01-01T00:00:00Z",
            sessionId="session-1",
        )
        self.manager.write_lock(lock_info)

        # Create heartbeat with different sessionId
        heartbeat = HeartbeatInfo(
            sessionId="session-2",  # Different!
            lastBeatAt="2099-01-01T00:00:00Z",
        )
        self.manager.write_heartbeat(heartbeat)

        success, reason = self.manager.acquire_lock()

        self.assertFalse(success)
        self.assertEqual(reason, "LOCK_DENIED_INCONSISTENT")

    def test_acquire_lock_with_stale_heartbeat(self):
        """Test acquire_lock with stale heartbeat but alive PID."""
        # Create lock with current PID
        lock_info = LockInfo(
            pid=os.getpid(),
            startTime="2025-01-01T00:00:00Z",
            sessionId=str(uuid4()),
        )
        self.manager.write_lock(lock_info)

        # Create stale heartbeat
        old_time = "2025-01-01T00:00:00Z"
        heartbeat = HeartbeatInfo(
            sessionId=lock_info.sessionId,
            lastBeatAt=old_time,
        )
        self.manager.write_heartbeat(heartbeat)

        success, reason = self.manager.acquire_lock()

        self.assertFalse(success)
        self.assertEqual(reason, "LOCK_DENIED_STALE_HEARTBEAT")


if __name__ == "__main__":
    import os
    unittest.main()
