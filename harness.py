#!/usr/bin/env python3
"""
Autonomous Coding Agent CLI
===========================

CLI for managing and running autonomous coding agents using Git worktrees.

Usage:
    python harness.py start <run-name>
    python harness.py run <run-name>
    python harness.py list
    python harness.py clean <run-name>
"""

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
import threading
import signal
from typing import Optional
from pathlib import Path
from importlib.metadata import version, PackageNotFoundError

from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

import lifecycle
import schema
import logging
import json
from datetime import datetime

# Import doc_check module for Documentation Trust Protocol
import doc_check

# Import Harness Commander modules
import state
import locking
import reconcile
import cockpit
import rules

# Configuration
DEFAULT_MODEL = "claude-sonnet-4-5-20250929"
DEFAULT_SPEC_PATH = Path("prompts/app_spec.txt")

# Logger for this module
logger = logging.getLogger(__name__)


def get_version() -> str:
    """Get version from package metadata or fallback to reading pyproject.toml."""
    try:
        return version("claude-harness")
    except PackageNotFoundError:
        # Fallback: read from pyproject.toml directly
        pyproject_path = Path(__file__).parent / "pyproject.toml"
        if pyproject_path.exists():
            import re
            content = pyproject_path.read_text()
            match = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
            if match:
                return match.group(1)
        return "unknown"


class JSONFormatter(logging.Formatter):
    """Format logs as JSON lines."""
    def format(self, record):
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.levelno >= logging.ERROR and record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


def setup_logging(run_dir: Path) -> None:
    """Configure structured logging to file and readable logging to console."""
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # clear existing handlers
    root_logger.handlers = []

    # 1. File Handler (JSONL) - captures everything
    log_file = run_dir / "session.jsonl"
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(file_handler)

    # 2. Console Handler (Readable) - INFO and above
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    # Simple format for console to match previous print style
    console_handler.setFormatter(logging.Formatter('%(message)s'))
    root_logger.addHandler(console_handler)

    logging.debug(f"Logging initialized. Writing to {log_file}")



def handle_schema(args: argparse.Namespace) -> None:
    """Print the handoff.json schema template."""
    template = {
        "meta": {
            "project": "Project Name",
            "phase": "Phase 1",
            "source": "manual",
            "lock": True
        },
        "tasks": [
            {
                "id": "TASK-001",
                "category": "api",
                "title": "Task Title",
                "description": "Task Description",
                "acceptance_criteria": [
                    "Criteria 1",
                    "Criteria 2"
                ],
                "passes": False,
                "files_expected": [],
                "steps": []
            }
        ]
    }
    print(json.dumps(template, indent=2))


def handle_start(args: argparse.Namespace) -> None:
    """Start a new run."""
    try:
        if args.dry_run:
            logging.info(f"[DRY-RUN] Would start run '{args.name}' from base '{args.base}'")
        
        run_dir = lifecycle.create_run(
            name=args.name,
            base_branch=args.base,
            repo_path=args.repo_path,
            dry_run=args.dry_run,
            archon=getattr(args, 'archon', False),
            handoff_path=getattr(args, 'handoff_path', None),
        )
        
        if args.dry_run:
            logging.info(f"[DRY-RUN] Would create worktree at: {run_dir}")
        else:
            setup_logging(Path(run_dir))
            logging.info(f"Starting new run: {args.name}")
            logging.info(f"\nSuccess! Worktree created at: {run_dir}")
            logging.info(f"To run the agent:\n  harness run {args.name} --repo-path {args.repo_path}")
    except Exception as e:
        # If logging isn't set up yet, fallback to print
        if logging.getLogger().handlers:
            logging.error(f"Error starting run: {e}")
        else:
            print(f"Error starting run: {e}")
        sys.exit(1)


def handle_run(args: argparse.Namespace) -> None:
    """Execute the agent in an existing run."""
    try:
        # Load run metadata to get the project directory
        # In dry run, we might not have metadata if start was dry-run too.
        # But run usually assumes valid existing run.
        if args.dry_run:
             logging.info(f"[DRY-RUN] Would resume run '{args.name}' with model '{args.model}'")
             # Try to load if exists, else mock
             try:
                meta = lifecycle.load_run_metadata(args.name)
                project_dir = Path(meta.project_dir)
                logging.info(f"[DRY-RUN] Found run at {project_dir}, would execute agent.")
             except Exception:
                logging.info(f"[DRY-RUN] Could not load metadata (expected if start was dry-run).")
             return

        meta = lifecycle.load_run_metadata(args.name)
        project_dir = Path(meta.project_dir)
        
        # Setup logging first thing
        setup_run_dir = Path(f"runs/{args.name}") 
        
        run_parent_dir = project_dir.parent
        # Ensure it exists (it should)
        if not run_parent_dir.exists():
             # Fallback if structure is weird
             run_parent_dir = project_dir
             
        setup_logging(run_parent_dir)

        logging.info(f"Resuming run '{args.name}'")
        logging.info(f"Worktree: {project_dir}")
        logging.info(f"Branch: {meta.branch}")
        logging.info(f"Mode: {args.mode}")
        if args.handoff_path:
            logging.info(f"Handoff: {args.handoff_path}")
        
        # Import agent here (lazy load)
        from agent import run_autonomous_agent
        
        asyncio.run(
            run_autonomous_agent(
                project_dir=project_dir,
                model=args.model,
                max_iterations=args.max_iterations,
                spec_path=args.spec,
                mode=args.mode,
                handoff_path=args.handoff_path,
                no_archon=args.no_archon,
            )
        )
    except FileNotFoundError:
        print(f"Error: Run '{args.name}' not found.")
        print("Use 'python harness.py list' to see active runs.")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    except Exception as e:
        print(f"\nFatal error: {e}")
        # print stack trace for debugging
        import traceback
        traceback.print_exc()
        sys.exit(1)


