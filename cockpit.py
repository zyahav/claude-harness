"""
Harness Commander - Interactive Cockpit Display
=================================================

Visual display system for the Harness Commander session.
Shows focus project, active runs, tasks, inbox, and next action.
"""

import logging
from typing import Optional
from state import State, StateManager, Project, Run, Task, InboxItem

logger = logging.getLogger(__name__)


def format_section_header(title: str, width: int = 60) -> str:
    """Format a section header with a title.

    Args:
        title: Section title
        width: Total width of header line

    Returns:
        Formatted header string
    """
    return f"\n{title}" + " " * (width - len(title) - 2) + []


def format_project(project: Project) -> str:
    """Format a project for display.

    Args:
        project: Project to format

    Returns:
        Formatted project string
    """
    return f"  [{project.id[:8]}] {project.name} ({project.status})"


def format_run(run: Run) -> str:
    """Format a run for display.

    Args:
        run: Run to format

    Returns:
        Formatted run string
    """
    status_symbol = {
        "running": "▶",
        "finished": "✓",
        "cleaned": "○",
    }.get(run.state, "?")

    return f"  {status_symbol} {run.runName} [{run.id[:8]}] - {run.state}"


def format_task(task: Task) -> str:
    """Format a task for display.

    Args:
        task: Task to format

    Returns:
        Formatted task string
    """
    column_symbol = {
        "todo": "○",
        "doing": "▶",
        "preview": "◐",
        "blocked": "✕",
        "done": "✓",
    }.get(task.column, "?")

    return f"  {column_symbol} {task.title} [{task.id[:8]}]"


def format_inbox_item(item: InboxItem) -> str:
    """Format an inbox item for display.

    Args:
        item: InboxItem to format

    Returns:
        Formatted inbox item string
    """
    return f"  • {item.text} [{item.id[:8]}]"


def display_cockpit(state: State, state_mgr: StateManager) -> None:
    """Display the full cockpit dashboard.

    Args:
        state: Current Commander state
        state_mgr: StateManager instance for lookups
    """
    print("\n" + "=" * 60)
    print("  HARNESS COMMANDER COCKPIT")
    print("=" * 60)

    # Focus Now Section
    display_focus_section(state, state_mgr)

    # Active Runs Section
    display_runs_section(state)

    # Tasks Section (grouped by column)
    display_tasks_section(state)

    # Inbox Section
    display_inbox_section(state)

    print("=" * 60)


def display_focus_section(state: State, state_mgr: StateManager) -> None:
    """Display the focus project section.

    Args:
        state: Current Commander state
        state_mgr: StateManager instance
    """
    print("\n  FOCUS NOW")
    print("  " + "-" * 56)

    if state.focusProjectId:
        focus_project = state_mgr.get_project(state.focusProjectId)
        if focus_project:
            print(format_project(focus_project))
        else:
            print("  Focus project not found (ID: {})".format(state.focusProjectId[:8]))
    else:
        print("  No focus project set")


def display_runs_section(state: State) -> None:
    """Display active runs section.

    Args:
        state: Current Commander state
    """
    print("\n  ACTIVE RUNS")
    print("  " + "-" * 56)

    active_runs = [r for r in state.runs if r.state == "running"]

    if not active_runs:
        print("  No active runs")
    else:
        for run in active_runs:
            print(format_run(run))

    # Show finished runs count
    finished_count = len([r for r in state.runs if r.state == "finished"])
    if finished_count > 0:
        print(f"  ({finished_count} finished run(s) not shown)")


def display_tasks_section(state: State) -> None:
    """Display tasks section grouped by column.

    Args:
        state: Current Commander state
    """
    print("\n  TASKS")
    print("  " + "-" * 56)

    # Group tasks by column
    columns = ["doing", "preview", "blocked", "todo"]
    column_labels = {
        "doing": "▶ IN PROGRESS",
        "preview": "◐ IN PREVIEW",
        "blocked": "✕ BLOCKED",
        "todo": "○ TODO",
    }

    for column in columns:
        tasks_in_column = [t for t in state.tasks if t.column == column]
        if tasks_in_column:
            print(f"\n  {column_labels[column]}")
            for task in tasks_in_column:
                print(format_task(task))

    # Show done count
    done_count = len([t for t in state.tasks if t.column == "done"])
    if done_count > 0:
        print(f"\n  ({done_count} completed task(s) not shown)")

    if not state.tasks:
        print("  No tasks")


def display_inbox_section(state: State) -> None:
    """Display inbox section.

    Args:
        state: Current Commander state
    """
    print("\n  INBOX")
    print("  " + "-" * 56)

    if not state.inbox:
        print("  Inbox empty")
    else:
        for item in state.inbox:
            print(format_inbox_item(item))


def compute_next_action(state: State, state_mgr: StateManager) -> dict:
    """Compute the next action using rule engine.

    Args:
        state: Current Commander state
        state_mgr: StateManager instance

    Returns:
        Dictionary with 'action', 'why', and 'done' keys
    """
    # Rule engine priority (from HARNESS-018-H acceptance criteria):
    # clean → tests → finish → focus → start → tasks

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


def display_next_action(state: State, state_mgr: StateManager) -> None:
    """Display the next action recommendation.

    Args:
        state: Current Commander state
        state_mgr: StateManager instance
    """
    print("\n  NEXT ACTION")
    print("  " + "-" * 56)

    next_info = compute_next_action(state, state_mgr)

    print(f"\n  → {next_info['action']}")
    print(f"\n  Why: {next_info['why']}")
    print(f"  Done: {next_info['done']}")


def display_observer_mode() -> None:
    """Display observer mode message."""
    print("\n" + "!" * 60)
    print("  OBSERVER MODE")
    print("!" * 60)
    print("\n  Another controller session is active.")
    print("  You are in read-only observer mode.")
    print("  Use 'c-harness status' to see controller info.")
    print("!" * 60)
