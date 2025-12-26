import unittest
import sys
import subprocess
from io import StringIO
from unittest.mock import patch

from harness import main

class TestCLI(unittest.TestCase):
    def test_help_command(self):
        """Test that --help prints usage and exits with 0."""
        # subprocess is safest for end-to-end CLI entry point test
        result = subprocess.run(
            [sys.executable, "harness.py", "--help"], 
            capture_output=True, 
            text=True
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("Autonomous Coding Agent CLI", result.stdout)

    def test_list_command(self):
        """Test that list command runs without error."""
        # Using subprocess to verify entry point
        result = subprocess.run(
            [sys.executable, "harness.py", "list"], 
            capture_output=True, 
            text=True
        )
        self.assertEqual(result.returncode, 0)

    @patch('harness.handle_start')
    def test_start_command_dispatch(self, mock_start):
        """Verify 'start' command calls the correct handler."""
        # Mock sys.argv
        with patch.object(sys, 'argv', ['harness.py', 'start', 'run-name']):
            main()
            mock_start.assert_called_once()
            args = mock_start.call_args[0][0]
            self.assertEqual(args.name, 'run-name')

    @patch('harness.handle_run')
    def test_run_command_dispatch_defaults(self, mock_run):
        """Verify 'run' command calls handler with defaults."""
        with patch.object(sys, 'argv', ['harness.py', 'run', 'run-name']):
            main()
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            self.assertEqual(args.name, 'run-name')
            self.assertEqual(args.model, "claude-sonnet-4-5-20250929") # Checks default

    @patch('harness.handle_clean')
    def test_clean_command_dispatch(self, mock_clean):
        """Verify 'clean' command calls handler."""
        with patch.object(sys, 'argv', ['harness.py', 'clean', 'run-name', '--force']):
            main()
            mock_clean.assert_called_once()
            args = mock_clean.call_args[0][0]
            self.assertEqual(args.name, 'run-name')
            self.assertTrue(args.force)

    @patch('harness.handle_status')
    def test_status_command_dispatch(self, mock_status):
        """Verify 'status' command calls handler."""
        with patch.object(sys, 'argv', ['harness.py', 'status']):
            main()
            mock_status.assert_called_once()

    def test_status_command_runs(self):
        """Test that status command runs without error."""
        result = subprocess.run(
            [sys.executable, "harness.py", "status"],
            capture_output=True,
            text=True
        )
        self.assertEqual(result.returncode, 0)
        # Should contain key status elements
        self.assertTrue("focus:" in result.stdout or "Observer" in result.stdout or "Controller" in result.stdout)

if __name__ == "__main__":
    unittest.main()
