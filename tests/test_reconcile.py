"""
Unit tests for Harness Commander reconciliation engine.
"""

import unittest
import tempfile
import json
import shutil
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch, MagicMock

from reconcile import (
    Reconciler,
    GitStatus,
    WorktreeInfo,
    HarnessRunInfo,
    ReconcileResult,
    cached,
    RECONCILE_CACHE_DURATION,
)


class TestGitStatus(unittest.TestCase):
    """Test GitStatus dataclass."""

    def test_git_status_creation(self):
        """Test GitStatus can be created."""
        status = GitStatus(branch="main", clean=True, files_changed=0)
        self.assertEqual(status.branch, "main")
        self.assertTrue(status.clean)


class TestWorktreeInfo(unittest.TestCase):
    """Test WorktreeInfo dataclass."""

    def test_worktree_info_creation(self):
        """Test WorktreeInfo can be created."""
        info = WorktreeInfo(path="/tmp/test", branch="main", is_bare=False)
        self.assertEqual(info.path, "/tmp/test")
        self.assertFalse(info.is_bare)


class TestHarnessRunInfo(unittest.TestCase):
    """Test HarnessRunInfo dataclass."""

    def test_harness_run_info_creation(self):
        """Test HarnessRunInfo can be created."""
        info = HarnessRunInfo(
            name="test-run", branch="run/test-run", status="active", worktree_path="/tmp"
        )
        self.assertEqual(info.name, "test-run")


class TestReconcileResult(unittest.TestCase):
    """Test ReconcileResult dataclass."""

    def test_reconcile_result_defaults(self):
        """Test ReconcileResult has correct defaults."""
        result = ReconcileResult()
        self.assertEqual(result.projects_added, 0)
        self.assertEqual(result.runs_parked, 0)
        self.assertFalse(result.drift_detected)


class TestCachedDecorator(unittest.TestCase):
    """Test cached decorator."""

    def test_cached_returns_same_result_within_duration(self):
        """Test cached decorator returns cached result."""
        call_count = [0]

        @cached(cache_duration=RECONCILE_CACHE_DURATION)
        def expensive_function(self):
            call_count[0] += 1
            return call_count[0]

        class Dummy:
            pass

        obj = Dummy()

        # First call
        result1 = expensive_function(obj)
        self.assertEqual(result1, 1)

        # Second call (cached)
        result2 = expensive_function(obj)
        self.assertEqual(result2, 1)
        self.assertEqual(call_count[0], 1)  # Only called once


