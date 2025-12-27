"""
Integration tests for Harness Commander.

These tests cover end-to-end scenarios including:
- Concurrent session management
- Crash recovery
- Reconciliation
- State safety
"""

import unittest
import tempfile
import json
import os
import time
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

# Import Commander modules
from state import (
    StateManager,
    State,
    Project,
    Run,
    COMMANDER_HOME,
    STATE_FILE,
    STATE_FILE_TMP,
)
from locking import LockManager, HEARTBEAT_FILE, LOCK_FILE, HEARTBEAT_TIMEOUT
from reconcile import Reconciler, WorktreeInfo, HarnessRunInfo
from events import EventLogger


class TestConcurrentSessions(unittest.TestCase):
    """Test concurrent session acquisition and controller/observer mode."""

    def setUp(self):
        """Set up test environment with temp directories."""
        self.test_dir = tempfile.mkdtemp()
        self.state_file = Path(self.test_dir) / "state.json"
        self.state_tmp = Path(self.test_dir) / "state.json.tmp"
        self.locks_dir = Path(self.test_dir) / "locks"
        self.locks_dir.mkdir()

        # Patch module-level paths
        self.state_patcher = patch("state.STATE_FILE", self.state_file)
        self.state_tmp_patcher = patch("state.STATE_FILE_TMP", self.state_tmp)
        self.commander_home_patcher = patch("state.COMMANDER_HOME", Path(self.test_dir))
        self.locks_dir_patcher = patch("locking.LOCKS_DIR", self.locks_dir)
        self.lock_file_patcher = patch("locking.LOCK_FILE", self.locks_dir / "commander.lock")
        self.heartbeat_file_patcher = patch(
            "locking.HEARTBEAT_FILE", self.locks_dir / "commander.heartbeat"
        )

        self.state_patcher.start()
        self.state_tmp_patcher.start()
        self.commander_home_patcher.start()
        self.locks_dir_patcher.start()
        self.lock_file_patcher.start()
        self.heartbeat_file_patcher.start()

    def tearDown(self):
        """Clean up test environment."""
        patchers = [
            self.state_patcher,
            self.state_tmp_patcher,
            self.commander_home_patcher,
            self.locks_dir_patcher,
            self.lock_file_patcher,
            self.heartbeat_file_patcher,
        ]
        for patcher in patchers:
            patcher.stop()

        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)

    def test_controller_acquires_lock_successfully(self):
        """Test that first session successfully acquires controller lock."""
        lock_mgr = LockManager()
        success, reason = lock_mgr.acquire_lock()

        self.assertTrue(success)
        self.assertEqual(reason, "ACQUIRED")
        self.assertIsNotNone(lock_mgr.sessionId)
        self.assertTrue(lock_mgr.is_controller())

        # Clean up
        lock_mgr.release_lock()

    def test_second_session_observer_mode(self):
        """Test that second session is denied lock (observer mode)."""
        # First session acquires lock
        controller = LockManager()
        success1, reason1 = controller.acquire_lock()
        self.assertTrue(success1)

        # Second session tries to acquire
        observer = LockManager()
        success2, reason2 = observer.acquire_lock()

        self.assertFalse(success2)
        self.assertEqual(reason2, "LOCK_DENIED")
        self.assertFalse(observer.is_controller())
        self.assertTrue(controller.is_controller())

        # Clean up
        controller.release_lock()

    def test_controller_can_reacquire_own_lock(self):
        """Test that controller can check its lock status."""
        lock_mgr = LockManager()
        lock_mgr.acquire_lock()

        # Should be controller
        self.assertTrue(lock_mgr.is_controller())

        # Try to acquire again - should succeed with ACQUIRED
        success, reason = lock_mgr.acquire_lock(force_takeover=True)
        self.assertTrue(success)

        lock_mgr.release_lock()


