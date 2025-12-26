"""
Archon Integration Tests
========================

Tests for the Archon MCP integration.
"""

import unittest
import json
import tempfile
from pathlib import Path


class TestArchonIntegration(unittest.TestCase):
    """Test Archon integration module."""

    def test_archon_integration_module_exists(self):
        """Verify archon_integration module can be imported."""
        try:
            import archon_integration
            self.assertTrue(hasattr(archon_integration, 'is_archon_available'))
            self.assertTrue(hasattr(archon_integration, 'setup_archon_for_run'))
            self.assertTrue(hasattr(archon_integration, 'ArchonProject'))
        except ImportError:
            self.fail("archon_integration module not found")

    def test_archon_project_dataclass(self):
        """Verify ArchonProject dataclass works."""
        from archon_integration import ArchonProject
        
        project = ArchonProject(
            project_id="test-123",
            title="Test Project",
            task_ids={"TASK-001": "archon-task-1"}
        )
        
        self.assertEqual(project.project_id, "test-123")
        self.assertEqual(project.title, "Test Project")
        self.assertEqual(project.task_ids["TASK-001"], "archon-task-1")

    def test_save_and_load_archon_reference(self):
        """Verify Archon reference can be saved and loaded from .run.json."""
        from archon_integration import ArchonProject, save_archon_reference, load_archon_reference
        
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            
            # Create initial .run.json
            run_json = run_dir / ".run.json"
            run_json.write_text(json.dumps({"name": "test-run"}))
            
            # Save archon reference
            project = ArchonProject(
                project_id="proj-456",
                title="Test / RUN-001",
                task_ids={"T1": "at1", "T2": "at2"}
            )
            save_archon_reference(run_dir, project)
            
            # Load it back
            loaded = load_archon_reference(run_dir)
            
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.project_id, "proj-456")
            self.assertEqual(loaded.title, "Test / RUN-001")
            self.assertEqual(loaded.task_ids, {"T1": "at1", "T2": "at2"})

    def test_lifecycle_create_run_accepts_archon_flag(self):
        """Verify create_run accepts archon parameter."""
        import inspect
        from lifecycle import create_run
        
        sig = inspect.signature(create_run)
        params = list(sig.parameters.keys())
        
        self.assertIn("archon", params, "create_run should accept archon parameter")
        self.assertIn("handoff_path", params, "create_run should accept handoff_path parameter")

    def test_agent_has_archon_helper_functions(self):
        """Verify agent.py has the Archon helper functions."""
        import agent
        
        self.assertTrue(hasattr(agent, 'get_current_task_id'))
        self.assertTrue(hasattr(agent, 'update_archon_task_status'))
        self.assertTrue(hasattr(agent, 'get_task_pass_states'))
        self.assertTrue(hasattr(agent, 'check_newly_completed_tasks'))
        self.assertTrue(hasattr(agent, 'log_session_summary'))

    def test_get_current_task_id_returns_first_incomplete(self):
        """Verify get_current_task_id returns first task with passes=false."""
        from agent import get_current_task_id
        
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            handoff = project_dir / "handoff.json"
            
            # Create handoff with mixed pass states
            handoff.write_text(json.dumps({
                "tasks": [
                    {"id": "TASK-1", "passes": True},
                    {"id": "TASK-2", "passes": False},
                    {"id": "TASK-3", "passes": False},
                ]
            }))
            
            result = get_current_task_id(project_dir)
            self.assertEqual(result, "TASK-2")

    def test_get_current_task_id_returns_none_when_all_complete(self):
        """Verify get_current_task_id returns None when all tasks pass."""
        from agent import get_current_task_id
        
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            handoff = project_dir / "handoff.json"
            
            handoff.write_text(json.dumps({
                "tasks": [
                    {"id": "TASK-1", "passes": True},
                    {"id": "TASK-2", "passes": True},
                ]
            }))
            
            result = get_current_task_id(project_dir)
            self.assertIsNone(result)

    def test_check_newly_completed_tasks(self):
        """Verify check_newly_completed_tasks detects changes."""
        from agent import check_newly_completed_tasks
        
        before = {"T1": False, "T2": False, "T3": True}
        after = {"T1": True, "T2": False, "T3": True}
        
        result = check_newly_completed_tasks(before, after)
        
        self.assertEqual(result, ["T1"])

    def test_graceful_fallback_when_archon_unavailable(self):
        """Verify Archon functions don't crash when Archon is unavailable."""
        from agent import update_archon_task_status, log_session_summary
        import agent
        
        # Ensure no archon project is set
        agent._archon_project = None
        
        # These should not raise exceptions
        update_archon_task_status("FAKE-TASK", "doing")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            log_session_summary(Path(tmpdir), 1, [])
        
        # If we got here without exception, test passes

    def test_run_autonomous_agent_accepts_no_archon_flag(self):
        """Verify run_autonomous_agent accepts no_archon parameter."""
        import inspect
        from agent import run_autonomous_agent
        
        sig = inspect.signature(run_autonomous_agent)
        params = list(sig.parameters.keys())
        
        self.assertIn("no_archon", params, "run_autonomous_agent should accept no_archon parameter")


if __name__ == "__main__":
    unittest.main()
