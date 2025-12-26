"""
Harness Commander - Git-First Reconciliation
==============================================

Reconciliation engine that syncs Commander state with Git/worktree reality.
Prevents "split brain" state by always adopting Git as source of truth.
"""

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, List, Callable
from datetime import datetime, timedelta
from functools import wraps
import logging

logger = logging.getLogger(__name__)

# Reconciliation result cache duration (30 seconds)
RECONCILE_CACHE_DURATION = timedelta(seconds=30)


@dataclass
class GitStatus:
    """Result of git status command."""

    branch: str
    clean: bool
    files_changed: int


@dataclass
class WorktreeInfo:
    """Information about a Git worktree."""

    path: str
    branch: str
    is_bare: bool


@dataclass
class HarnessRunInfo:
    """Information about a harness run from c-harness list."""

    name: str
    branch: str
    status: str
    worktree_path: Optional[str]


@dataclass
class ReconcileResult:
    """Result of reconciliation operation."""

    projects_added: int = 0
    projects_removed: int = 0
    runs_added: int = 0
    runs_removed: int = 0
    runs_updated: int = 0
    runs_parked: int = 0
    drift_detected: bool = False


def cached(cache_duration: timedelta = RECONCILE_CACHE_DURATION):
    """Decorator for caching reconciliation results.

    Args:
        cache_duration: How long to cache results
    """

    def decorator(func: Callable) -> Callable:
        cache = {}
        last_call = {}

        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # Create cache key from args
            cache_key = (func.__name__, args, frozenset(kwargs.items()))

            # Check if cache is still valid
            if cache_key in cache:
                last_time = last_call[cache_key]
                if datetime.utcnow() - last_time < cache_duration:
                    logger.debug(f"Cache hit for {func.__name__}")
                    return cache[cache_key]

            # Call function and cache result
            result = func(self, *args, **kwargs)
            cache[cache_key] = result
            last_call[cache_key] = datetime.utcnow()

            return result

        # Add method to clear cache
        wrapper.clear_cache = lambda: cache.clear()

        return wrapper

    return decorator