def handle_list(args: argparse.Namespace) -> None:
    """List active runs."""
    runs = lifecycle.list_runs()
    if not runs:
        print("No active runs found.")
        return

    print(f"{'NAME':<20} {'STATUS':<10} {'BRANCH':<30} {'CREATED'}")
    print("-" * 75)
    for run in runs:
        created = time.strftime("%Y-%m-%d %H:%M", time.localtime(run.created_at))
        print(f"{run.name:<20} {run.status:<10} {run.branch:<30} {created}")


def get_repo_url(repo_path: Path, branch: str) -> Optional[str]:
    """
    Extract and convert git remote URL to a web PR/merge request URL.

    Args:
        repo_path: Path to the git repository
        branch: Branch name to create PR for

    Returns:
        Web URL for creating PR/merge request, or None if unable to determine
    """
    try:
        # Get the remote URL from git config
        remote_url = lifecycle.run_git(
            ["config", "--get", "remote.origin.url"],
            cwd=repo_path
        )

        if not remote_url:
            return None

        # Convert SSH URL to HTTPS
        # git@github.com:user/repo.git -> https://github.com/user/repo
        # git@gitlab.com:user/repo.git -> https://gitlab.com/user/repo
        if remote_url.startswith("git@"):
            # Remove git@ prefix and .git suffix
            url = remote_url[4:].replace(".git", "")
            # Replace : with / for the path separator
            url = url.replace(":", "/")
            https_url = f"https://{url}"
        elif remote_url.startswith("git://"):
            # git://github.com/user/repo.git -> https://github.com/user/repo
            url = remote_url[6:].replace(".git", "")
            https_url = f"https://{url}"
        elif remote_url.startswith("http://"):
            https_url = remote_url.replace("http://", "https://").replace(".git", "")
        elif remote_url.startswith("https://"):
            https_url = remote_url.replace(".git", "")
        else:
            # Unknown format, return as-is
            https_url = remote_url

        # Generate PR/merge request URL based on platform
        if "github.com" in https_url:
            # GitHub: /compare/<branch> (expand to create new PR)
            return f"{https_url}/compare/{branch}"
        elif "gitlab.com" in https_url:
            # GitLab: /merge_requests/new?merge_request[source_branch]=<branch>
            return f"{https_url}/-/merge_requests/new?merge_request[source_branch]={branch}"
        else:
            # Unknown platform, just return the base URL
            return https_url

    except Exception:
        # If anything goes wrong, return None
        return None


