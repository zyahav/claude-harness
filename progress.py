"""
Progress Tracking Utilities
===========================

Functions for tracking and displaying progress of the autonomous coding agent.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def count_passing_tests(project_dir: Path) -> tuple[int, int]:
    """
    Count passing and total tests in handoff.json.

    Args:
        project_dir: Directory containing handoff.json

    Returns:
        (passing_count, total_count)
    """
    tests_file = project_dir / "handoff.json"

    if not tests_file.exists():
        return 0, 0

    try:
        with open(tests_file, "r") as f:
            data = json.load(f)

        # Handle both flat array and wrapped format
        if isinstance(data, list):
            tests = data
        elif isinstance(data, dict) and "tasks" in data:
            tests = data["tasks"]
        else:
            return 0, 0

        total = len(tests)
        passing = sum(1 for test in tests if test.get("passes", False))

        return passing, total
    except (json.JSONDecodeError, IOError):
        return 0, 0


def print_session_header(session_num: int, is_initializer: bool) -> None:
    """Print a formatted header for the session."""
    session_type = "INITIALIZER" if is_initializer else "CODING AGENT"

    logger.info("")
    logger.info("=" * 70)
    logger.info(f"  SESSION {session_num}: {session_type}")
    logger.info("=" * 70)
    logger.info("")


def print_progress_summary(project_dir: Path) -> None:
    """Print a summary of current progress."""
    passing, total = count_passing_tests(project_dir)

    if total > 0:
        percentage = (passing / total) * 100
        logger.info(f"Progress: {passing}/{total} tests passing ({percentage:.1f}%)")
    else:
        logger.info("Progress: handoff.json not yet created")
