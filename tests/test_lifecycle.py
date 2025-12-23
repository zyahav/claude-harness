import unittest
import os
import shutil
import tempfile
import subprocess
from pathlib import Path
from unittest.mock import patch

# Configure lifecycle module to use temporary directories
import lifecycle

class TestLifecycle(unittest.TestCase):
    def setUp(self):
        # 1. Create a temporary root directory for the test
        self.test_root = tempfile.TemporaryDirectory()
        self.root_path = Path(self.test_root.name)
        
        # 2. Setup mock "origin" repo (so we have a base branch to fetch from)
        self.origin_dir = self.root_path / "origin.git"
        self.origin_dir.mkdir()
        subprocess.run(["git", "init", "--bare", str(self.origin_dir)], check=True, capture_output=True)
        
        # 3. Setup a "local" repo that simulates the user's workspace
        self.local_repo_dir = self.root_path / "harness-lab"
        self.local_repo_dir.mkdir()
        
        # Initialize and configure local repo
        run_git_here = lambda args: subprocess.run(
            ["git"] + args, cwd=self.local_repo_dir, check=True, capture_output=True
        )
        run_git_here(["init"])
        # Configure git identity for CI environment where global config may be missing
        # run_git_here(["config", "user.email", "test@example.com"])
        # run_git_here(["config", "user.name", "Test User"])
        
        # Ensure we are on 'main' branch (git init might default to 'master' on some systems)
        run_git_here(["checkout", "-B", "main"])
        
        run_git_here(["remote", "add", "origin", str(self.origin_dir)])
        
        # Create an initial commit so we have a 'main' branch
        (self.local_repo_dir / "README.md").write_text("# Test Repo")
        run_git_here(["add", "README.md"])
        run_git_here(["commit", "-m", "Initial commit"])
        run_git_here(["push", "-u", "origin", "main"])
        
        # 4. Patch lifecycle.RUNS_DIR to point to our temp 'runs' inside local repo
        self.runs_dir = self.local_repo_dir / "runs"
        self.runs_patcher = patch('lifecycle.RUNS_DIR', self.runs_dir)
        self.runs_patcher.start()
        
        # 5. Switch to our temporary local repo for execution
        self.cwd_patcher = patch('lifecycle.run_git')
        self.mock_run_git = self.cwd_patcher.start()
        
        # IMPORTANT: We want the REAL run_git logic, but executed in our temp dir.
        # But lifecycle.run_git doesn't take cwd arg for all calls (uses module default or shell).
        # WAIT: lifecycle.run_git puts `cwd=cwd` in subproccess.run.
        # However, checking `lifecycle.py`, create_run calls:
        # run_git(["worktree", "add",...]) which defaults to None (current process cwd).
        # We need to change the current working directory of the process for the test duration.
        self.original_cwd = os.getcwd()
        os.chdir(self.local_repo_dir)

        # Unmock run_git because we want to test the REAL git commands!
        # The isolation comes from os.chdir and the temp directory structure.
        self.cwd_patcher.stop() 

    def tearDown(self):
        # Restore CWD
        os.chdir(self.original_cwd)
        
        # Stop patcher
        self.runs_patcher.stop()
        
        # Cleanup temp dir (handled by TemporaryDirectory context manager, but we call cleanup explicitly to be sure)
        self.test_root.cleanup()

    def test_create_run_success(self):
        """Test creating a new run, which should create a worktree and branch."""
        run_name = "test-feature"
        
        # Execute
        run_dir = lifecycle.create_run(run_name)
        
        # Verify Directory Exists
        self.assertTrue(run_dir.exists())
        self.assertTrue((run_dir / ".git").exists()) # Worktree has a .git file
        self.assertTrue((run_dir / ".run.json").exists())
        
        # Verify Metadata
        meta = lifecycle.load_run_metadata(run_name)
        self.assertEqual(meta.name, run_name)
        self.assertEqual(meta.status, "active")
        self.assertEqual(meta.branch, f"run/{run_name}")

        # Verify Branch exists using git
        branches = subprocess.check_output(["git", "branch"], text=True)
        self.assertIn(f"run/{run_name}", branches)

    def test_create_duplicate_run_fails(self):
        """Test that creating a run with an existing name fails."""
        lifecycle.create_run("duplicate-test")
        
        with self.assertRaises(FileExistsError):
            lifecycle.create_run("duplicate-test")

    def test_list_runs(self):
        """Test listing active runs."""
        # Create two runs
        lifecycle.create_run("run-1")
        lifecycle.create_run("run-2")
        
        runs = lifecycle.list_runs()
        self.assertEqual(len(runs), 2)
        
        names = [r.name for r in runs]
        self.assertIn("run-1", names)
        self.assertIn("run-2", names)

    def test_cleanup_run(self):
        """Test cleaning up a run removes the worktree and directory."""
        run_name = "cleanup-test"
        run_dir = lifecycle.create_run(run_name)
        
        self.assertTrue(run_dir.exists())
        
        # Execute cleanup
        lifecycle.cleanup_run(run_name)
        
        # Verify directory is gone
        self.assertFalse(run_dir.exists())
        
        # Verify it's no longer in list_runs
        runs = lifecycle.list_runs()
        names = [r.name for r in runs]
        self.assertNotIn(run_name, names)
        
        # Verify worktree is pruned from git
        worktrees = subprocess.check_output(["git", "worktree", "list"], text=True)
        self.assertNotIn(str(run_dir), worktrees)

    def test_cleanup_with_branch_deletion(self):
        """Test cleanup with --delete-branch option."""
        run_name = "delete-branch-test"
        lifecycle.create_run(run_name)
        
        # Execute cleanup with branch deletion
        lifecycle.cleanup_run(run_name, delete_branch=True)
        
        # Verify branch is gone
        branches = subprocess.check_output(["git", "branch"], text=True)
        self.assertNotIn(f"run/{run_name}", branches)

if __name__ == "__main__":
    # Ensure git user is configured for commits to work in temp repo
    subprocess.run(["git", "config", "--global", "user.email", "test@example.com"], capture_output=True)
    subprocess.run(["git", "config", "--global", "user.name", "Test User"], capture_output=True)
    unittest.main()
