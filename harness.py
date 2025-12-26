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
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

import lifecycle
import schema
import logging
import json
from datetime import datetime

# Configuration
DEFAULT_MODEL = "claude-sonnet-4-5-20250929"
DEFAULT_SPEC_PATH = Path("prompts/app_spec.txt")


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
        
        run_dir = lifecycle.create_run(args.name, args.base, repo_path=args.repo_path, dry_run=args.dry_run)
        
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
        
        # Import agent here (lazy load)
        from agent import run_autonomous_agent
        
        asyncio.run(
            run_autonomous_agent(
                project_dir=project_dir,
                model=args.model,
                max_iterations=args.max_iterations,
                spec_path=args.spec,
                mode=args.mode,
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


def handle_finish(args: argparse.Namespace) -> None:
    """Finish a run: verify status and push branch."""
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
            
        print(f"\nPushing branch {meta.branch}...")
        try:
            # Push from the TARGET REPO (repo_path), not the harness dir
            repo_path = Path(getattr(meta, "repo_path", "."))
            lifecycle.run_git(["push", "origin", meta.branch, "--force"], cwd=repo_path)
        except RuntimeError as e:
            print(f"Error pushing branch: {e}")
            sys.exit(1)
            
        print("\nSuccess! Create your Pull Request here:")
        # TODO: Detect repo URL from git config for a clickable link
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

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Autonomous Coding Agent CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest="command", required=True, help="Command to execute")

    # SCHEMA command
    schema_parser = subparsers.add_parser("schema", help="Print the handoff.json schema template")
    schema_parser.set_defaults(func=handle_schema)

    # START command
    start_parser = subparsers.add_parser("start", help="Start a new agent run (creates worktree)")
    start_parser.add_argument("name", help="Name of the run (used for branch and folder)")
    start_parser.add_argument("--base", default="main", help="Base branch to start from (default: main)")
    start_parser.add_argument("--repo-path", default=".", help="Path to the target repository (default: current dir)")
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
    run_parser.add_argument("--repo-path", default=".", help="Path to the target repository (for context)")
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

    args = parser.parse_args()
    
    # Execute the handler
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()