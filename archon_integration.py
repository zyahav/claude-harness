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


class ArchonMCPClient:
    """Client for communicating with Archon MCP server."""
    
    def __init__(self, url: str = ARCHON_MCP_URL):
        self.url = url
        self.session_id: Optional[str] = None
        self._client = None
    
    def _get_client(self):
        if self._client is None:
            import httpx
            self._client = httpx.Client(timeout=30)
        return self._client
    
    def _headers(self):
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        return headers
    
    def initialize(self) -> bool:
        """Initialize MCP session."""
        try:
            client = self._get_client()
            init_request = {
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "c-harness", "version": "0.1.0"}
                },
                "id": "init"
            }
            
            response = client.post(self.url, json=init_request, headers=self._headers())
            if response.status_code != 200:
                logger.error(f"MCP init failed: {response.status_code}")
                return False
            
            self.session_id = response.headers.get("mcp-session-id")
            if not self.session_id:
                logger.error("No session ID received")
                return False
            
            # Send initialized notification
            notif = {"jsonrpc": "2.0", "method": "notifications/initialized"}
            client.post(self.url, json=notif, headers=self._headers())
            
            return True
            
        except Exception as e:
            logger.error(f"MCP init error: {e}")
            return False
    
    def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Call an MCP tool and return the result."""
        if not self.session_id:
            if not self.initialize():
                return {"success": False, "error": "Failed to initialize MCP session"}
        
        try:
            client = self._get_client()
            tool_call = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments},
                "id": "tool"
            }
            
            response = client.post(self.url, json=tool_call, headers=self._headers())
            if response.status_code != 200:
                return {"success": False, "error": f"HTTP {response.status_code}"}
            
            # Parse SSE response
            for line in response.text.split('\n'):
                if line.startswith('data: '):
                    data = json.loads(line[6:])
                    if 'result' in data:
                        content = data['result'].get('content', [])
                        if content:
                            try:
                                result = json.loads(content[0]['text'])
                                return {"success": True, **result}
                            except json.JSONDecodeError:
                                return {"success": True, "text": content[0]['text']}
                    elif 'error' in data:
                        return {"success": False, "error": data['error']}
            
            return {"success": False, "error": "No result in response"}
            
        except Exception as e:
            logger.error(f"Tool call failed: {e}")
            return {"success": False, "error": str(e)}
    
    def close(self):
        """Close the client."""
        if self._client:
            self._client.close()
            self._client = None


# Global client instance
_archon_client: Optional[ArchonMCPClient] = None


def get_archon_client() -> ArchonMCPClient:
    """Get or create the Archon MCP client."""
    global _archon_client
    if _archon_client is None:
        _archon_client = ArchonMCPClient()
    return _archon_client


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
    """Call an Archon MCP tool."""
    client = get_archon_client()
    return client.call_tool(tool_name, arguments)


def create_archon_project(
    repo_name: str,
    run_id: str,
    github_repo: Optional[str] = None,
) -> Optional[str]:
    """Create an Archon project for a c-harness run."""
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
        print(f"  Archon project: {title}")
        print(f"  Project ID: {project_id}")
        return project_id
    else:
        logger.warning(f"Failed to create Archon project: {result.get('error')}")
        print(f"  Warning: Failed to create Archon project: {result.get('error')}")
        return None


def import_handoff_tasks(project_id: str, handoff_path: Path) -> dict[str, str]:
    """Import tasks from handoff.json into Archon."""
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
            
    print(f"  Imported {len(task_mapping)}/{len(tasks)} tasks to Archon")
    return task_mapping


def setup_archon_for_run(
    repo_path: Path,
    run_id: str,
    handoff_path: Optional[Path] = None,
) -> Optional[ArchonProject]:
    """Set up Archon integration for a c-harness run."""
    if not is_archon_available():
        logger.info("Archon not available, skipping integration")
        return None
    
    print("Setting up Archon integration...")
    repo_name = repo_path.name
    
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
        
    project_id = create_archon_project(repo_name, run_id, github_repo)
    if not project_id:
        return None
        
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
    
    run_data = {}
    if run_json_path.exists():
        try:
            with open(run_json_path, "r") as f:
                run_data = json.load(f)
        except Exception:
            pass
            
    run_data["archon"] = {
        "project_id": archon_project.project_id,
        "title": archon_project.title,
        "task_ids": archon_project.task_ids,
    }
    
    with open(run_json_path, "w") as f:
        json.dump(run_data, f, indent=2)


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



# =============================================================================
# Progress Logging Functions
# =============================================================================

from datetime import datetime


def get_task_description(task_id: str) -> Optional[str]:
    """Get current task description from Archon."""
    result = call_archon_tool("find_tasks", {"task_id": task_id})
    if result.get("success") and result.get("task"):
        return result["task"].get("description", "")
    return None


def update_task_description(task_id: str, description: str) -> bool:
    """Update task description in Archon."""
    result = call_archon_tool("manage_task", {
        "action": "update",
        "task_id": task_id,
        "description": description,
    })
    return result.get("success", False)


def update_task_status(task_id: str, status: str) -> bool:
    """
    Update task status in Archon.
    
    Args:
        task_id: Archon task ID
        status: One of 'todo', 'doing', 'review', 'done'
    
    Returns:
        True if successful
    """
    if status not in ("todo", "doing", "review", "done"):
        logger.error(f"Invalid status: {status}")
        return False
    
    result = call_archon_tool("manage_task", {
        "action": "update",
        "task_id": task_id,
        "status": status,
    })
    success = result.get("success", False)
    if success:
        logger.info(f"Task {task_id} status -> {status}")
    return success


def log_progress(task_id: str, message: str, status: Optional[str] = None) -> bool:
    """
    Log progress to an Archon task by appending to its description.
    
    Args:
        task_id: Archon task ID
        message: Progress message to append
        status: Optional status update ('todo', 'doing', 'review', 'done')
    
    Returns:
        True if successful
    
    Example:
        log_progress("abc-123", "Reading codebase...", status="doing")
        log_progress("abc-123", "Implementing feature...")
        log_progress("abc-123", "✓ Complete - ready for review", status="review")
    """
    # Get current description
    current_desc = get_task_description(task_id)
    if current_desc is None:
        logger.error(f"Could not get description for task {task_id}")
        return False
    
    # Format timestamp
    timestamp = datetime.now().strftime("%H:%M")
    entry = f"[{timestamp}] {message}"
    
    # Check if progress section exists
    progress_marker = "\n\n---\n## Progress Log\n"
    if progress_marker in current_desc:
        # Append to existing progress section
        new_desc = current_desc + entry + "\n"
    else:
        # Create progress section
        new_desc = current_desc + progress_marker + entry + "\n"
    
    # Update description
    if not update_task_description(task_id, new_desc):
        logger.error(f"Failed to update description for task {task_id}")
        return False
    
    # Update status if provided
    if status:
        update_task_status(task_id, status)
    
    logger.info(f"Logged progress to task {task_id}: {message}")
    return True


def start_task(task_id: str, message: str = "Task started") -> bool:
    """Mark task as doing and log start."""
    return log_progress(task_id, message, status="doing")


def complete_task(task_id: str, message: str = "✓ Task complete") -> bool:
    """Mark task as review and log completion."""
    return log_progress(task_id, message, status="review")