class TestPIDCrashRecovery(unittest.TestCase):
    """Test crash recovery when process dies."""

    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.state_file = Path(self.test_dir) / "state.json"
        self.state_tmp = Path(self.test_dir) / "state.json.tmp"
        self.locks_dir = Path(self.test_dir) / "locks"
        self.locks_dir.mkdir()

        self.state_patcher = patch("state.STATE_FILE", self.state_file)
        self.state_tmp_patcher = patch("state.STATE_FILE_TMP", self.state_tmp)
        self.commander_home_patcher = patch("state.COMMANDER_HOME", Path(self.test_dir))
        self.locks_dir_patcher = patch("locking.LOCKS_DIR", self.locks_dir)
        self.lock_file_patcher = patch("locking.LOCK_FILE", self.locks_dir / "commander.lock")
        self.heartbeat_file_patcher = patch(
            "locking.HEARTBEAT_FILE", self.locks_dir / "commander.heartbeat"
        )

        self.state_patcher.start()
        self.state_tmp_patcher.start()
        self.commander_home_patcher.start()
        self.locks_dir_patcher.start()
        self.lock_file_patcher.start()
        self.heartbeat_file_patcher.start()

    def tearDown(self):
        """Clean up test environment."""
        patchers = [
            self.state_patcher,
            self.state_tmp_patcher,
            self.commander_home_patcher,
            self.locks_dir_patcher,
            self.lock_file_patcher,
            self.heartbeat_file_patcher,
        ]
        for patcher in patchers:
            patcher.stop()

        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)

    def test_stale_pid_takeover_on_dead_process(self):
        """Test takeover when lock holder PID is dead."""
        # First session acquires lock
        controller = LockManager()
        controller.acquire_lock()

        # Simulate crash by manually writing a dead PID
        dead_pid = 99999  # Non-existent PID
        lock_info = {
            "pid": dead_pid,
            "startTime": datetime.utcnow().isoformat() + "Z",
            "sessionId": controller.sessionId,
        }
        with open(self.locks_dir / "commander.lock", "w") as f:
            json.dump(lock_info, f)

        # New session should detect dead PID and take over
        new_session = LockManager()
        success, reason = new_session.acquire_lock()

        self.assertTrue(success)
        self.assertEqual(reason, "STALE_TAKEOVER_PID_DEAD")
        self.assertTrue(new_session.is_controller())
        self.assertNotEqual(new_session.sessionId, controller.sessionId)

        # Clean up
        new_session.release_lock()

    def test_lock_file_persistence_across_sessions(self):
        """Test that lock file persists and can be read by new sessions."""
        # First session creates lock
        session1 = LockManager()
        session1.acquire_lock()
        original_session_id = session1.sessionId

        # Verify lock file exists
        self.assertTrue((self.locks_dir / "commander.lock").exists())

        # Release lock
        session1.release_lock()

        # New session should be able to acquire
        session2 = LockManager()
        success, reason = session2.acquire_lock()

        self.assertTrue(success)
        self.assertEqual(reason, "ACQUIRED")
        self.assertNotEqual(session2.sessionId, original_session_id)

        session2.release_lock()