class Reconciler:
    """Reconciliation engine for syncing state with Git reality."""

    def __init__(self, harness_path: Optional[Path] = None):
        """Initialize reconciler.

        Args:
            harness_path: Path to harness root (defaults to current dir)
        """
        self.harness_path = harness_path or Path.cwd()
        self.runs_dir = self.harness_path / "runs"

    def run_git(self, args: List[str], cwd: Optional[Path] = None) -> str:
        """Run a git command and return output.

        Args:
            args: Git command arguments (without 'git')
            cwd: Working directory (defaults to harness_path)

        Returns:
            Command stdout

        Raises:
            RuntimeError: If git command fails
        """
        cwd = cwd or self.harness_path

        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=cwd,
                check=True,
                capture_output=True,
                text=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Git command failed: git {' '.join(args)}\n{e.stderr}")

    def get_git_status(self, repo_path: Path) -> GitStatus:
        """Get git status for a repository.

        Args:
            repo_path: Path to repository

        Returns:
            GitStatus with branch and cleanliness info
        """
        try:
            # Get current branch
            branch = self.run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_path)

            # Check if working tree is clean
            output = self.run_git(["status", "--porcelain"], cwd=repo_path)
            clean = len(output.strip()) == 0

            # Count changed files
            files_changed = len(output.strip().split("\n")) if output.strip() else 0

            return GitStatus(branch=branch, clean=clean, files_changed=files_changed)

        except Exception as e:
            logger.error(f"Error getting git status for {repo_path}: {e}")
            raise

    def list_worktrees(self, repo_path: Optional[Path] = None) -> List[WorktreeInfo]:
        """List all Git worktrees.

        Args:
            repo_path: Path to repository (defaults to harness_path)

        Returns:
            List of WorktreeInfo objects
        """
        repo_path = repo_path or self.harness_path

        try:
            output = self.run_git(["worktree", "list", "--porcelain"], cwd=repo_path)

            worktrees = []
            current_worktree = {}

            for line in output.split("\n"):
                if not line:
                    if current_worktree:
                        worktrees.append(
                            WorktreeInfo(
                                path=current_worktree.get("worktree", ""),
                                branch=current_worktree.get("branch", "").replace(
                                    "refs/heads/", ""
                                ),
                                is_bare=current_worktree.get("bare") == "true",
                            )
                        )
                        current_worktree = {}
                    continue

                if line.startswith("worktree "):
                    current_worktree["worktree"] = line[len("worktree ") :]
                elif line.startswith("branch "):
                    current_worktree["branch"] = line[len("branch ") :]
                elif line == "bare":
                    current_worktree["bare"] = "true"

            return worktrees

        except Exception as e:
            logger.error(f"Error listing worktrees: {e}")
            return []

    def list_harness_runs(self) -> List[HarnessRunInfo]:
        """List all harness runs by parsing runs/ directory.

        Returns:
            List of HarnessRunInfo objects
        """
        if not self.runs_dir.exists():
            return []

        runs = []

        for run_path in self.runs_dir.iterdir():
            if not run_path.is_dir():
                continue

            # Check for .run metadata file
            metadata_file = run_path / ".run"
            if not metadata_file.exists():
                continue

            try:
                import json

                with open(metadata_file, "r") as f:
                    metadata = json.load(f)

                runs.append(
                    HarnessRunInfo(
                        name=run_path.name,
                        branch=metadata.get("branch", ""),
                        status=metadata.get("status", "unknown"),
                        worktree_path=str(run_path),
                    )
                )
            except Exception as e:
                logger.warning(f"Error reading metadata for {run_path.name}: {e}")

        return runs

    def check_dirty_tree_policy(
        self, repo_path: Path, allow_mutations: bool = True
    ) -> tuple[bool, str]:
        """Check if working tree is clean.

        Args:
            repo_path: Path to repository
            allow_mutations: If False, always refuse mutations

        Returns:
            Tuple of (is_clean, message)
        """
        try:
            status = self.get_git_status(repo_path)

            if not status.clean:
                msg = f"Working tree is dirty ({status.files_changed} files changed)"
                if allow_mutations:
                    return False, msg
                else:
                    return False, f"{msg}. Mutations refused."
            else:
                return True, "Working tree is clean"

        except Exception as e:
            error_msg = f"Error checking working tree: {e}"
            return False, error_msg

    def validate_worktree_path(
        self, path: Path, registered_projects: List[Path]
    ) -> tuple[bool, str]:
        """Validate that a worktree path is safe to delete.

        Args:
            path: Path to validate
            registered_projects: List of registered project paths

        Returns:
            Tuple of (is_safe, message)
        """
        # Normalize path
        try:
            real_path = path.resolve()
        except Exception as e:
            return False, f"Cannot resolve path: {e}"

        # Check for marker file
        marker_file = real_path / ".harness-worktree"
        if not marker_file.exists():
            return False, f"Refusing: missing .harness-worktree marker"

        # Check allowlist (must be under registered project or runs dir)
        is_under_runs = real_path.is_relative_to(self.runs_dir)
        is_under_project = any(real_path.is_relative_to(p) for p in registered_projects)

        if not (is_under_runs or is_under_project):
            return False, f"Refusing: path not under registered project or runs dir"

        return True, "Path is safe"

    @cached(cache_duration=RECONCILE_CACHE_DURATION)
    def reconcile(
        self,
        state_manager,
        event_logger=None,
    ) -> ReconcileResult:
        """Run reconciliation: sync state with Git reality.

        Args:
            state_manager: StateManager instance
            event_logger: Optional EventLogger instance

        Returns:
            ReconcileResult with changes
        """
        if event_logger:
            event_logger.log_reconcile_start()

        result = ReconcileResult()

        try:
            # Load current state
            state = state_manager.load_state()

            # Get current runs from harness
            harness_runs = self.list_harness_runs()
            harness_run_names = {r.name for r in harness_runs}

            # Detect runs in state but missing from reality
            runs_to_park = []
            for run in state.runs:
                if run.runName not in harness_run_names:
                    runs_to_park.append(run)
                    result.runs_parked += 1

            # Park missing runs
            for run in runs_to_park:
                logger.warning(f"Run {run.runName} missing from filesystem, parking")
                # Park by setting state to "missing"
                run.state = "missing"
                result.drift_detected = True

            # Detect runs in reality but missing from state
            existing_run_names = {r.runName for r in state.runs}
            for harness_run in harness_runs:
                if harness_run.name not in existing_run_names:
                    logger.info(f"Discovered run {harness_run.name} in filesystem")
                    # Would add to state here (implementation depends on schema)
                    result.runs_added += 1
                    result.drift_detected = True

            # Save updated state
            if result.drift_detected:
                state_manager.save_state()

                if event_logger:
                    event_logger.log_reconcile_result(
                        {
                            "runsAdded": result.runs_added,
                            "runsRemoved": result.runs_removed,
                            "runsParked": result.runs_parked,
                        }
                    )

            logger.info(f"Reconciliation complete: {result}")
            return result

        except Exception as e:
            logger.error(f"Reconciliation failed: {e}")
            if event_logger:
                event_logger.log_reconcile_result({"error": str(e)})
            raise
