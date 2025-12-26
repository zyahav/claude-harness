"""
Unit tests for Harness Commander state management.
"""

import unittest
import tempfile
import json
import os
from pathlib import Path
from uuid import uuid4

from state import (
    StateManager,
    State,
    Project,
    Run,
    Task,
    InboxItem,
    generate_uuid,
    get_timestamp,
    COMMANDER_HOME,
)


class TestStateModels(unittest.TestCase):
    """Test state data models."""

    def test_inbox_item_generates_id(self):
        """Test InboxItem generates UUID if not provided."""
        item = InboxItem(id="", text="Test item", createdAt="2025-01-01T00:00:00Z")
        self.assertIsNotNone(item.id)
        self.assertTrue(len(item.id) > 0)

    def test_task_generates_id(self):
        """Test Task generates UUID if not provided."""
        task = Task(
            id="",
            projectId=str(uuid4()),
            title="Test task",
            column="todo",
            createdAt="2025-01-01T00:00:00Z",
        )
        self.assertIsNotNone(task.id)

    def test_run_generates_id(self):
        """Test Run generates UUID if not provided."""
        run = Run(
            id="", projectId=str(uuid4()), runName="test-run", state="running"
        )
        self.assertIsNotNone(run.id)

    def test_project_generates_id(self):
        """Test Project generates UUID if not provided."""
        project = Project(
            id="", name="test-project", repoPath="/tmp/test", status="active"
        )
        self.assertIsNotNone(project.id)

    def test_state_to_dict(self):
        """Test State serializes to dict correctly."""
        state = State(focusProjectId="proj-123")
        data = state.to_dict()

        self.assertEqual(data["focusProjectId"], "proj-123")
        self.assertEqual(data["projects"], [])
        self.assertEqual(data["runs"], [])
        self.assertEqual(data["tasks"], [])
        self.assertEqual(data["inbox"], [])

    def test_state_from_dict(self):
        """Test State deserializes from dict correctly."""
        data = {
            "focusProjectId": "proj-123",
            "projects": [],
            "runs": [],
            "tasks": [],
            "inbox": [],
        }
        state = State.from_dict(data)

        self.assertEqual(state.focusProjectId, "proj-123")
        self.assertEqual(len(state.projects), 0)
        self.assertEqual(len(state.runs), 0)


class TestStateManager(unittest.TestCase):
    """Test StateManager class."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.state_path = Path(self.temp_dir) / "state.json"
        self.manager = StateManager(state_path=self.state_path)

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_ensure_directories_creates_home(self):
        """Test ensure_directories creates the home directory."""
        self.manager.ensure_directories()
        self.assertTrue(self.state_path.parent.exists())

    def test_load_state_creates_new_if_missing(self):
        """Test load_state creates empty state if file doesn't exist."""
        state = self.manager.load_state()

        self.assertIsInstance(state, State)
        self.assertIsNone(state.focusProjectId)
        self.assertEqual(len(state.projects), 0)
        self.assertEqual(len(state.runs), 0)

    def test_load_state_saves_to_manager(self):
        """Test load_state saves state to manager instance."""
        state = self.manager.load_state()
        self.assertIs(self.manager.state, state)

    def test_save_state_creates_file(self):
        """Test save_state creates state file."""
        self.manager.state = State(focusProjectId="proj-123")
        self.manager.save_state()

        self.assertTrue(self.state_path.exists())

    def test_save_state_writes_correct_data(self):
        """Test save_state writes correct data to file."""
        self.manager.state = State(focusProjectId="proj-123")
        self.manager.save_state()

        with open(self.state_path, "r") as f:
            data = json.load(f)

        self.assertEqual(data["focusProjectId"], "proj-123")

    def test_atomic_write_is_atomic(self):
        """Test atomic_write uses temp file and rename."""
        self.manager.atomic_write({"test": "data"})

        # Temp file should be cleaned up
        self.assertFalse(self.manager.state_tmp_path.exists())

        # Main file should exist
        self.assertTrue(self.state_path.exists())

    def test_recover_from_crash_removes_tmp_file(self):
        """Test recover_from_crash removes incomplete temp file."""
        # Create a temp file
        self.manager.state_tmp_path.write_text("incomplete")

        self.manager.recover_from_crash()

        # Temp file should be removed
        self.assertFalse(self.manager.state_tmp_path.exists())

    def test_recover_from_crash_does_nothing_if_no_tmp(self):
        """Test recover_from_crash does nothing if no temp file."""
        # Should not raise
        self.manager.recover_from_crash()

    def test_load_recovers_from_crash(self):
        """Test load_state calls recover_from_crash."""
        # Create incomplete temp file
        self.manager.state_tmp_path.write_text("incomplete")

        # Load should clean up
        state = self.manager.load_state()

        # Temp file should be removed
        self.assertFalse(self.manager.state_tmp_path.exists())

    def test_save_state_without_load_raises(self):
        """Test save_state raises if no state is loaded."""
        with self.assertRaises(RuntimeError):
            self.manager.save_state()

    def test_update_state_saves_to_disk(self):
        """Test update_state saves new state to disk."""
        # Load initial state
        self.manager.load_state()

        # Update with new state
        new_state = State(focusProjectId="proj-456")
        self.manager.update_state(new_state)

        # Verify it was saved
        with open(self.state_path, "r") as f:
            data = json.load(f)

        self.assertEqual(data["focusProjectId"], "proj-456")

    def test_get_project_returns_none_if_no_state(self):
        """Test get_project returns None if no state loaded."""
        result = self.manager.get_project("proj-123")
        self.assertIsNone(result)

    def test_get_project_returns_none_if_not_found(self):
        """Test get_project returns None if project doesn't exist."""
        self.manager.state = State(projects=[])
        result = self.manager.get_project("proj-123")
        self.assertIsNone(result)

    def test_get_project_finds_by_id(self):
        """Test get_project finds project by ID."""
        project = Project(
            id="proj-123", name="test", repoPath="/tmp", status="active"
        )
        self.manager.state = State(projects=[project])

        result = self.manager.get_project("proj-123")

        self.assertIsNotNone(result)
        self.assertEqual(result.id, "proj-123")

    def test_get_run_returns_none_if_no_state(self):
        """Test get_run returns None if no state loaded."""
        result = self.manager.get_run("run-123")
        self.assertIsNone(result)

    def test_get_run_finds_by_id(self):
        """Test get_run finds run by ID."""
        run = Run(id="run-123", projectId="proj-1", runName="test", state="running")
        self.manager.state = State(runs=[run])

        result = self.manager.get_run("run-123")

        self.assertIsNotNone(result)
        self.assertEqual(result.id, "run-123")

    def test_get_inbox_item_returns_none_if_no_state(self):
        """Test get_inbox_item returns None if no state loaded."""
        result = self.manager.get_inbox_item("inbox-123")
        self.assertIsNone(result)

    def test_get_inbox_item_finds_by_id(self):
        """Test get_inbox_item finds item by ID."""
        item = InboxItem(
            id="inbox-123", text="Test item", createdAt="2025-01-01T00:00:00Z"
        )
        self.manager.state = State(inbox=[item])

        result = self.manager.get_inbox_item("inbox-123")

        self.assertIsNotNone(result)
        self.assertEqual(result.id, "inbox-123")