class TestHeartbeatTimeout(unittest.TestCase):
    """Test hung process recovery via heartbeat timeout."""

    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.state_file = Path(self.test_dir) / "state.json"
        self.state_tmp = Path(self.test_dir) / "state.json.tmp"
        self.locks_dir = Path(self.test_dir) / "locks"
        self.locks_dir.mkdir()

        self.state_patcher = patch("state.STATE_FILE", self.state_file)
        self.state_tmp_patcher = patch("state.STATE_FILE_TMP", self.state_tmp)
        self.commander_home_patcher = patch("state.COMMANDER_HOME", Path(self.test_dir))
        self.locks_dir_patcher = patch("locking.LOCKS_DIR", self.locks_dir)
        self.lock_file_patcher = patch("locking.LOCK_FILE", self.locks_dir / "commander.lock")
        self.heartbeat_file_patcher = patch(
            "locking.HEARTBEAT_FILE", self.locks_dir / "commander.heartbeat"
        )

        self.state_patcher.start()
        self.state_tmp_patcher.start()
        self.commander_home_patcher.start()
        self.locks_dir_patcher.start()
        self.lock_file_patcher.start()
        self.heartbeat_file_patcher.start()

    def tearDown(self):
        """Clean up test environment."""
        patchers = [
            self.state_patcher,
            self.state_tmp_patcher,
            self.commander_home_patcher,
            self.locks_dir_patcher,
            self.lock_file_patcher,
            self.heartbeat_file_patcher,
        ]
        for patcher in patchers:
            patcher.stop()

        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)

    def test_stale_heartbeat_detection(self):
        """Test detection of stale heartbeat."""
        lock_mgr = LockManager()

        # Create a stale heartbeat (older than 5 minutes)
        stale_time = (datetime.utcnow() - HEARTBEAT_TIMEOUT - timedelta(minutes=1)).isoformat() + "Z"
        heartbeat_info = {
            "sessionId": "test-session-id",
            "lastBeatAt": stale_time,
        }
        with open(self.locks_dir / "commander.heartbeat", "w") as f:
            json.dump(heartbeat_info, f)

        # Create matching lock with alive PID
        lock_info = {
            "pid": os.getpid(),
            "startTime": datetime.utcnow().isoformat() + "Z",
            "sessionId": "test-session-id",
        }
        with open(self.locks_dir / "commander.lock", "w") as f:
            json.dump(lock_info, f)

        # Should detect stale heartbeat
        self.assertTrue(lock_mgr.is_heartbeat_stale(lock_mgr.read_heartbeat_info()))

    def test_fresh_heartbeat_not_stale(self):
        """Test that fresh heartbeat is not detected as stale."""
        lock_mgr = LockManager()

        # Create a fresh heartbeat
        fresh_time = datetime.utcnow().isoformat() + "Z"
        heartbeat_info = {
            "sessionId": "test-session-id",
            "lastBeatAt": fresh_time,
        }
        with open(self.locks_dir / "commander.heartbeat", "w") as f:
            json.dump(heartbeat_info, f)

        # Should not detect as stale
        heartbeat = lock_mgr.read_heartbeat_info()
        self.assertFalse(lock_mgr.is_heartbeat_stale(heartbeat))

    def test_force_takeover_on_stale_heartbeat(self):
        """Test force takeover when heartbeat is stale."""
        # First session
        session1 = LockManager()
        session1.acquire_lock()

        # Manually make heartbeat stale
        stale_time = (datetime.utcnow() - HEARTBEAT_TIMEOUT - timedelta(minutes=1)).isoformat() + "Z"
        stale_heartbeat = {
            "sessionId": session1.sessionId,
            "lastBeatAt": stale_time,
        }
        with open(self.locks_dir / "commander.heartbeat", "w") as f:
            json.dump(stale_heartbeat, f)

        # New session should be denied without force
        session2 = LockManager()
        success, reason = session2.acquire_lock()
        self.assertFalse(success)
        self.assertEqual(reason, "LOCK_DENIED_STALE_HEARTBEAT")

        # With force_takeover, should succeed
        success, reason = session2.acquire_lock(force_takeover=True)
        self.assertTrue(success)
        self.assertEqual(reason, "STALE_TAKEOVER_HEARTBEAT_TIMEOUT")

        session2.release_lock()


class TestReconcileDrift(unittest.TestCase):
    """Test reconciliation drift scenarios."""

    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.runs_dir = Path(self.test_dir) / "runs"
        self.runs_dir.mkdir()

        self.state_file = Path(self.test_dir) / "state.json"
        self.state_tmp = Path(self.test_dir) / "state.json.tmp"

        self.state_patcher = patch("state.STATE_FILE", self.state_file)
        self.state_tmp_patcher = patch("state.STATE_FILE_TMP", self.state_tmp)
        self.commander_home_patcher = patch("state.COMMANDER_HOME", Path(self.test_dir))

        self.state_patcher.start()
        self.state_tmp_patcher.start()
        self.commander_home_patcher.start()

    def tearDown(self):
        """Clean up test environment."""
        self.state_patcher.stop()
        self.state_tmp_patcher.stop()
        self.commander_home_patcher.stop()

        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)

    def test_reconcile_detects_missing_run(self):
        """Test that reconcile detects runs in state but missing from filesystem."""
        # Create state with a run
        state_mgr = StateManager()
        state = state_mgr.load_state()

        test_run = Run(
            id="test-run-id",
            projectId="test-project-id",
            runName="HARNESS-TEST",
            state="running",
            worktreePath=str(self.runs_dir / "HARNESS-TEST"),
        )
        state.runs.append(test_run)
        state_mgr.save_state()

        # Run reconciliation (run doesn't exist in filesystem)
        reconciler = Reconciler(harness_path=Path(self.test_dir))
        result = reconciler.reconcile(state_mgr)

        self.assertTrue(result.drift_detected)
        self.assertEqual(result.runs_parked, 1)

        # Verify run was parked
        updated_state = state_mgr.load_state()
        parked_run = next(r for r in updated_state.runs if r.runName == "HARNESS-TEST")
        self.assertEqual(parked_run.state, "missing")

    def test_reconcile_detects_new_run(self):
        """Test that reconcile detects runs in filesystem but missing from state."""
        # Create a run directory with metadata
        run_dir = self.runs_dir / "HARNESS-NEW"
        run_dir.mkdir()

        metadata = {
            "branch": "run/HARNESS-NEW",
            "status": "running",
        }
        with open(run_dir / ".run", "w") as f:
            json.dump(metadata, f)

        # Start with empty state
        state_mgr = StateManager()
        state_mgr.load_state()

        # Run reconciliation
        reconciler = Reconciler(harness_path=Path(self.test_dir))
        result = reconciler.reconcile(state_mgr)

        self.assertTrue(result.drift_detected)
        self.assertGreater(result.runs_added, 0)


