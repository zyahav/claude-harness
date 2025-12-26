"""
Progress Tracking Utilities
===========================

Functions for tracking and displaying progress of the autonomous coding agent.
"""

import json
from pathlib import Path
from typing import Optional


def count_passing_tests(project_dir: Path, handoff_path: Optional[Path] = None) -> tuple[int, int]:
    """
    Count passing and total tests in handoff.json.

    Args:
        project_dir: Directory containing handoff.json (fallback if handoff_path not provided)
        handoff_path: Optional explicit path to handoff.json

    Returns:
        (passing_count, total_count)
    """
    tests_file = handoff_path if handoff_path else project_dir / "handoff.json"

    if not tests_file.exists():
        return 0, 0

    try:
        with open(tests_file, "r") as f:
            data = json.load(f)
        
        # Support both old format (list) and new format (object with tasks array)
        if isinstance(data, list):
            tests = data
        else:
            tests = data.get("tasks", [])

        total = len(tests)
        passing = sum(1 for test in tests if test.get("passes", False))

        return passing, total
    except (json.JSONDecodeError, IOError):
        return 0, 0


def print_session_header(session_num: int, is_initializer: bool) -> None:
    """Print a formatted header for the session."""
    session_type = "INITIALIZER" if is_initializer else "CODING AGENT"

    print("\n" + "=" * 70)
    print(f"  SESSION {session_num}: {session_type}")
    print("=" * 70)
    print()


def print_progress_summary(project_dir: Path, handoff_path: Optional[Path] = None) -> None:
    """Print a summary of current progress."""
    passing, total = count_passing_tests(project_dir, handoff_path)

    if total > 0:
        percentage = (passing / total) * 100
        print(f"\nProgress: {passing}/{total} tests passing ({percentage:.1f}%)")
    else:
        print("\nProgress: handoff.json not yet created")
