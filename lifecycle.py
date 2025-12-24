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
    repo_path: str  # Added: path to the target repository


def run_git(cmd: List[str], cwd: Optional[Path] = None, dry_run: bool = False) -> str:
    """Run a git command and return output."""
    if dry_run:
        print(f"[DRY-RUN] git {' '.join(cmd)} (cwd={cwd})")
        return ""

    try:
        # If cwd is not provided, use the current directory (Orchestrator root)
        # But if we are an orchestrator, we usually want to run git in the target repo.
        # This function is generic, but callers should be careful.
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


def create_run(name: str, base_branch: str = "main", repo_path: Path = Path("."), dry_run: bool = False) -> Path:
    """
    Create a new run with an isolated worktree.
    
    1. Create branch run/<name> in target repo (repo_path)
    2. Create worktree at runs/<name> (in Harness dir)
    3. Initialize metadata
    """
    # Runs are stored relative to the Harness, not the target repo
    run_dir = RUNS_DIR / name
    branch_name = f"run/{name}"
    
    if run_dir.exists() and not dry_run:
        raise FileExistsError(f"Run directory {run_dir} already exists")
    
    if not dry_run:
        # ensure runs directory exists
        RUNS_DIR.mkdir(exist_ok=True, parents=True)
    
    print(f"Creating worktree for run '{name}'...")
    print(f"  Target Repo: {repo_path}")
    print(f"  Worktree:    {run_dir}")
    
    repo_path = Path(repo_path).resolve()
    
    # Validate repo_path (skip strict validation in dry_run if it might fail just because of access?)
    # Actually validation is good even in dry run
    if not dry_run and not (repo_path / ".git").exists():
        # It might be a worktree itself or a bare repo, but basic check
        # We can try running git status
        try:
            run_git(["status"], cwd=repo_path)
        except Exception:
             raise ValueError(f"Invalid git repository at {repo_path}")

    # Create worktree and branch
    # git worktree add -b <branch> <path> <start-point>
    # We must run this FROM the target repo, point to the absolute path of the new worktree
    try:
        run_git(
            ["worktree", "add", "-b", branch_name, str(run_dir.resolve()), base_branch],
            cwd=repo_path,
            dry_run=dry_run
        )
    except RuntimeError as e:
        if "already exists" in str(e):
             raise FileExistsError(f"Branch {branch_name} already exists. Choose a different run name.")
        raise e
        
    # Create metadata
    if not dry_run:
        meta = RunMetadata(
            name=name,
            branch=branch_name,
            created_at=time.time(),
            status="active",
            project_dir=str(run_dir.resolve()),
            repo_path=str(repo_path)
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
    
    # Handle backward compatibility for old runs (missing repo_path)
    if "repo_path" not in data:
        data["repo_path"] = "." 
        
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
        # If the directory is gone, we might still want to clean up the worktree entry directly
        # But we need valid RunMetadata to know where the repo was... 
        # For now, simplistic approach: if run_dir is gone, we can't easily clean up the git entry 
        # unless we saved that info elsewhere.
        # But if the user says "clean foo", we assume they mean the one in runs/foo.
        print(f"Run directory {run_dir} not found.")
        return

    # Load metadata to find the repo path
    try:
        meta = load_run_metadata(name)
        repo_path = Path(meta.repo_path)
    except Exception:
        print("Warning: Could not load metadata. Assuming local repo.")
        repo_path = Path(".")

    print(f"Cleaning up run '{name}'...")
    
    # Remove worktree using git
    # We must run this from the target repo
    try:
        run_git(["worktree", "remove", str(run_dir.resolve()), "--force"], cwd=repo_path)
    except Exception as e:
        print(f"Warning: git worktree remove failed: {e}")
        # Continue to force delete directory
    
    # Double check directory is gone
    if run_dir.exists():
        shutil.rmtree(run_dir)
        
    if delete_branch:
        print(f"Deleting branch {branch_name}...")
        try:
            run_git(["branch", "-D", branch_name], cwd=repo_path)
        except RuntimeError as e:
            print(f"Warning: Could not delete branch {branch_name}: {e}")
            
    print(f"Run '{name}' cleanup complete")