class TestReconciler(unittest.TestCase):
    """Test Reconciler class."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.harness_path = Path(self.temp_dir)
        self.runs_dir = self.harness_path / "runs"
        self.runs_dir.mkdir()

        self.reconciler = Reconciler(harness_path=self.harness_path)

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_init_creates_runs_dir_path(self):
        """Test Reconciler initialization."""
        self.assertEqual(self.reconciler.harness_path, self.harness_path)
        self.assertEqual(self.reconciler.runs_dir, self.runs_dir)

    def test_list_harness_runs_returns_empty_if_no_runs(self):
        """Test list_harness_runs returns empty list if no runs."""
        runs = self.reconciler.list_harness_runs()
        self.assertEqual(len(runs), 0)

    def test_list_harness_runs_discovers_run_with_metadata(self):
        """Test list_harness_runs discovers run with .run file."""
        # Create a run directory with metadata
        run_dir = self.runs_dir / "test-run"
        run_dir.mkdir()

        metadata = {
            "branch": "run/test-run",
            "status": "active",
            "created_at": 1234567890.0,
        }
        with open(run_dir / ".run", "w") as f:
            json.dump(metadata, f)

        runs = self.reconciler.list_harness_runs()

        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0].name, "test-run")
        self.assertEqual(runs[0].branch, "run/test-run")

    def test_list_harness_runs_skips_directory_without_metadata(self):
        """Test list_harness_runs skips directories without .run file."""
        # Create a run directory WITHOUT metadata
        run_dir = self.runs_dir / "incomplete-run"
        run_dir.mkdir()

        runs = self.reconciler.list_harness_runs()

        self.assertEqual(len(runs), 0)

    def test_validate_worktree_path_accepts_path_with_marker(self):
        """Test validate_worktree_path accepts path with .harness-worktree marker."""
        test_path = self.runs_dir / "test-run"
        test_path.mkdir()
        (test_path / ".harness-worktree").touch()

        is_safe, msg = self.reconciler.validate_worktree_path(test_path, [])

        self.assertTrue(is_safe)
        self.assertEqual(msg, "Path is safe")

    def test_validate_worktree_path_rejects_path_without_marker(self):
        """Test validate_worktree_path rejects path without marker."""
        test_path = self.runs_dir / "test-run"
        test_path.mkdir()

        is_safe, msg = self.reconciler.validate_worktree_path(test_path, [])

        self.assertFalse(is_safe)
        self.assertIn("missing .harness-worktree marker", msg)

    def test_validate_worktree_path_rejects_path_outside_allowed_dirs(self):
        """Test validate_worktree_path rejects path outside allowed directories."""
        test_path = Path("/tmp/suspicious-path")
        test_path.mkdir()
        (test_path / ".harness-worktree").touch()

        try:
            is_safe, msg = self.reconciler.validate_worktree_path(test_path, [])

            self.assertFalse(is_safe)
            self.assertIn("not under registered project", msg)
        finally:
            shutil.rmtree(test_path, ignore_errors=True)

    def test_check_dirty_tree_policy_with_clean_tree(self):
        """Test check_dirty_tree_policy returns True for clean tree."""
        # Mock a clean git status
        with patch.object(self.reconciler, "get_git_status") as mock_status:
            mock_status.return_value = GitStatus(
                branch="main", clean=True, files_changed=0
            )

            is_clean, msg = self.reconciler.check_dirty_tree_policy(
                self.harness_path, allow_mutations=True
            )

            self.assertTrue(is_clean)
            self.assertEqual(msg, "Working tree is clean")

    def test_check_dirty_tree_policy_with_dirty_tree(self):
        """Test check_dirty_tree_policy returns False for dirty tree."""
        # Mock a dirty git status
        with patch.object(self.reconciler, "get_git_status") as mock_status:
            mock_status.return_value = GitStatus(
                branch="main", clean=False, files_changed=2
            )

            is_clean, msg = self.reconciler.check_dirty_tree_policy(
                self.harness_path, allow_mutations=True
            )

            self.assertFalse(is_clean)
            self.assertIn("dirty", msg)

    def test_check_dirty_tree_policy_refuses_mutations_when_dirty(self):
        """Test check_dirty_tree_policy refuses mutations when dirty."""
        with patch.object(self.reconciler, "get_git_status") as mock_status:
            mock_status.return_value = GitStatus(
                branch="main", clean=False, files_changed=1
            )

            is_clean, msg = self.reconciler.check_dirty_tree_policy(
                self.harness_path, allow_mutations=False
            )

            self.assertFalse(is_clean)
            self.assertIn("Mutations refused", msg)

    @patch("reconcile.subprocess.run")
    def test_run_git_successful(self, mock_run):
        """Test run_git executes git command successfully."""
        mock_run.return_value = MagicMock(stdout="output", stderr="", returncode=0)

        result = self.reconciler.run_git(["status"])

        self.assertEqual(result, "output")

    @patch("reconcile.subprocess.run")
    def test_run_git_fails_on_error(self, mock_run):
        """Test run_git raises RuntimeError on failure."""
        mock_run.side_effect = subprocess.CalledProcessError(
            1, "git", stderr="error"
        )

        with self.assertRaises(RuntimeError):
            self.reconciler.run_git(["status"])

    @patch("reconcile.subprocess.run")
    def test_get_git_status(self, mock_run):
        """Test get_git_status parses git output correctly."""
        # Mock branch command
        mock_run.side_effect = [
            MagicMock(stdout="main", stderr=""),  # branch
            MagicMock(stdout="", stderr=""),  # status (clean)
        ]

        status = self.reconciler.get_git_status(self.harness_path)

        self.assertEqual(status.branch, "main")
        self.assertTrue(status.clean)
        self.assertEqual(status.files_changed, 0)

    @patch("reconcile.subprocess.run")
    def test_list_worktrees(self, mock_run):
        """Test list_worktrees parses git worktree output."""
        output = """worktree /path/to/main
branch refs/heads/main

worktree /path/to/worktree
branch refs/heads/feature
"""
        mock_run.return_value = MagicMock(stdout=output, stderr="")

        worktrees = self.reconciler.list_worktrees()

        self.assertEqual(len(worktrees), 2)
        self.assertEqual(worktrees[0].branch, "main")
        self.assertEqual(worktrees[1].branch, "feature")


class TestReconcileIntegration(unittest.TestCase):
    """Integration tests for reconciliation."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.harness_path = Path(self.temp_dir)
        self.runs_dir = self.harness_path / "runs"
        self.runs_dir.mkdir()

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_reconcile_parks_missing_runs(self):
        """Test reconcile parks runs missing from filesystem."""
        from state import StateManager, Run, STATE_FILE

        # Create state with a run
        state_path = Path(self.temp_dir) / "state.json"
        state_mgr = StateManager(state_path=state_path)

        state = StateManager.State(
            runs=[
                Run(
                    id=str(uuid4()),
                    projectId=str(uuid4()),
                    runName="missing-run",
                    state="running",
                )
            ]
        )
        state_mgr.state = state

        # Create reconciler (no actual runs in filesystem)
        reconciler = Reconciler(harness_path=self.harness_path)

        # Run reconciliation
        result = reconciler.reconcile(state_mgr)

        # Verify run was parked
        self.assertEqual(result.runs_parked, 1)
        self.assertTrue(result.drift_detected)
        self.assertEqual(state_mgr.state.runs[0].state, "missing")


if __name__ == "__main__":
    unittest.main()