class TestUtilities(unittest.TestCase):
    """Test utility functions."""

    def test_generate_uuid_returns_string(self):
        """Test generate_uuid returns a string."""
        uuid_str = generate_uuid()
        self.assertIsInstance(uuid_str, str)
        self.assertTrue(len(uuid_str) > 0)

    def test_generate_uuid_generates_unique_ids(self):
        """Test generate_uuid generates unique IDs."""
        uuid1 = generate_uuid()
        uuid2 = generate_uuid()
        self.assertNotEqual(uuid1, uuid2)

    def test_get_timestamp_returns_string(self):
        """Test get_timestamp returns a string."""
        timestamp = get_timestamp()
        self.assertIsInstance(timestamp, str)
        self.assertTrue(len(timestamp) > 0)

    def test_get_timestamp_includes_z(self):
        """Test get_timestamp ends with Z (UTC)."""
        timestamp = get_timestamp()
        self.assertTrue(timestamp.endswith("Z"))


class TestStatePersistence(unittest.TestCase):
    """Test state persistence across sessions."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.state_path = Path(self.temp_dir) / "state.json"

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_state_survives_manager_recreation(self):
        """Test state persists across StateManager instances."""
        # Create and save state
        manager1 = StateManager(state_path=self.state_path)
        manager1.state = State(focusProjectId="proj-123")
        manager1.save_state()

        # Create new manager and load
        manager2 = StateManager(state_path=self.state_path)
        state = manager2.load_state()

        self.assertEqual(state.focusProjectId, "proj-123")

    def test_complex_state_serializes_correctly(self):
        """Test complex state with projects, runs, tasks, inbox."""
        project = Project(
            id="proj-1", name="test", repoPath="/tmp", status="active"
        )
        run = Run(id="run-1", projectId="proj-1", runName="test", state="running")
        task = Task(
            id="task-1", projectId="proj-1", title="Test", column="todo", createdAt="now"
        )
        inbox = InboxItem(id="inbox-1", text="Idea", createdAt="now")

        state = State(
            focusProjectId="proj-1",
            projects=[project],
            runs=[run],
            tasks=[task],
            inbox=[inbox],
        )

        # Save and load
        manager = StateManager(state_path=self.state_path)
        manager.state = state
        manager.save_state()

        manager2 = StateManager(state_path=self.state_path)
        loaded = manager2.load_state()

        self.assertEqual(len(loaded.projects), 1)
        self.assertEqual(len(loaded.runs), 1)
        self.assertEqual(len(loaded.tasks), 1)
        self.assertEqual(len(loaded.inbox), 1)
        self.assertEqual(loaded.projects[0].name, "test")


if __name__ == "__main__":
    unittest.main()
