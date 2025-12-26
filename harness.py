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
import sys
import time
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

# Configuration
DEFAULT_MODEL = "claude-sonnet-4-5-20250929"
DEFAULT_SPEC_PATH = Path("prompts/app_spec.txt")


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

    args = parser.parse_args()
    
    # Execute the handler
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()