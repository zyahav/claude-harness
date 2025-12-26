"""
Harness Commander - Rule Engine
================================

Rule engine for computing the next action in Harness Commander.
Implements priority-based action selection.
"""

import logging
from state import State, StateManager, Project, Run

logger = logging.getLogger(__name__)


def compute_next_action(state: State, state_mgr: StateManager) -> dict:
    """Compute the next action using rule engine.

    Rule engine priority (from HARNESS-018-H acceptance criteria):
    1. Clean finished runs
    2. Set focus project if not set
    3. Continue tasks in doing/preview
    4. Start tasks in todo
    5. Promote inbox items to tasks
    6. Start new run

    Args:
        state: Current Commander state
        state_mgr: StateManager instance for lookups

    Returns:
        Dictionary with 'action', 'why', and 'done' keys
    """
    # Rule 1: Clean finished runs
    for run in state.runs:
        if run.state == "finished":
            project = state_mgr.get_project(run.projectId)
            project_name = project.name if project else "unknown"
            return {
                "action": f"c-harness clean {run.runName}",
                "why": f"Run '{run.runName}' in {project_name} is finished and should be cleaned up",
                "done": f"Worktree deleted, run marked as cleaned"
            }

    # Rule 2: No focus project set
    if not state.focusProjectId:
        if state.projects:
            return {
                "action": "c-harness focus set <project-id>",
                "why": "No focus project set. Choose a project to focus on.",
                "done": "Focus project set, subsequent commands target this project"
            }
        else:
            return {
                "action": "c-harness start <run-name>",
                "why": "No projects exist. Start your first run to create a project.",
                "done": "New worktree created, project registered, run started"
            }

    # Rule 3: Tasks in "doing" or "preview" - check if worktree is dirty
    active_tasks = [t for t in state.tasks if t.column in ["doing", "preview"]]
    if active_tasks:
        # For now, just prompt to continue work
        task = active_tasks[0]
        return {
            "action": f"# Work on task: {task.title}",
            "why": f"Task '{task.title}' is in {task.column.upper()} - continue implementation",
            "done": f"Task completed, move to 'done' or 'preview'"
        }

    # Rule 4: Tasks in "todo"
    todo_tasks = [t for t in state.tasks if t.column == "todo"]
    if todo_tasks:
        task = todo_tasks[0]
        return {
            "action": f"c-harness focus set <project>; c-harness start <run-name>",
            "why": f"Task '{task.title}' is ready to start",
            "done": f"Run started, task moved to 'doing'"
        }

    # Rule 5: Inbox items to promote
    if state.inbox:
        item = state.inbox[0]
        return {
            "action": f"c-harness inbox promote {item.id[:8]}",
            "why": f"Inbox has {len(state.inbox)} item(s). Promote to create tasks.",
            "done": f"Inbox item converted to task in focus project"
        }

    # Rule 6: Nothing to do - prompt to start something
    focus_project = state_mgr.get_project(state.focusProjectId)
    project_name = focus_project.name if focus_project else "unknown"

    return {
        "action": f"c-harness start <run-name> --project {project_name}",
        "why": "No active tasks or inbox items. Start a new run to begin work.",
        "done": f"New run started for {project_name}"
    }
