"""
Unit tests for Harness Commander rule engine.
"""

import unittest
from uuid import uuid4
from datetime import datetime

from rules import compute_next_action
from state import State, StateManager, Project, Run, Task, InboxItem


class MockStateManager:
    """Mock StateManager for testing."""

    def __init__(self, projects=None):
        self.projects = projects or []

    def get_project(self, project_id):
        """Get project by ID."""
        for project in self.projects:
            if project.id == project_id:
                return project
        return None


class TestComputeNextAction(unittest.TestCase):
    """Test compute_next_action rule engine."""

    def test_rule_1_clean_finished_runs(self):
        """Test Rule 1: Clean finished runs takes highest priority."""
        project = Project(
            id=str(uuid4()),
            name="test-project",
            repoPath="/tmp/test",
            status="active",
        )
        finished_run = Run(
            id=str(uuid4()),
            projectId=project.id,
            runName="finished-run",
            state="finished",
        )
        active_run = Run(
            id=str(uuid4()),
            projectId=project.id,
            runName="active-run",
            state="running",
        )

        state = State(
            focusProjectId=project.id,
            projects=[project],
            runs=[finished_run, active_run],
            tasks=[],
            inbox=[],
        )
        state_mgr = MockStateManager(projects=[project])

        result = compute_next_action(state, state_mgr)

        self.assertEqual(
            result["action"], f"c-harness clean {finished_run.runName}"
        )
        self.assertIn("finished and should be cleaned up", result["why"])
        self.assertIn("marked as cleaned", result["done"])

    def test_rule_2a_no_focus_project_with_projects(self):
        """Test Rule 2a: No focus project, projects exist."""
        project = Project(
            id=str(uuid4()),
            name="test-project",
            repoPath="/tmp/test",
            status="active",
        )

        state = State(
            focusProjectId="",  # No focus set
            projects=[project],
            runs=[],
            tasks=[],
            inbox=[],
        )
        state_mgr = MockStateManager(projects=[project])

        result = compute_next_action(state, state_mgr)

        self.assertEqual(result["action"], "c-harness focus set <project-id>")
        self.assertIn("No focus project set", result["why"])
        self.assertIn("Focus project set", result["done"])

    def test_rule_2b_no_focus_project_no_projects(self):
        """Test Rule 2b: No focus project, no projects exist."""
        state = State(
            focusProjectId="",  # No focus set
            projects=[],
            runs=[],
            tasks=[],
            inbox=[],
        )
        state_mgr = MockStateManager(projects=[])

        result = compute_next_action(state, state_mgr)

        self.assertEqual(result["action"], "c-harness start <run-name>")
        self.assertIn("No projects exist", result["why"])
        self.assertIn("project registered", result["done"])

    def test_rule_3_tasks_in_doing(self):
        """Test Rule 3: Tasks in 'doing' column."""
        project = Project(
            id=str(uuid4()),
            name="test-project",
            repoPath="/tmp/test",
            status="active",
        )
        active_task = Task(
            id=str(uuid4()),
            projectId=project.id,
            title="Implement feature X",
            column="doing",
            createdAt=datetime.now().isoformat(),
        )

        state = State(
            focusProjectId=project.id,
            projects=[project],
            runs=[],
            tasks=[active_task],
            inbox=[],
        )
        state_mgr = MockStateManager(projects=[project])

        result = compute_next_action(state, state_mgr)

        self.assertIn("Work on task:", result["action"])
        self.assertIn("feature X", result["action"])
        self.assertIn("DOING", result["why"])
        self.assertIn("continue implementation", result["why"])

    def test_rule_3_tasks_in_preview(self):
        """Test Rule 3: Tasks in 'preview' column."""
        project = Project(
            id=str(uuid4()),
            name="test-project",
            repoPath="/tmp/test",
            status="active",
        )
        preview_task = Task(
            id=str(uuid4()),
            projectId=project.id,
            title="Review feature Y",
            column="preview",
            createdAt=datetime.now().isoformat(),
        )

        state = State(
            focusProjectId=project.id,
            projects=[project],
            runs=[],
            tasks=[preview_task],
            inbox=[],
        )
        state_mgr = MockStateManager(projects=[project])

        result = compute_next_action(state, state_mgr)

        self.assertIn("Work on task:", result["action"])
        self.assertIn("feature Y", result["action"])
        self.assertIn("PREVIEW", result["why"])

    def test_rule_4_tasks_in_todo(self):
        """Test Rule 4: Tasks in 'todo' column."""
        project = Project(
            id=str(uuid4()),
            name="test-project",
            repoPath="/tmp/test",
            status="active",
        )
        todo_task = Task(
            id=str(uuid4()),
            projectId=project.id,
            title="Fix bug Z",
            column="todo",
            createdAt=datetime.now().isoformat(),
        )

        state = State(
            focusProjectId=project.id,
            projects=[project],
            runs=[],
            tasks=[todo_task],
            inbox=[],
        )
        state_mgr = MockStateManager(projects=[project])

        result = compute_next_action(state, state_mgr)

        self.assertIn("c-harness start", result["action"])
        self.assertIn("Fix bug Z", result["why"])
        self.assertIn("ready to start", result["why"])
        self.assertIn("moved to 'doing'", result["done"])

    def test_rule_5_inbox_items(self):
        """Test Rule 5: Inbox items to promote."""
        project = Project(
            id=str(uuid4()),
            name="test-project",
            repoPath="/tmp/test",
            status="active",
        )
        inbox_item = InboxItem(
            id=str(uuid4()),
            text="Idea for new feature",
            createdAt=datetime.now().isoformat(),
        )

        state = State(
            focusProjectId=project.id,
            projects=[project],
            runs=[],
            tasks=[],
            inbox=[inbox_item],
        )
        state_mgr = MockStateManager(projects=[project])

        result = compute_next_action(state, state_mgr)

        self.assertIn("c-harness inbox promote", result["action"])
        self.assertIn("1 item(s)", result["why"])
        self.assertIn("Promote to create tasks", result["why"])
        self.assertIn("converted to task", result["done"])

    def test_rule_6_nothing_to_do(self):
        """Test Rule 6: No tasks, no inbox - prompt to start new run."""
        project = Project(
            id=str(uuid4()),
            name="test-project",
            repoPath="/tmp/test",
            status="active",
        )

        state = State(
            focusProjectId=project.id,
            projects=[project],
            runs=[],
            tasks=[],
            inbox=[],
        )
        state_mgr = MockStateManager(projects=[project])

        result = compute_next_action(state, state_mgr)

        self.assertIn("c-harness start", result["action"])
        self.assertIn("test-project", result["action"])
        self.assertIn("No active tasks", result["why"])
        self.assertIn("Start a new run", result["why"])

    def test_priority_order_finished_vs_active_tasks(self):
        """Test that cleaning finished runs takes priority over active tasks."""
        project = Project(
            id=str(uuid4()),
            name="test-project",
            repoPath="/tmp/test",
            status="active",
        )
        finished_run = Run(
            id=str(uuid4()),
            projectId=project.id,
            runName="finished-run",
            state="finished",
        )
        active_task = Task(
            id=str(uuid4()),
            projectId=project.id,
            title="Active task",
            column="doing",
            createdAt=datetime.now().isoformat(),
        )

        state = State(
            focusProjectId=project.id,
            projects=[project],
            runs=[finished_run],
            tasks=[active_task],
            inbox=[],
        )
        state_mgr = MockStateManager(projects=[project])

        result = compute_next_action(state, state_mgr)

        # Should prioritize cleaning finished run
        self.assertEqual(result["action"], f"c-harness clean {finished_run.runName}")

    def test_priority_order_focus_vs_tasks(self):
        """Test that setting focus takes priority over tasks."""
        project = Project(
            id=str(uuid4()),
            name="test-project",
            repoPath="/tmp/test",
            status="active",
        )
        todo_task = Task(
            id=str(uuid4()),
            projectId=project.id,
            title="Todo task",
            column="todo",
            createdAt=datetime.now().isoformat(),
        )

        state = State(
            focusProjectId="",  # No focus set
            projects=[project],
            runs=[],
            tasks=[todo_task],
            inbox=[],
        )
        state_mgr = MockStateManager(projects=[project])

        result = compute_next_action(state, state_mgr)

        # Should prioritize setting focus
        self.assertEqual(result["action"], "c-harness focus set <project-id>")

    def test_multiple_inbox_items(self):
        """Test that inbox shows correct count when multiple items exist."""
        project = Project(
            id=str(uuid4()),
            name="test-project",
            repoPath="/tmp/test",
            status="active",
        )
        inbox_items = [
            InboxItem(
                id=str(uuid4()),
                text=f"Idea {i}",
                createdAt=datetime.now().isoformat(),
            )
            for i in range(3)
        ]

        state = State(
            focusProjectId=project.id,
            projects=[project],
            runs=[],
            tasks=[],
            inbox=inbox_items,
        )
        state_mgr = MockStateManager(projects=[project])

        result = compute_next_action(state, state_mgr)

        self.assertIn("3 item(s)", result["why"])


if __name__ == "__main__":
    unittest.main()
