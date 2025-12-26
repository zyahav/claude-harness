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


if __name__ == "__main__":
    unittest.main()