class TestDirtyTreePolicy(unittest.TestCase):
    """Test dirty tree policy enforcement."""

    def setUp(self):
        """Set up test environment with a git repo."""
        self.test_dir = tempfile.mkdtemp()
        self.repo_path = Path(self.test_dir)

        # Initialize git repo
        import subprocess
        subprocess.run(["git", "init"], cwd=self.repo_path, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=self.repo_path,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=self.repo_path,
            capture_output=True,
        )

        # Create initial commit
        test_file = self.repo_path / "test.txt"
        test_file.write_text("initial content")
        subprocess.run(["git", "add", "."], cwd=self.repo_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=self.repo_path,
            capture_output=True,
        )

    def tearDown(self):
        """Clean up test environment."""
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)

    def test_clean_tree_passes_check(self):
        """Test that clean working tree passes check."""
        reconciler = Reconciler(harness_path=self.repo_path)
        is_clean, msg = reconciler.check_dirty_tree_policy(self.repo_path)

        self.assertTrue(is_clean)
        self.assertEqual(msg, "Working tree is clean")

    def test_dirty_tree_fails_check(self):
        """Test that dirty working tree fails check."""
        # Make repo dirty
        test_file = self.repo_path / "test.txt"
        test_file.write_text("modified content")

        reconciler = Reconciler(harness_path=self.repo_path)
        is_clean, msg = reconciler.check_dirty_tree_policy(self.repo_path)

        self.assertFalse(is_clean)
        self.assertIn("dirty", msg.lower())

    def test_dirty_tree_refuses_mutations(self):
        """Test that dirty tree refuses mutations when allow_mutations=False."""
        # Make repo dirty
        test_file = self.repo_path / "test.txt"
        test_file.write_text("modified content")

        reconciler = Reconciler(harness_path=self.repo_path)
        is_clean, msg = reconciler.check_dirty_tree_policy(
            self.repo_path, allow_mutations=False
        )

        self.assertFalse(is_clean)
        self.assertIn("refused", msg.lower())


class TestWorktreePathSafety(unittest.TestCase):
    """Test worktree path validation."""

    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.runs_dir = Path(self.test_dir) / "runs"
        self.runs_dir.mkdir(parents=True)

        self.runs_dir_patcher = patch("reconcile.Reconciler.runs_dir", self.runs_dir)
        self.runs_dir_patcher.start()

    def tearDown(self):
        """Clean up test environment."""
        self.runs_dir_patcher.stop()

        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)

    def test_path_under_runs_is_safe(self):
        """Test that path under runs dir is considered safe."""
        worktree_path = self.runs_dir / "HARNESS-TEST"
        worktree_path.mkdir()

        # Create marker file
        marker = worktree_path / ".harness-worktree"
        marker.write_text("")

        reconciler = Reconciler(harness_path=Path(self.test_dir))
        is_safe, msg = reconciler.validate_worktree_path(worktree_path, [])

        self.assertTrue(is_safe)
        self.assertEqual(msg, "Path is safe")

    def test_missing_marker_file_is_unsafe(self):
        """Test that path without marker file is unsafe."""
        worktree_path = self.runs_dir / "HARNESS-TEST"
        worktree_path.mkdir()

        # No marker file created

        reconciler = Reconciler(harness_path=Path(self.test_dir))
        is_safe, msg = reconciler.validate_worktree_path(worktree_path, [])

        self.assertFalse(is_safe)
        self.assertIn("marker", msg.lower())

    def test_path_outside_allowed_areas_is_unsafe(self):
        """Test that path outside registered projects/runs is unsafe."""
        # Create path outside runs dir
        outside_path = Path(self.test_dir) / "some-other-dir"
        outside_path.mkdir()

        # Create marker file
        marker = outside_path / ".harness-worktree"
        marker.write_text("")

        reconciler = Reconciler(harness_path=Path(self.test_dir))
        is_safe, msg = reconciler.validate_worktree_path(outside_path, [])

        self.assertFalse(is_safe)
        self.assertIn("refusing", msg.lower())