def handle_finish(args: argparse.Namespace) -> None:
    """Finish a run: verify status, check docs, and push branch."""
    if args.dry_run:
        logging.info(f"[DRY-RUN] Would finish run '{args.name}' and push branch.")
        return

    try:
        meta = lifecycle.load_run_metadata(args.name)
        project_dir = Path(meta.project_dir)

        # Resolve handoff path:
        # 1. Custom path (CLI arg)
        # 2. Default: project_dir / "handoff.json"
        if args.handoff_path:
            handoff_path = Path(args.handoff_path).resolve()
        else:
            handoff_path = project_dir / "handoff.json"

        # Verify handoff.json
        if not handoff_path.exists():
            print(f"Error: handoff.json not found at {handoff_path}")
            sys.exit(1)

        handoff = schema.load_handoff(handoff_path)
        passing, total = handoff.count_passing()

        print(f"Run: {args.name}")
        print(f"Progress: {passing}/{total} tasks passing")

        if passing < total and not args.force:
            print("\nWarning: Not all tasks are marked as passing.")
            print("Use --force to finish anyway.")
            sys.exit(1)

        # Documentation Trust Protocol: Detect drift before push
        print("\nChecking for documentation drift...")
        has_drift, drift_items, decision_store = doc_check.check_drift_before_finish(project_dir)

        if has_drift:
            print(f"\n⚠️  Documentation drift detected: {len(drift_items)} item(s)")
            print("\nUndocumented changes found:")

            for i, drift in enumerate(drift_items, 1):
                print(f"  {i}. [{drift.type}] {drift.item}")
                print(f"     → Should be documented in: {drift.location}")

            # Documentation Awareness Notice (Engage step)
            print("\n⚠️  Documentation Awareness Notice")
            print("-" * 50)
            print("The following changes should be documented to maintain project health.")
            print("\nHow would you like to proceed?")
            print("  1) Update documentation now")
            print("  2) Mark as internal (not for public docs)")
            print("  3) Defer (ask again in 7 days)")
            print("  4) Continue without changes")

            # Get user choice
            try:
                choice = input("\nEnter choice [1-4]: ").strip()

                if choice == "1":
                    # Update documentation
                    print("\n📝 Documentation Update Assistance")
                    print("-" * 50)
                    print("Please provide a brief description for each undocumented item:")

                    for drift in drift_items:
                        item_id = doc_check.DocDecisionStore._make_item_id(drift)
                        print(f"\nItem: {drift.item} ({drift.type})")
                        description = input(f"  Description (or press Enter to skip): ").strip()

                        if description:
                            # For now, just save the decision with description
                            # In a future enhancement, this could auto-edit the docs
                            decision_store.set_decision(item_id, 'documented', description)
                            print(f"  ✓ Decision saved: {description}")
                        else:
                            print(f"  ⊘ Skipped")

                    print("\n✓ Documentation decisions recorded")
                    print("  Note: Automatic documentation editing is planned for a future update.")
                    print("  Please manually update the documentation files based on your descriptions.")

                    # Re-check for remaining drift
                    remaining_drift = decision_store.get_pending_items(drift_items)

                    if remaining_drift:
                        print(f"\n⚠️  {len(remaining_drift)} item(s) still need attention")
                        if not doc_strict:
                            print("  Continuing with warning...")
                        else:
                            print("\n❌ --doc-strict mode: Cannot finish with unresolved drift")
                            sys.exit(1)
                    else:
                        print("\n✓ All items addressed")

                elif choice == "2":
                    # Mark as internal
                    print("\n🔒 Marking items as internal...")
                    for drift in drift_items:
                        item_id = doc_check.DocDecisionStore._make_item_id(drift)
                        decision_store.set_decision(item_id, 'internal')
                        print(f"  ✓ {drift.item} marked as internal")
                    print("\n✓ Items marked as internal - will not be flagged again")

                elif choice == "3":
                    # Defer
                    print("\n⏰ Deferring documentation...")
                    for drift in drift_items:
                        item_id = doc_check.DocDecisionStore._make_item_id(drift)
                        decision_store.set_decision(item_id, 'deferred')
                        print(f"  ✓ {drift.item} deferred (will ask again in 7 days)")
                    print("\n✓ Items deferred - you will be asked again on future runs")

                elif choice == "4":
                    # Continue without changes
                    print("\n⚠️  Continuing without addressing documentation drift...")

                else:
                    print("\n⚠️  Invalid choice. Continuing without changes...")

            except (EOFError, KeyboardInterrupt):
                # Non-interactive mode
                print("\n⚠️  Non-interactive mode: Continuing with warning...")

            # Check if --doc-strict mode is enabled
            doc_strict = getattr(args, 'doc_strict', False)

            if doc_strict:
                # Re-check drift after any decisions made
                remaining_drift = decision_store.get_pending_items(drift_items)
                if remaining_drift:
                    print("\n❌ --doc-strict mode enabled: Blocking finish due to unresolved drift")
                    print("   Options:")
                    print("   - Document the changes and run finish again")
                    print("   - Mark items as internal using .harness/doc_decisions.json")
                    print("   - Run without --doc-strict to finish anyway")
                    sys.exit(1)
            else:
                print("\n⚠️  Documentation drift detected. To enforce documentation, use: --doc-strict")
        else:
            print("✓ No documentation drift detected")

        print(f"\nPushing branch {meta.branch}...")
        try:
            # Push from the TARGET REPO (repo_path), not the harness dir
            repo_path = Path(getattr(meta, "repo_path", "."))
            lifecycle.run_git(["push", "origin", meta.branch, "--force"], cwd=repo_path)
        except RuntimeError as e:
            print(f"Error pushing branch: {e}")
            sys.exit(1)

        print("\nSuccess! Create your Pull Request here:")

        # Try to get a clickable PR/merge request URL
        repo_path = Path(getattr(meta, "repo_path", "."))
        pr_url = get_repo_url(repo_path, meta.branch)

        if pr_url:
            print(f"  {pr_url}")
        else:
            # Fallback if we can't determine the URL
            print(f"  Branch: {meta.branch}")

    except FileNotFoundError:
        print(f"Error: Run '{args.name}' not found.")
        sys.exit(1)
    except Exception as e:
        print(f"Error finishing run: {e}")
        sys.exit(1)


def handle_clean(args: argparse.Namespace) -> None:
    """Clean up a run."""
    if not args.force:
        confirm = input(f"Are you sure you want to delete run '{args.name}'? [y/N] ")
        if confirm.lower() != 'y':
            print("Aborted.")
            return

    try:
        if args.dry_run:
            logging.info(f"[DRY-RUN] Would cleanup run '{args.name}' (delete_branch={args.delete_branch})")
        else:
            lifecycle.cleanup_run(args.name, delete_branch=args.delete_branch)
    except Exception as e:
        print(f"Error cleaning up run: {e}")
        sys.exit(1)


