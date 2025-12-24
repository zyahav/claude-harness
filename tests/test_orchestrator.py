import unittest
import shutil
import tempfile
import subprocess
from pathlib import Path
from unittest.mock import patch

# Configure lifecycle module to use temporary directories
import lifecycle

class TestOrchestrator(unittest.TestCase):
    def setUp(self):
        # 1. Create a "Harness" environment (temp dir simulating where we run the tool)
        self.harness_root = tempfile.TemporaryDirectory()
        self.harness_path = Path(self.harness_root.name)
        
        # 2. Patch RUNS_DIR to be inside our Harness test env
        self.runs_dir = self.harness_path / "runs"
        self.runs_patcher = patch('lifecycle.RUNS_DIR', self.runs_dir)
        self.runs_patcher.start()
        
        # 3. Create a "Target Repo" (external to Harness)
        self.target_root = tempfile.TemporaryDirectory()
        self.target_path = Path(self.target_root.name) / "my-project"
        self.target_path.mkdir()
        
        # Initialize target repo
        run_git_target = lambda args: subprocess.run(
            ["git"] + args, cwd=self.target_path, check=True, capture_output=True
        )
        run_git_target(["init"])
        run_git_target(["config", "user.email", "test@example.com"])
        run_git_target(["config", "user.name", "Test User"])
        run_git_target(["checkout", "-B", "main"])
        
        # Initial commit
        (self.target_path / "README.md").write_text("# Target Repo")
        run_git_target(["add", "README.md"])
        run_git_target(["commit", "-m", "Initial commit"])

    def tearDown(self):
        self.runs_patcher.stop()
        self.harness_root.cleanup()
        self.target_root.cleanup()

    def test_external_repo_workflow(self):
        """Test the full Orchestrator workflow."""
        run_name = "orch-test-01"
        
        # 1. Start Run (Orchestrator Mode)
        # We are passing the EXTERNAL repo path.
        # The worktree should be created in self.runs_dir (Harness/runs)
        print(f"\n[Test] Creating run for target: {self.target_path}")
        run_dir = lifecycle.create_run(run_name, repo_path=self.target_path)
        
        # VERIFY: Worktree location
        self.assertTrue(run_dir.exists())
        self.assertTrue(str(run_dir).startswith(str(self.harness_path)))
        self.assertFalse(str(run_dir).startswith(str(self.target_path)))
        
        # VERIFY: Git status in worktree
        # It should know it's part of the target repo
        status = subprocess.check_output(["git", "status"], cwd=run_dir, text=True)
        self.assertIn(f"On branch run/{run_name}", status)
        
        # VERIFY: Branch existence in target repo
        branches = subprocess.check_output(["git", "branch"], cwd=self.target_path, text=True)
        self.assertIn(f"run/{run_name}", branches)
        
        # 2. Cleanup
        lifecycle.cleanup_run(run_name, delete_branch=True)
        
        # VERIFY: Cleanup
        self.assertFalse(run_dir.exists())
        branches_after = subprocess.check_output(["git", "branch"], cwd=self.target_path, text=True)
        self.assertNotIn(f"run/{run_name}", branches_after)

if __name__ == "__main__":
    unittest.main()
