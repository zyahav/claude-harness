"""
Lifecycle Management
====================

Manages the lifecycle of autonomous agent runs using Git worktrees.
Each run gets its own isolated worktree and branch.
"""

import json
import shutil
import subprocess
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, List


RUNS_DIR = Path("runs")


@dataclass
class RunMetadata:
    name: str
    branch: str
    created_at: float
    status: str  # "active", "finished", "failed"
    project_dir: str


def run_git(cmd: List[str], cwd: Optional[Path] = None) -> str:
    """Run a git command and return output."""
    try:
        result = subprocess.run(
            ["git"] + cmd,
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Git command failed: {' '.join(cmd)}\n{e.stderr}")


def create_run(name: str, base_branch: str = "main") -> Path:
    """
    Create a new run with an isolated worktree.
    
    1. Create branch run/<name> from base_branch
    2. Create worktree at runs/<name>
    3. Initialize metadata
    """
    run_dir = RUNS_DIR / name
    branch_name = f"run/{name}"
    
    if run_dir.exists():
        raise FileExistsError(f"Run directory {run_dir} already exists")
    
    # ensure runs directory exists
    RUNS_DIR.mkdir(exist_ok=True)
    
    print(f"Creating worktree for run '{name}'...")
    
    # Create worktree and branch
    # git worktree add -b <branch> <path> <start-point>
    try:
        run_git(["worktree", "add", "-b", branch_name, str(run_dir), base_branch])
    except RuntimeError as e:
        if "already exists" in str(e):
             raise FileExistsError(f"Branch {branch_name} already exists. Choose a different run name.")
        raise e
        
    # Create metadata
    meta = RunMetadata(
        name=name,
        branch=branch_name,
        created_at=time.time(),
        status="active",
        project_dir=str(run_dir.resolve())
    )
    
    meta_path = run_dir / ".run.json"
    with open(meta_path, "w") as f:
        json.dump(asdict(meta), f, indent=2)
        
    print(f"Run '{name}' initialized at {run_dir}")
    return run_dir


def load_run_metadata(run_name: str) -> RunMetadata:
    """Load metadata for a run."""
    meta_path = RUNS_DIR / run_name / ".run.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"Run metadata not found for {run_name}")
        
    with open(meta_path, "r") as f:
        data = json.load(f)
    return RunMetadata(**data)


def list_runs() -> List[RunMetadata]:
    """List all active runs."""
    if not RUNS_DIR.exists():
        return []
        
    runs = []
    for run_dir in RUNS_DIR.iterdir():
        if run_dir.is_dir() and (run_dir / ".run.json").exists():
            try:
                runs.append(load_run_metadata(run_dir.name))
            except Exception:
                continue
    return sorted(runs, key=lambda r: r.created_at, reverse=True)


def cleanup_run(name: str, delete_branch: bool = False) -> None:
    """
    Remove a run's worktree and optionally its branch.
    """
    run_dir = RUNS_DIR / name
    branch_name = f"run/{name}"
    
    if not run_dir.exists():
        # Check if it's just a git worktree prune candidate
        run_git(["worktree", "prune"])
        return

    print(f"Cleaning up run '{name}'...")
    
    # Remove worktree using git
    # This automatically removes the directory
    run_git(["worktree", "remove", str(run_dir), "--force"])
    
    # Double check directory is gone
    if run_dir.exists():
        shutil.rmtree(run_dir)
        
    if delete_branch:
        print(f"Deleting branch {branch_name}...")
        try:
            run_git(["branch", "-D", branch_name])
        except RuntimeError as e:
            print(f"Warning: Could not delete branch {branch_name}: {e}")
            
    print(f"Run '{name}' cleanup complete")
