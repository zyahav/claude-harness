"""
Archon Integration
==================

Integration with Archon MCP for project/task management.
When enabled, c-harness runs are tracked in Archon for visibility.

Flow:
1. c-harness start → Creates Archon project, imports tasks from handoff.json
2. Agent runs → Uses Archon MCP to update task status
3. c-harness finish → Syncs final state to Archon
"""

import json
import logging
import subprocess
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Archon MCP server endpoint
ARCHON_MCP_URL = "http://localhost:8051/mcp"


@dataclass
class ArchonProject:
    """Reference to an Archon project."""
    project_id: str
    title: str
    task_ids: dict[str, str]  # handoff_task_id -> archon_task_id


def is_archon_available() -> bool:
    """Check if Archon MCP server is running."""
    try:
        import requests
        response = requests.get(
            ARCHON_MCP_URL.replace("/mcp", "/health"),
            timeout=2
        )
        return response.status_code == 200
    except Exception:
        return False


def call_archon_tool(tool_name: str, arguments: dict) -> dict:
    """
    Call an Archon MCP tool via mcp-remote.
    
    This uses the mcp-remote CLI to invoke tools on the Archon server.
    """
    try:
        import requests
        
        # For now, use direct HTTP API if available
        # The Archon server exposes REST endpoints
        
        if tool_name == "manage_project":
            if arguments.get("action") == "create":
                # POST to create project
                response = requests.post(
                    ARCHON_MCP_URL.replace("/mcp", "/api/projects"),
                    json={
                        "title": arguments.get("title"),
                        "description": arguments.get("description", ""),
                        "github_repo": arguments.get("github_repo"),
                    },
                    timeout=10
                )
                if response.status_code in (200, 201):
                    return {"success": True, "project": response.json()}
                    
        elif tool_name == "manage_task":
            if arguments.get("action") == "create":
                response = requests.post(
                    ARCHON_MCP_URL.replace("/mcp", "/api/tasks"),
                    json={
                        "project_id": arguments.get("project_id"),
                        "title": arguments.get("title"),
                        "description": arguments.get("description", ""),
                        "status": arguments.get("status", "todo"),
                        "feature": arguments.get("feature"),
                        "assignee": arguments.get("assignee", "Archon"),
                    },
                    timeout=10
                )
                if response.status_code in (200, 201):
                    return {"success": True, "task": response.json()}
                    
        return {"success": False, "error": "Unknown tool or action"}
        
    except Exception as e:
        logger.error(f"Failed to call Archon tool {tool_name}: {e}")
        return {"success": False, "error": str(e)}


def create_archon_project(
    repo_name: str,
    run_id: str,
    github_repo: Optional[str] = None,
) -> Optional[str]:
    """
    Create an Archon project for a c-harness run.
    
    Args:
        repo_name: Name of the target repository
        run_id: The run ID (e.g., TEST-001)
        github_repo: Optional GitHub URL
        
    Returns:
        project_id if successful, None otherwise
    """
    title = f"{repo_name} / {run_id}"
    description = f"c-harness run: {run_id} on {repo_name}"
    
    result = call_archon_tool("manage_project", {
        "action": "create",
        "title": title,
        "description": description,
        "github_repo": github_repo,
    })
    
    if result.get("success") and result.get("project"):
        project_id = result["project"].get("id")
        logger.info(f"Created Archon project: {title} ({project_id})")
        return project_id
    else:
        logger.warning(f"Failed to create Archon project: {result.get('error')}")
        return None


def import_handoff_tasks(
    project_id: str,
    handoff_path: Path,
) -> dict[str, str]:
    """
    Import tasks from handoff.json into Archon.
    
    Args:
        project_id: Archon project ID
        handoff_path: Path to handoff.json
        
    Returns:
        Mapping of handoff task IDs to Archon task IDs
    """
    task_mapping = {}
    
    try:
        with open(handoff_path, "r") as f:
            handoff = json.load(f)
    except Exception as e:
        logger.error(f"Failed to read handoff.json: {e}")
        return task_mapping
        
    tasks = handoff.get("tasks", [])
    
    for task in tasks:
        task_id = task.get("id", "")
        title = task.get("title", "")
        description = task.get("description", "")
        category = task.get("category", "functional")
        passes = task.get("passes", False)
        
        # Build description with acceptance criteria
        full_description = description
        criteria = task.get("acceptance_criteria", [])
        if criteria:
            full_description += "\n\nAcceptance Criteria:\n"
            full_description += "\n".join(f"- {c}" for c in criteria)
        
        result = call_archon_tool("manage_task", {
            "action": "create",
            "project_id": project_id,
            "title": f"[{task_id}] {title}",
            "description": full_description,
            "status": "done" if passes else "todo",
            "feature": category,
            "assignee": "Archon",
        })
        
        if result.get("success") and result.get("task"):
            archon_task_id = result["task"].get("id")
            task_mapping[task_id] = archon_task_id
            logger.debug(f"Imported task {task_id} -> {archon_task_id}")
        else:
            logger.warning(f"Failed to import task {task_id}: {result.get('error')}")
            
    logger.info(f"Imported {len(task_mapping)}/{len(tasks)} tasks to Archon")
    return task_mapping


def setup_archon_for_run(
    repo_path: Path,
    run_id: str,
    handoff_path: Optional[Path] = None,
) -> Optional[ArchonProject]:
    """
    Set up Archon integration for a c-harness run.
    
    Args:
        repo_path: Path to the target repository
        run_id: The run ID
        handoff_path: Path to handoff.json (optional)
        
    Returns:
        ArchonProject if successful, None otherwise
    """
    if not is_archon_available():
        logger.info("Archon not available, skipping integration")
        return None
        
    repo_name = repo_path.name
    
    # Try to get GitHub URL from git remote
    github_repo = None
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=repo_path,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            github_repo = result.stdout.strip()
    except Exception:
        pass
        
    # Create project
    project_id = create_archon_project(repo_name, run_id, github_repo)
    if not project_id:
        return None
        
    # Import tasks if handoff exists
    task_mapping = {}
    if handoff_path and handoff_path.exists():
        task_mapping = import_handoff_tasks(project_id, handoff_path)
        
    return ArchonProject(
        project_id=project_id,
        title=f"{repo_name} / {run_id}",
        task_ids=task_mapping,
    )


def save_archon_reference(run_dir: Path, archon_project: ArchonProject) -> None:
    """Save Archon project reference to .run.json."""
    run_json_path = run_dir / ".run.json"
    
    # Load existing or create new
    run_data = {}
    if run_json_path.exists():
        try:
            with open(run_json_path, "r") as f:
                run_data = json.load(f)
        except Exception:
            pass
            
    # Add Archon reference
    run_data["archon"] = {
        "project_id": archon_project.project_id,
        "title": archon_project.title,
        "task_ids": archon_project.task_ids,
    }
    
    with open(run_json_path, "w") as f:
        json.dump(run_data, f, indent=2)
        
    logger.info(f"Saved Archon reference to {run_json_path}")


def load_archon_reference(run_dir: Path) -> Optional[ArchonProject]:
    """Load Archon project reference from .run.json."""
    run_json_path = run_dir / ".run.json"
    
    if not run_json_path.exists():
        return None
        
    try:
        with open(run_json_path, "r") as f:
            run_data = json.load(f)
            
        archon_data = run_data.get("archon")
        if not archon_data:
            return None
            
        return ArchonProject(
            project_id=archon_data["project_id"],
            title=archon_data["title"],
            task_ids=archon_data.get("task_ids", {}),
        )
    except Exception as e:
        logger.error(f"Failed to load Archon reference: {e}")
        return None