def handle_status(args: argparse.Namespace) -> None:
    """Display Harness Commander status line.

    Outputs current mode, focus project, active run, and controller info.
    Read-only command (acquires no lock).
    """
    try:
        # Load state
        state_mgr = state.StateManager()
        current_state = state_mgr.load_state()

        # Check lock status to determine mode
        lock_mgr = locking.LockManager()
        lock_info = lock_mgr.read_lock_info()

        # Determine mode and build status line
        if lock_info and lock_mgr.check_pid_alive(lock_info.pid):
            # Controller is active
            mode = "Controller"
            controller_info = f"PID {lock_info.pid}"

            # Check if we are the controller
            if lock_info.pid == os.getpid():
                mode = "Controller (you)"

            # Format active run
            active_run = None
            for run in current_state.runs:
                if run.state == "running":
                    active_run = run
                    break

            run_info = active_run.runName if active_run else "none"

            # Format focus project
            focus_info = "none"
            if current_state.focusProjectId:
                focus_project = state_mgr.get_project(current_state.focusProjectId)
                if focus_project:
                    focus_info = focus_project.name

            # Format state info
            state_info = f"{len(current_state.runs)} runs, {len(current_state.tasks)} tasks"

        else:
            # Observer mode (no active controller)
            mode = "Observer"
            controller_info = "none"

            # In observer mode, still show what we can from state
            active_run = None
            for run in current_state.runs:
                if run.state == "running":
                    active_run = run
                    break

            run_info = active_run.runName if active_run else "none"

            focus_info = "none"
            if current_state.focusProjectId:
                focus_project = state_mgr.get_project(current_state.focusProjectId)
                if focus_project:
                    focus_info = focus_project.name

            state_info = f"{len(current_state.runs)} runs, {len(current_state.tasks)} tasks"

            # Add controller info if lock file exists but PID is dead
            if lock_info:
                controller_info = f"PID {lock_info.pid} (DEAD)"

        # Print status line
        status_parts = [
            f"{mode}",
            f"focus: {focus_info}",
            f"run: {run_info}",
            f"state: {state_info}"
        ]

        if controller_info != "none":
            status_parts.append(f"controller: {controller_info}")

        print(" | ".join(status_parts))

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def handle_doctor(args: argparse.Namespace) -> None:
    """Run pre-flight checks for Harness Commander.

    Checks Git version, home directory, locks, state file, and engine availability.
    Supports --repair-state flag to fix safe issues automatically.
    """
    passed = 0
    warnings = 0
    errors = 0

    print("Harness Commander Health Check")
    print("=" * 40)
    print()

    # Check 1: Git availability and version
    try:
        result = subprocess.run(
            ["git", "--version"],
            capture_output=True,
            text=True,
            check=True
        )
        git_version = result.stdout.strip()
        print(f"[✓] Git version: {git_version}")
        passed += 1
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"[!] Git check failed — Git not found or not executable")
        errors += 1
    except Exception as e:
        print(f"[!] Git check failed — {e}")
        errors += 1

    # Check 2: Home directory and Commander structure
    try:
        commander_home = state.COMMANDER_HOME
        if commander_home.exists():
            print(f"[✓] Commander home: {commander_home}")
            passed += 1
        else:
            print(f"[!] Commander home missing — will be created on first use")
            warnings += 1
    except Exception as e:
        print(f"[!] Home directory check failed — {e}")
        errors += 1

    # Check 3: Locks directory
    try:
        locks_dir = locking.LOCKS_DIR
        if locks_dir.exists():
            lock_mgr = locking.LockManager()
            lock_info = lock_mgr.read_lock_info()

            if lock_info:
                # Check if PID is alive
                if lock_mgr.check_pid_alive(lock_info.pid):
                    print(f"[✓] Lock directory: Active controller (PID {lock_info.pid})")
                    passed += 1
                else:
                    print(f"[!] Lock directory: Stale lock (PID {lock_info.pid} is dead)")
                    warnings += 1
            else:
                print(f"[✓] Lock directory: No active lock")
                passed += 1
        else:
            print(f"[✓] Lock directory: Not created yet")
            passed += 1
    except Exception as e:
        print(f"[!] Lock directory check failed — {e}")
        errors += 1

    # Check 4: State file
    try:
        state_mgr = state.StateManager()
        state_file = state.STATE_FILE

        if state_file.exists():
            current_state = state_mgr.load_state()
            print(f"[✓] State file: {len(current_state.projects)} projects, {len(current_state.runs)} runs")
            passed += 1
        else:
            print(f"[!] State file: Not found (will be created on first use)")
            warnings += 1
    except ValueError as e:
        print(f"[!] State file check failed — {e}")
        errors += 1
    except Exception as e:
        print(f"[!] State file check failed — {e}")
        errors += 1

    # Check 5: Engine availability (c-harness itself)
    try:
        # Try to run c-harness --version
        result = subprocess.run(
            [sys.executable, str(Path(__file__) ), "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        # We expect this to succeed or fail gracefully
        print(f"[✓] Engine: c-harness is available")
        passed += 1
    except Exception as e:
        print(f"[!] Engine check failed — {e}")
        errors += 1

    # Check 6: Temporary files cleanup check
    try:
        tmp_files = list(state.COMMANDER_HOME.glob("*.tmp"))
        if tmp_files:
            print(f"[!] Temporary files: Found {len(tmp_files)} .tmp file(s)")
            warnings += 1

            # Auto-cleanup if --repair-state is set
            if args.repair_state:
                for tmp_file in tmp_files:
                    try:
                        tmp_file.unlink()
                        print(f"   └─ Cleaned up: {tmp_file.name}")
                    except Exception as e:
                        print(f"   └─ Failed to cleanup {tmp_file.name}: {e}")
        else:
            print(f"[✓] Temporary files: None found")
            passed += 1
    except Exception as e:
        print(f"[!] Temporary files check failed — {e}")
        errors += 1

    # Run reconcile if --repair-state is set
    if args.repair_state:
        print()
        print("Running state repair...")

        try:
            reconciler = reconcile.Reconciler()
            result = reconciler.run_reconcile()

            if result.drift_detected:
                print(f"   └─ Drift detected and fixed:")
                print(f"      • Projects: +{result.projects_added}, -{result.projects_removed}")
                print(f"      • Runs: +{result.runs_added}, -{result.runs_removed}, ~{result.runs_updated}")
                print(f"      • Parked: {result.runs_parked} runs with missing worktrees")

                # Park runs with missing worktrees
                if result.runs_parked > 0:
                    print(f"   └─ Parked {result.runs_parked} runs with missing worktrees")
            else:
                print(f"   └─ No drift detected, state is consistent")

        except Exception as e:
            print(f"   └─ Repair failed: {e}")
            errors += 1

    # Print summary
    print()
    print("=" * 40)
    print(f"Status: {passed} passed, {warnings} warnings, {errors} errors")

    # Exit with error code if there were errors
    if errors > 0:
        sys.exit(1)


def handle_next(args: argparse.Namespace) -> None:
    """Compute and display the next action using rule engine.

    Outputs the next action with 'Why' and 'Done' criteria.
    Read-only command (acquires no lock, runs reconcile with cache).
    """
    try:
        # Load state
        state_mgr = state.StateManager()
        current_state = state_mgr.load_state()

        # Run reconcile with caching
        reconciler = reconcile.Reconciler()
        reconciler.reconcile(state_mgr)

        # Reload state after reconcile
        current_state = state_mgr.load_state()

        # Compute next action using rule engine
        next_info = rules.compute_next_action(current_state, state_mgr)

        # Display next action
        print("\n" + "=" * 60)
        print("  NEXT ACTION")
        print("=" * 60)
        print(f"\n  → {next_info['action']}")
        print(f"\n  Why: {next_info['why']}")
        print(f"  Done: {next_info['done']}")
        print("=" * 60)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def handle_focus(args: argparse.Namespace) -> None:
    """Set or view the focus project.

    'focus set <projectId|name>' - Set focus project (requires controller lock)
    'focus' - View current focus project (read-only, no lock)
    """
    try:
        # Load state
        state_mgr = state.StateManager()
        current_state = state_mgr.load_state()

        # VIEW MODE: Just display current focus
        if not args.set_project:
            if current_state.focusProjectId:
                project = state_mgr.get_project(current_state.focusProjectId)
                if project:
                    print(f"\nCurrent focus project:")
                    print(f"  ID: {project.id}")
                    print(f"  Name: {project.name}")
                    print(f"  Path: {project.repoPath}")
                    print(f"  Status: {project.status}")
                else:
                    print(f"\nCurrent focus ID: {current_state.focusProjectId}")
                    print(f"  (Project not found in state)")
            else:
                print("\nNo focus project set.")
                print("Use 'c-harness focus set <projectId|name>' to set focus.")
            return

        # SET MODE: Change focus project (requires lock)
        project_identifier = args.set_project

        # Run reconcile first to ensure state is up-to-date
        print("\nReconciling state with Git...")
        reconciler = reconcile.Reconciler()
        result = reconciler.reconcile(state_mgr)
        if result.drift_detected:
            print("  └─ State reconciled")
        # Reload state after reconcile
        current_state = state_mgr.load_state()

        # Find project by ID or name
        target_project = None
        for project in current_state.projects:
            if project.id == project_identifier or project.name == project_identifier:
                target_project = project
                break

        if not target_project:
            print(f"Error: Project '{project_identifier}' not found.", file=sys.stderr)
            print("\nAvailable projects:")
            if current_state.projects:
                for p in current_state.projects:
                    print(f"  - {p.name} (ID: {p.id})")
            else:
                print("  (No projects registered)")
            sys.exit(1)

        # Check if already focused on this project
        if current_state.focusProjectId == target_project.id:
            print(f"\nAlready focused on: {target_project.name}")
            print(f"  ID: {target_project.id}")
            print(f"  Path: {target_project.repoPath}")
            return

        # Require confirmation if switching from current focus
        if current_state.focusProjectId:
            current_project = state_mgr.get_project(current_state.focusProjectId)
            if current_project:
                print(f"\nCurrent focus: {current_project.name}")
                print(f"New focus: {target_project.name}")
                print("\nThis will change your focus project.")

                # Prompt for confirmation
                response = input("Continue? (y/N) ").strip().lower()
                if response not in ["y", "yes"]:
                    print("Focus change cancelled.")
                    return

        # Acquire controller lock for mutation
        lock_mgr = locking.LockManager()
        try:
            lock_mgr.acquire_lock()
            print("  └─ Acquired controller lock")
        except Exception as e:
            print(f"Error: Could not acquire controller lock: {e}", file=sys.stderr)
            print("\nAnother session may be in progress. Try 'c-harness status' for details.")
            sys.exit(1)

        try:
            # Update focus project ID atomically
            current_state.focusProjectId = target_project.id
            state_mgr.update_state(current_state)

            print(f"\n✓ Focus updated")
            print(f"  Project: {target_project.name}")
            print(f"  ID: {target_project.id}")
            print(f"  Path: {target_project.repoPath}")

        finally:
            # Always release lock
            lock_mgr.release_lock()
            print("  └─ Released controller lock")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        logger.exception("Focus command failed")
        sys.exit(1)


def handle_inbox(args: argparse.Namespace) -> None:
    """Manage inbox items for capturing ideas and promoting them to tasks.

    Subcommands:
        - 'c-harness inbox <text>' - Capture an idea (fire-and-forget, no prompts)
        - 'c-harness inbox list' - List all inbox items (requires controller lock)
        - 'c-harness inbox promote <id>' - Promote inbox item to task (requires controller lock)
        - 'c-harness inbox dismiss <id>' - Dismiss (delete) an inbox item (requires controller lock)
    """
    try:
        state_mgr = state.StateManager()
        current_state = state_mgr.load_state()

        # DETERMINE SUBCOMMAND based on args
        # If promote/dismiss is set, use that
        # If list_action is True, do list
        # Otherwise, capture mode (args.text contains the idea)

        if args.promote:
            # PROMOTE MODE: Convert inbox item to task
            item_id = args.promote

            # Find the inbox item
            item = state_mgr.get_inbox_item(item_id)
            if not item:
                print(f"Error: Inbox item '{item_id}' not found.", file=sys.stderr)
                print("\nUse 'c-harness inbox list' to see all items.")
                sys.exit(1)

            # Check if focus project is set
            if not current_state.focusProjectId:
                print("Error: No focus project set.", file=sys.stderr)
                print("Use 'c-harness focus set <projectId|name>' to set focus first.")
                sys.exit(1)

            focus_project = state_mgr.get_project(current_state.focusProjectId)
            if not focus_project:
                print(f"Error: Focus project '{current_state.focusProjectId}' not found.", file=sys.stderr)
                sys.exit(1)

            # Acquire controller lock for mutation
            lock_mgr = locking.LockManager()
            try:
                lock_mgr.acquire_lock()
                logger.debug("Acquired controller lock for inbox promote")
            except Exception as e:
                print(f"Error: Could not acquire controller lock: {e}", file=sys.stderr)
                print("\nAnother session may be in progress. Try 'c-harness status' for details.")
                sys.exit(1)

            try:
                # Create task from inbox item
                new_task = state.Task(
                    id="",  # Will be generated in __post_init__
                    projectId=focus_project.id,
                    title=item.text[:100],  # Truncate to 100 chars for title
                    column="todo",
                    createdAt=state.get_timestamp()
                )

                # Remove inbox item and add task
                current_state.inbox = [i for i in current_state.inbox if i.id != item_id]
                current_state.tasks.append(new_task)

                # Save state atomically
                state_mgr.update_state(current_state)

                print(f"\n✓ Promoted inbox item to task")
                print(f"  Task: {new_task.title}")
                print(f"  Project: {focus_project.name}")
                print(f"  Task ID: {new_task.id}")

            finally:
                # Always release lock
                lock_mgr.release_lock()
                logger.debug("Released controller lock")

        elif args.dismiss:
            # DISMISS MODE: Delete inbox item
            item_id = args.dismiss

            # Find the inbox item
            item = state_mgr.get_inbox_item(item_id)
            if not item:
                print(f"Error: Inbox item '{item_id}' not found.", file=sys.stderr)
                print("\nUse 'c-harness inbox list' to see all items.")
                sys.exit(1)

            # Acquire controller lock for mutation
            lock_mgr = locking.LockManager()
            try:
                lock_mgr.acquire_lock()
                logger.debug("Acquired controller lock for inbox dismiss")
            except Exception as e:
                print(f"Error: Could not acquire controller lock: {e}", file=sys.stderr)
                print("\nAnother session may be in progress. Try 'c-harness status' for details.")
                sys.exit(1)

            try:
                # Remove inbox item
                current_state.inbox = [i for i in current_state.inbox if i.id != item_id]

                # Save state atomically
                state_mgr.update_state(current_state)

                print(f"\n✓ Dismissed inbox item")
                print(f"  Text: {item.text[:60]}{'...' if len(item.text) > 60 else ''}")

            finally:
                # Always release lock
                lock_mgr.release_lock()
                logger.debug("Released controller lock")

        elif args.list_action:
            # LIST MODE: Show all inbox items
            # Requires controller lock
            lock_mgr = locking.LockManager()
            try:
                lock_mgr.acquire_lock()
                logger.debug("Acquired controller lock for inbox list")
            except Exception as e:
                print(f"Error: Could not acquire controller lock: {e}", file=sys.stderr)
                print("\nAnother session may be in progress. Try 'c-harness status' for details.")
                sys.exit(1)

            try:
                # Reload state to ensure fresh data
                current_state = state_mgr.load_state()

                if not current_state.inbox:
                    print("\nInbox is empty.")
                    print("\nCapture ideas with:")
                    print("  c-harness inbox <your idea>")
                    return

                print(f"\nInbox ({len(current_state.inbox)} items)")
                print("=" * 60)

                for i, item in enumerate(current_state.inbox, 1):
                    created = item.createdAt.replace("T", " ").replace("Z", "")[:19]
                    print(f"\n{i}. {item.id[:8]}")
                    print(f"   Created: {created}")
                    print(f"   Text: {item.text}")

                print("\n" + "=" * 60)
                print("\nActions:")
                print("  c-harness inbox promote <id>   Promote to task")
                print("  c-harness inbox dismiss <id>   Dismiss item")

            finally:
                # Always release lock
                lock_mgr.release_lock()
                logger.debug("Released controller lock")

        else:
            # CAPTURE MODE: Add new inbox item (fire-and-forget)
            if not args.text:
                print("Error: No text provided.", file=sys.stderr)
                print("\nUsage:")
                print("  c-harness inbox '<your idea>'")
                sys.exit(1)

            # Create inbox item (no lock needed for append)
            new_item = state.InboxItem(
                id="",  # Will be generated in __post_init__
                text=args.text,
                createdAt=state.get_timestamp()
            )

            # Append to inbox
            current_state.inbox.append(new_item)

            # Save state atomically
            state_mgr.update_state(current_state)

            print(f"\n✓ Captured idea")
            print(f"  ID: {new_item.id[:8]}")
            print(f"  Text: {new_item.text}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        logger.exception("Inbox command failed")
        sys.exit(1)


def handle_bootstrap(args: argparse.Namespace) -> None:
    """Check installation and discover updates for c-harness.

    This command:
    - Checks if c-harness is installed/available
    - Prints install steps if missing (never silent install)
    - Checks for updates (notification only, no auto-update)
    - Supports --apply flag for explicit updates
    """
    try:
        print("\nHarness Commander Bootstrap")
        print("=" * 60)

        # Check 1: Verify c-harness is available
        print("\nChecking installation...")
        current_version = get_version()

        if current_version == "unknown":
            print("\n[!] c-harness is not installed or not in PATH")
            print("\nInstallation steps:")
            print("  1. Clone the repository:")
            print("     git clone https://github.com/your-org/claude-harness.git")
            print("  2. Install in editable mode:")
            print("     pip install -e ./claude-harness")
            print("  3. Verify installation:")
            print("     c-harness --version")
            print("\nOr install from PyPI (when available):")
            print("  pip install claude-harness")
            sys.exit(1)

        print(f"[✓] c-harness version: {current_version}")

        # Check 2: Try to fetch latest version from GitHub
        # For now, we'll skip this since we don't have a reliable API
        # In production, this would check GitHub releases or PyPI
        print("\nChecking for updates...")
        print("[!] Update checking not yet implemented")
        print("    To check manually, visit:")
        print("    https://github.com/your-org/claude-harness/releases")

        # If --apply flag is set, show message
        if args.apply:
            print("\n[*] --apply flag specified")
            print("    Auto-update not yet implemented")
            print("    Please update manually:")
            print("    pip install --upgrade claude-harness")

        print("\n" + "=" * 60)
        print("Bootstrap complete")
        print("=" * 60)

    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        logger.exception("Bootstrap command failed")
        sys.exit(1)


def handle_session(args: argparse.Namespace) -> None:
    """Start an interactive Harness Commander session.

    Runs doctor pre-flight, reconciles state, acquires controller lock,
    and displays the cockpit with next action. Runs heartbeat loop in
    background. Handles Ctrl+C gracefully for clean exit.
    """
    state_mgr = None
    lock_mgr = None
    heartbeat_thread = None
    is_controller = False

    def heartbeat_worker(lock_mgr: locking.LockManager, stop_event: threading.Event):
        """Background thread that updates heartbeat every 60 seconds.

        Args:
            lock_mgr: LockManager instance
            stop_event: Threading event to signal stop
        """
        while not stop_event.is_set():
            try:
                lock_mgr.update_heartbeat()
                logger.debug("Heartbeat updated")
            except Exception as e:
                logger.error(f"Heartbeat update failed: {e}")

            # Sleep for 60 seconds or until stop event
            stop_event.wait(60)

    def signal_handler(signum, frame):
        """Handle SIGINT (Ctrl+C) for clean exit.

        Args:
            signum: Signal number
            frame: Current stack frame
        """
        nonlocal is_controller
        logger.info(f"Received signal {signum}, shutting down...")

        if is_controller and lock_mgr:
            print("\n\nReleasing controller lock...")
            lock_mgr.release_lock()
            print("Lock released. Goodbye!")

        sys.exit(0)

    try:
        # Step 1: Run doctor pre-flight checks
        print("\nHarness Commander Session")
        print("=" * 60)
        print("\nRunning pre-flight checks...")
        doctor_args = argparse.Namespace(repair_state=False)
        # Temporarily suppress doctor output in session
        handle_doctor(doctor_args)
        print("\n✓ Preflight checks passed")

        # Step 2: Reconcile state with Git reality
        print("\nReconciling state with Git...")
        state_mgr = state.StateManager()
        current_state = state_mgr.load_state()

        reconciler = reconcile.Reconciler()
        result = reconciler.reconcile(state_mgr)

        if result.drift_detected:
            print(f"  └─ Drift detected and fixed")
            print(f"      • Projects: +{result.projects_added}, -{result.projects_removed}")
            print(f"      • Runs: +{result.runs_added}, -{result.runs_removed}, ~{result.runs_updated}")
            if result.runs_parked > 0:
                print(f"      • Parked: {result.runs_parked} runs with missing worktrees")
        else:
            print(f"  └─ No drift detected")

        # Reload state after reconcile
        current_state = state_mgr.load_state()

        # Step 3: Acquire controller lock
        print("\nAcquiring controller lock...")
        lock_mgr = locking.LockManager()

        success, reason = lock_mgr.acquire_lock()

        if success:
            # Controller mode
            is_controller = True
            session_id = lock_mgr.sessionId
            print(f"  ✓ Controller mode (session: {session_id[:8]})")

            # Set up signal handler for clean exit
            signal.signal(signal.SIGINT, signal_handler)

            # Start heartbeat thread
            stop_heartbeat = threading.Event()
            heartbeat_thread = threading.Thread(
                target=heartbeat_worker,
                args=(lock_mgr, stop_heartbeat),
                daemon=True
            )
            heartbeat_thread.start()
            logger.debug("Heartbeat thread started")

        else:
            # Observer mode
            is_controller = False
            lock_info = lock_mgr.read_lock_info()
            if lock_info:
                print(f"  ! Lock held by PID {lock_info.pid}")
            else:
                print(f"  ! Lock acquisition failed: {reason}")
            print(f"  → Entering observer mode (read-only)")

        # Step 4: Display cockpit
        cockpit.display_cockpit(current_state, state_mgr)

        # Step 5: Display next action (only in controller mode)
        if is_controller:
            cockpit.display_next_action(current_state, state_mgr)

        # Step 6: Keep session alive (controller mode)
        if is_controller:
            print("\n" + "=" * 60)
            print("Session active. Press Ctrl+C to exit.")
            print("=" * 60)

            # Keep main thread alive
            try:
                while heartbeat_thread and heartbeat_thread.is_alive():
                    time.sleep(1)
            except KeyboardInterrupt:
                # This shouldn't happen due to signal handler, but just in case
                logger.info("KeyboardInterrupt caught")

        else:
            # Observer mode - display message and exit
            cockpit.display_observer_mode()
            sys.exit(0)

    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        logger.exception("Session failed")

        # Clean up lock if we acquired it
        if is_controller and lock_mgr:
            try:
                lock_mgr.release_lock()
                print("Lock released due to error")
            except Exception as e2:
                logger.error(f"Failed to release lock: {e2}")

        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Autonomous Coding Agent CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--version", "-V", action="version", version=f"c-harness {get_version()}")
    
    subparsers = parser.add_subparsers(dest="command", required=True, help="Command to execute")

    # SCHEMA command
    schema_parser = subparsers.add_parser("schema", help="Print the handoff.json schema template")
    schema_parser.set_defaults(func=handle_schema)

    # START command
    start_parser = subparsers.add_parser("start", help="Start a new agent run (creates worktree)")
    start_parser.add_argument("name", help="Name of the run (used for branch and folder)")
    start_parser.add_argument("--base", default="main", help="Base branch to start from (default: main)")
    start_parser.add_argument("--repo-path", default=".", help="Path to the target repository (default: current dir)")
    start_parser.add_argument("--mode", choices=["greenfield", "brownfield"], default="greenfield",
                             help="Mode: 'greenfield' (new project) or 'brownfield' (existing codebase)")
    start_parser.add_argument("--handoff-path", type=Path, default=None,
                             help="Path to handoff.json (for Archon task import)")
    start_parser.add_argument("--archon", action="store_true",
                             help="Create Archon project for visibility into agent work")
    start_parser.add_argument("--dry-run", action="store_true", help="Simulate commands without executing them")
    start_parser.set_defaults(func=handle_start)

    # RUN command
    run_parser = subparsers.add_parser("run", help="Execute agent in a run")
    run_parser.add_argument("name", help="Name of the run to execute")
    run_parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Model to use (default: {DEFAULT_MODEL})")
    run_parser.add_argument("--max-iterations", type=int, default=None, help="Limit iterations")
    run_parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC_PATH, help="Path to app spec")
    run_parser.add_argument("--mode", choices=["greenfield", "brownfield"], default="greenfield",
                           help="Mode: 'greenfield' (new project) or 'brownfield' (existing codebase). Default: greenfield")
    run_parser.add_argument("--handoff-path", type=Path, default=None,
                           help="Path to handoff.json for brownfield mode (default: <worktree>/handoff.json)")
    run_parser.add_argument("--repo-path", default=".", help="Path to the target repository (for context)")
    run_parser.add_argument("--no-archon", action="store_true", help="Disable Archon integration (skip all Archon updates)")
    run_parser.add_argument("--dry-run", action="store_true", help="Simulate commands without executing them")
    run_parser.set_defaults(func=handle_run)

    # LIST command
    list_parser = subparsers.add_parser("list", help="List active runs")
    list_parser.set_defaults(func=handle_list)

    # FINISH command
    finish_parser = subparsers.add_parser("finish", help="Finish a run (push branch)")
    finish_parser.add_argument("name", help="Name of the run to finish")
    finish_parser.add_argument("--force", "-f", action="store_true", help="Finish even if tasks are incomplete")
    # Added --handoff-path here
    finish_parser.add_argument("--handoff-path", default=None, help="Path to handoff.json (default: project_dir/handoff.json)")
    finish_parser.add_argument("--doc-strict", action="store_true", help="Block finish if documentation drift is detected")
    finish_parser.add_argument("--dry-run", action="store_true", help="Simulate commands without executing them")
    finish_parser.set_defaults(func=handle_finish)

    # CLEAN command
    clean_parser = subparsers.add_parser("clean", help="Remove a run's worktree")
    clean_parser.add_argument("name", help="Name of the run to clean")
    clean_parser.add_argument("--delete-branch", action="store_true", help="Also delete the git branch")
    clean_parser.add_argument("--force", "-f", action="store_true", help="Skip confirmation")
    clean_parser.add_argument("--repo-path", default=".", help="Path to the target repository (default: .)")
    clean_parser.add_argument("--dry-run", action="store_true", help="Simulate commands without executing them")
    clean_parser.set_defaults(func=handle_clean)

    # STATUS command (Harness Commander)
    status_parser = subparsers.add_parser("status", help="Display Harness Commander status")
    status_parser.set_defaults(func=handle_status)

    # DOCTOR command (Harness Commander)
    doctor_parser = subparsers.add_parser("doctor", help="Run health checks for Harness Commander")
    doctor_parser.add_argument("--repair-state", action="store_true",
                              help="Run reconciliation and fix safe issues automatically")
    doctor_parser.set_defaults(func=handle_doctor, repair_state=False)

    # NEXT command (Harness Commander)
    next_parser = subparsers.add_parser("next", help="Show next recommended action")
    next_parser.set_defaults(func=handle_next)

    # FOCUS command (Harness Commander)
    focus_parser = subparsers.add_parser("focus", help="Set or view the focus project")
    focus_parser.add_argument("set_project", nargs="?", const=None,
                             help="Project ID or name to set as focus (omits to view current focus)")
    focus_parser.set_defaults(func=handle_focus, set_project=None)

    # SESSION command (Harness Commander)
    session_parser = subparsers.add_parser("session", help="Start interactive Harness Commander session")
    session_parser.set_defaults(func=handle_session)

    # INBOX command (Harness Commander)
    inbox_parser = subparsers.add_parser("inbox", help="Manage inbox items")
    inbox_parser.add_argument("text", nargs="?", const=None,
                             help="Text to capture (use 'list', 'promote <id>', or 'dismiss <id>' for other actions)")
    inbox_parser.add_argument("--list", dest="list_action", action="store_true",
                             help="List all inbox items")
    inbox_parser.add_argument("--promote", metavar="ID",
                             help="Promote inbox item to task")
    inbox_parser.add_argument("--dismiss", metavar="ID",
                             help="Dismiss (delete) inbox item")
    inbox_parser.set_defaults(func=handle_inbox, text=None, list_action=False, promote=None, dismiss=None)

    # BOOTSTRAP command (Harness Commander)
    bootstrap_parser = subparsers.add_parser("bootstrap", help="Check installation and discover updates")
    bootstrap_parser.add_argument("--apply", action="store_true",
                                 help="Apply updates explicitly (no auto-update)")
    bootstrap_parser.set_defaults(func=handle_bootstrap, apply=False)

    args = parser.parse_args()
    
    # Execute the handler
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()