class TestStateAtomicWrites(unittest.TestCase):
    """Test state atomic writes and crash recovery."""

    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.state_file = Path(self.test_dir) / "state.json"
        self.state_tmp = Path(self.test_dir) / "state.json.tmp"

        self.state_patcher = patch("state.STATE_FILE", self.state_file)
        self.state_tmp_patcher = patch("state.STATE_FILE_TMP", self.state_tmp)
        self.commander_home_patcher = patch("state.COMMANDER_HOME", Path(self.test_dir))

        self.state_patcher.start()
        self.state_tmp_patcher.start()
        self.commander_home_patcher.start()

    def tearDown(self):
        """Clean up test environment."""
        self.state_patcher.stop()
        self.state_tmp_patcher.stop()
        self.commander_home_patcher.stop()

        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)

    def test_atomic_write_creates_real_file(self):
        """Test that atomic write creates the actual state file."""
        state_mgr = StateManager()
        state = state_mgr.load_state()

        # Add some data
        project = Project(
            id="test-project",
            name="Test Project",
            repoPath="/tmp/test",
            status="active",
            lastTouchedAt=datetime.utcnow().isoformat() + "Z",
        )
        state.projects.append(project)
        state_mgr.save_state()

        # Verify real file exists
        self.assertTrue(self.state_file.exists())
        self.assertFalse(self.state_tmp.exists())

    def test_crash_during_write_creates_tmp_file(self):
        """Test that crash during write leaves .tmp file."""
        state_mgr = StateManager()

        # Simulate crash by writing tmp file directly
        test_data = {"test": "data"}
        with open(self.state_tmp, "w") as f:
            json.dump(test_data, f)

        # Load state should recover from crash
        state_mgr.recover_from_crash()
        self.assertFalse(self.state_tmp.exists())

    def test_state_survives_crash(self):
        """Test that state is preserved across simulated crash."""
        # Write initial state
        state_mgr = StateManager()
        state = state_mgr.load_state()

        project = Project(
            id="test-project",
            name="Test Project",
            repoPath="/tmp/test",
            status="active",
            lastTouchedAt=datetime.utcnow().isoformat() + "Z",
        )
        state.projects.append(project)
        state_mgr.save_state()

        # Read it back (simulating new session after crash)
        new_state_mgr = StateManager()
        loaded_state = new_state_mgr.load_state()

        self.assertEqual(len(loaded_state.projects), 1)
        self.assertEqual(loaded_state.projects[0].name, "Test Project")


class TestStateCorruptionRepair(unittest.TestCase):
    """Test state file corruption and doctor repair."""

    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.state_file = Path(self.test_dir) / "state.json"
        self.state_tmp = Path(self.test_dir) / "state.json.tmp"

        self.state_patcher = patch("state.STATE_FILE", self.state_file)
        self.state_tmp_patcher = patch("state.STATE_FILE_TMP", self.state_tmp)
        self.commander_home_patcher = patch("state.COMMANDER_HOME", Path(self.test_dir))

        self.state_patcher.start()
        self.state_tmp_patcher.start()
        self.commander_home_patcher.start()

    def tearDown(self):
        """Clean up test environment."""
        self.state_patcher.stop()
        self.state_tmp_patcher.stop()
        self.commander_home_patcher.stop()

        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)

    def test_corrupt_state_file_raises_error(self):
        """Test that corrupt state file raises appropriate error."""
        # Write invalid JSON
        with open(self.state_file, "w") as f:
            f.write("{ invalid json }")

        state_mgr = StateManager()
        with self.assertRaises(ValueError) as ctx:
            state_mgr.load_state()

        self.assertIn("corrupt", str(ctx.exception).lower())

    def test_missing_state_file_creates_new_state(self):
        """Test that missing state file creates empty state."""
        # Don't create state file
        state_mgr = StateManager()
        state = state_mgr.load_state()

        self.assertIsInstance(state, State)
        self.assertEqual(len(state.projects), 0)
        self.assertEqual(len(state.runs), 0)

    def test_valid_state_loads_successfully(self):
        """Test that valid state file loads correctly."""
        # Write valid state
        test_state = {
            "focusProjectId": None,
            "projects": [
                {
                    "id": "test-id",
                    "name": "Test Project",
                    "repoPath": "/tmp/test",
                    "status": "active",
                    "lastTouchedAt": "2025-01-01T00:00:00Z",
                }
            ],
            "runs": [],
            "tasks": [],
            "inbox": [],
        }
        with open(self.state_file, "w") as f:
            json.dump(test_state, f)

        state_mgr = StateManager()
        state = state_mgr.load_state()

        self.assertEqual(len(state.projects), 1)
        self.assertEqual(state.projects[0].name, "Test Project")


if __name__ == "__main__":
    unittest.main()
