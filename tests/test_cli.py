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

    @patch('harness.handle_session')
    def test_session_command_dispatch(self, mock_session):
        """Verify 'session' command calls handler."""
        with patch.object(sys, 'argv', ['harness.py', 'session']):
            main()
            mock_session.assert_called_once()

    @patch('harness.handle_next')
    def test_next_command_dispatch(self, mock_next):
        """Verify 'next' command calls handler."""
        with patch.object(sys, 'argv', ['harness.py', 'next']):
            main()
            mock_next.assert_called_once()

    def test_next_command_runs(self):
        """Test that next command runs without error."""
        result = subprocess.run(
            [sys.executable, "harness.py", "next"],
            capture_output=True,
            text=True
        )
        self.assertEqual(result.returncode, 0)
        # Should contain key output elements
        self.assertIn("NEXT ACTION", result.stdout)
        self.assertIn("Why:", result.stdout)
        self.assertIn("Done:", result.stdout)

    @patch('harness.handle_focus')
    def test_focus_command_dispatch(self, mock_focus):
        """Verify 'focus' command calls handler."""
        with patch.object(sys, 'argv', ['harness.py', 'focus']):
            main()
            mock_focus.assert_called_once()

    @patch('harness.handle_focus')
    def test_focus_set_command_dispatch(self, mock_focus):
        """Verify 'focus set' command calls handler with project argument."""
        with patch.object(sys, 'argv', ['harness.py', 'focus', 'test-project']):
            main()
            mock_focus.assert_called_once()
            args = mock_focus.call_args[0][0]
            self.assertEqual(args.set_project, 'test-project')

    def test_focus_view_command_runs(self):
        """Test that focus view command runs without error."""
        result = subprocess.run(
            [sys.executable, "harness.py", "focus"],
            capture_output=True,
            text=True
        )
        self.assertEqual(result.returncode, 0)
        # Should display focus information or message about no focus
        self.assertTrue("focus" in result.stdout.lower() or "No focus project set" in result.stdout)

if __name__ == "__main__":
    unittest.main()
