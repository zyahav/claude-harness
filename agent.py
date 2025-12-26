"""
Agent Session Logic
===================

Core agent interaction functions for running autonomous coding sessions.
"""

import asyncio
import json
import threading
import time
from pathlib import Path
from typing import Optional, Callable

# from claude_code_sdk import ClaudeSDKClient

from client import create_client
from progress import print_session_header, print_progress_summary
from prompts import get_initializer_prompt, get_prompt_for_mode, copy_spec_to_project
import schema
import archon_integration

import logging

# Try to import watchdog for file watching
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileModifiedEvent
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    logger.warning("watchdog not available - file watching disabled")

logger = logging.getLogger(__name__)

# Global Archon reference for current session
_archon_project: Optional[archon_integration.ArchonProject] = None

# Configuration
AUTO_CONTINUE_DELAY_SECONDS = 3


# =============================================================================
# File Watching for Real-time Task Tracking
# =============================================================================

class HandoffFileHandler(FileSystemEventHandler):
    """
    Handler for handoff.json file modification events.
    """

    def __init__(self, handoff_path: Path, callback: Callable[[dict], None]):
        """
        Initialize the file handler.

        Args:
            handoff_path: Path to handoff.json file
            callback: Function to call when file changes (receives parsed JSON content)
        """
        self.handoff_path = handoff_path
        self.callback = callback
        self._last_content = None
        self._last_modified = 0

        # Read initial content to avoid immediate false trigger
        if handoff_path.exists():
            try:
                with open(handoff_path, 'r') as f:
                    self._last_content = f.read()
                self._last_modified = time.time()
            except Exception:
                pass

    def on_modified(self, event):
        """Called when file is modified."""
        if event.is_directory:
            return

        # Check if it's the handoff.json file
        if Path(event.src_path) != self.handoff_path:
            return

        # Debounce rapid successive changes (ignore changes within 1 second)
        current_time = time.time()
        if current_time - self._last_modified < 1.0:
            return

        try:
            # Read new content
            with open(self.handoff_path, 'r') as f:
                new_content = f.read()

            # Only trigger if content actually changed
            if new_content != self._last_content:
                self._last_content = new_content
                self._last_modified = current_time

                # Parse JSON and call callback
                data = json.loads(new_content)
                logger.debug(f"handoff.json modified, invoking callback")
                self.callback(data)

        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON in handoff.json: {e}")
        except Exception as e:
            logger.warning(f"Error reading handoff.json: {e}")


class HandoffFileWatcher:
    """
    File watcher for monitoring handoff.json changes.
    Uses watchdog if available, otherwise uses polling.
    """

    def __init__(self, handoff_path: Path, callback: Callable[[dict], None]):
        """
        Initialize the file watcher.

        Args:
            handoff_path: Path to handoff.json file
            callback: Function to call when file changes (receives parsed JSON content)
        """
        self.handoff_path = handoff_path
        self.callback = callback
        self._observer = None
        self._polling_thread = None
        self._polling_active = False
        self._last_content = None

        # Read initial content
        if handoff_path.exists():
            try:
                with open(handoff_path, 'r') as f:
                    self._last_content = f.read()
            except Exception:
                pass

    def start(self):
        """Start watching the file."""
        if not self.handoff_path.exists():
            logger.warning(f"handoff.json not found at {self.handoff_path}")
            return

        if WATCHDOG_AVAILABLE:
            self._start_watchdog()
        else:
            self._start_polling()

    def _start_watchdog(self):
        """Start watching using watchdog (preferred method)."""
        try:
            self._observer = Observer()
            handler = HandoffFileHandler(self.handoff_path, self.callback)
            self._observer.schedule(
                handler,
                str(self.handoff_path.parent),
                recursive=False
            )
            self._observer.start()
            logger.info(f"Watching handoff.json for changes (watchdog)")
        except Exception as e:
            logger.warning(f"Failed to start watchdog observer: {e}, falling back to polling")
            self._start_polling()

    def _start_polling(self):
        """Start watching using polling (fallback method)."""
        self._polling_active = True
        self._polling_thread = threading.Thread(
            target=self._polling_loop,
            daemon=True
        )
        self._polling_thread.start()
        logger.info(f"Watching handoff.json for changes (polling)")

    def _polling_loop(self):
        """Polling loop for file changes."""
        while self._polling_active:
            try:
                if self.handoff_path.exists():
                    with open(self.handoff_path, 'r') as f:
                        new_content = f.read()

                    if new_content != self._last_content:
                        self._last_content = new_content
                        data = json.loads(new_content)
                        logger.debug(f"handoff.json modified (polling), invoking callback")
                        self.callback(data)
            except json.JSONDecodeError:
                pass  # Ignore invalid JSON during writes
            except Exception as e:
                logger.warning(f"Error in polling loop: {e}")

            # Poll every 2 seconds
            time.sleep(2)

    def stop(self):
        """Stop watching the file."""
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None
            logger.debug("Stopped watchdog observer")

        if self._polling_thread:
            self._polling_active = False
            self._polling_thread.join(timeout=3)
            self._polling_thread = None
            logger.debug("Stopped polling thread")


def get_current_task_id(project_dir: Path) -> Optional[str]:
    """
    Get the ID of the first incomplete task from handoff.json.
    
    Returns:
        Task ID string (e.g., "HARNESS-014-A") or None if no incomplete tasks
    """
    handoff_file = project_dir / "handoff.json"
    if not handoff_file.exists():
        return None
    
    try:
        import json
        with open(handoff_file, "r") as f:
            data = json.load(f)
        
        tasks = data.get("tasks", [])
        for task in tasks:
            if not task.get("passes", False):
                return task.get("id")
        return None  # All tasks complete
    except Exception as e:
        logger.warning(f"Could not read handoff.json: {e}")
        return None


def update_archon_task_status(task_id: str, status: str) -> None:
    """
    Update the Archon task status if Archon integration is active.
    
    Args:
        task_id: The handoff.json task ID (e.g., "HARNESS-014-A")
        status: New status ("doing", "review", etc.)
    """
    global _archon_project
    
    if not _archon_project:
        return
    
    # Map handoff task ID to Archon task ID
    archon_task_id = _archon_project.task_ids.get(task_id)
    if not archon_task_id:
        logger.debug(f"No Archon mapping for task {task_id}")
        return
    
    try:
        if status == "doing":
            archon_integration.start_task(archon_task_id, f"Agent started working on {task_id}")
        elif status == "review":
            archon_integration.complete_task(archon_task_id, f"✓ {task_id} complete")
        else:
            archon_integration.update_task_status(archon_task_id, status)
        logger.info(f"Archon: {task_id} → {status}")
    except Exception as e:
        logger.warning(f"Failed to update Archon task status: {e}")


def get_task_pass_states(project_dir: Path) -> dict[str, bool]:
    """
    Get the pass/fail state of all tasks from handoff.json.

    Returns:
        Dict mapping task_id -> passes (True/False)
    """
    handoff_file = project_dir / "handoff.json"
    if not handoff_file.exists():
        return {}

    try:
        with open(handoff_file, "r") as f:
            data = json.load(f)

        tasks = data.get("tasks", [])
        return {task.get("id"): task.get("passes", False) for task in tasks if task.get("id")}
    except Exception as e:
        logger.warning(f"Could not read handoff.json: {e}")
        return {}


def get_task_states(project_dir: Path) -> dict[str, dict]:
    """
    Get the full state of all tasks from handoff.json.

    Returns:
        Dict mapping task_id -> task_dict with all task fields
    """
    handoff_file = project_dir / "handoff.json"
    if not handoff_file.exists():
        return {}

    try:
        with open(handoff_file, "r") as f:
            data = json.load(f)

        tasks = data.get("tasks", [])
        return {task.get("id"): task for task in tasks if task.get("id")}
    except Exception as e:
        logger.warning(f"Could not read handoff.json: {e}")
        return {}


def detect_task_changes(before: dict[str, dict], after: dict[str, dict]) -> list[dict]:
    """
    Detect changes between two task states.

    Args:
        before: Previous task states (task_id -> task_dict)
        after: New task states (task_id -> task_dict)

    Returns:
        List of change dicts with keys: task_id, change_type, details
        change_type can be: 'started', 'completed', 'modified'
    """
    changes = []

    # Check for new or modified tasks
    for task_id, new_task in after.items():
        old_task = before.get(task_id)

        if old_task is None:
            # New task added
            changes.append({
                "task_id": task_id,
                "change_type": "started",
                "details": "New task detected"
            })
        else:
            # Check for pass status change
            old_pass = old_task.get("passes", False)
            new_pass = new_task.get("passes", False)

            if not old_pass and new_pass:
                # Task completed
                changes.append({
                    "task_id": task_id,
                    "change_type": "completed",
                    "details": "Task passes changed to True"
                })
            elif old_task != new_task:
                # Task modified (but not completed)
                changes.append({
                    "task_id": task_id,
                    "change_type": "modified",
                    "details": "Task content changed"
                })

    return changes


def check_newly_completed_tasks(before: dict[str, bool], after: dict[str, bool]) -> list[str]:
    """
    Find tasks that changed from passes=False to passes=True.
    
    Args:
        before: Task states before iteration
        after: Task states after iteration
    
    Returns:
        List of task IDs that were newly completed
    """
    newly_completed = []
    for task_id, passes in after.items():
        if passes and not before.get(task_id, False):
            newly_completed.append(task_id)
    return newly_completed


def log_session_summary(project_dir: Path, iteration: int, newly_completed: list[str]) -> None:
    """
    Log a session summary to Archon for the current task.
    
    Args:
        project_dir: Project directory with handoff.json
        iteration: Current iteration number
        newly_completed: List of task IDs completed this iteration
    """
    global _archon_project
    
    if not _archon_project:
        return
    
    # Get current task to log summary to
    current_task = get_current_task_id(project_dir)
    if not current_task:
        # All tasks done, log to last completed task if any
        if newly_completed:
            current_task = newly_completed[-1]
        else:
            return
    
    archon_task_id = _archon_project.task_ids.get(current_task)
    if not archon_task_id:
        return
    
    # Build summary message
    from progress import count_passing_tests
    passing, total = count_passing_tests(project_dir)
    
    summary_parts = [f"Iteration {iteration} complete"]
    if newly_completed:
        summary_parts.append(f"completed: {', '.join(newly_completed)}")
    summary_parts.append(f"progress: {passing}/{total}")
    
    summary = " | ".join(summary_parts)
    
    try:
        archon_integration.log_progress(archon_task_id, summary)
    except Exception as e:
        logger.warning(f"Failed to log session summary: {e}")


async def run_agent_session(
    client: "ClaudeSDKClient",
    message: str,
    project_dir: Path,
) -> tuple[str, str]:
    """
    Run a single agent session using Claude Agent SDK.

    Args:
        client: Claude SDK client
        message: The prompt to send
        project_dir: Project directory path

    Returns:
        (status, response_text) where status is:
        - "continue" if agent should continue working
        - "error" if an error occurred
    """
    logger.info("Sending prompt to Claude Agent SDK...\n")

    try:
        # Send the query
        await client.query(message)

        # Collect response text and show tool use
        response_text = ""
        async for msg in client.receive_response():
            msg_type = type(msg).__name__

            # Handle AssistantMessage (text and tool use)
            if msg_type == "AssistantMessage" and hasattr(msg, "content"):
                for block in msg.content:
                    block_type = type(block).__name__

                    if block_type == "TextBlock" and hasattr(block, "text"):
                        response_text += block.text
                        logger.info(block.text) # Using info for main text
                    elif block_type == "ToolUseBlock" and hasattr(block, "name"):
                        logger.info(f"\n[Tool: {block.name}]")
                        if hasattr(block, "input"):
                            input_str = str(block.input)
                            if len(input_str) > 200:
                                logger.info(f"   Input: {input_str[:200]}...")
                            else:
                                logger.info(f"   Input: {input_str}")

            # Handle UserMessage (tool results)
            elif msg_type == "UserMessage" and hasattr(msg, "content"):
                for block in msg.content:
                    block_type = type(block).__name__

                    if block_type == "ToolResultBlock":
                        result_content = getattr(block, "content", "")
                        is_error = getattr(block, "is_error", False)

                        # Check if command was blocked by security hook
                        if "blocked" in str(result_content).lower():
                            logger.warning(f"   [BLOCKED] {result_content}")
                        elif is_error:
                            # Show errors (truncated)
                            error_str = str(result_content)[:500]
                            logger.error(f"   [Error] {error_str}")
                        else:
                            # Tool succeeded - just show brief confirmation
                            logger.info("   [Done]")

        logger.info("\n" + "-" * 70 + "\n")
        return "continue", response_text

    except Exception as e:
        logger.error(f"Error during agent session: {e}", exc_info=True)
        return "error", str(e)


async def run_autonomous_agent(
    project_dir: Path,
    model: str,
    max_iterations: Optional[int] = None,
    spec_path: Optional[Path] = None,
    mode: str = "greenfield",
    handoff_path: Optional[Path] = None,
    no_archon: bool = False,
) -> None:
    """
    Run the autonomous agent loop.

    Args:
        project_dir: Directory for the project
        model: Claude model to use
        max_iterations: Maximum number of iterations (None for unlimited)
        spec_path: Path to the constitution/spec file (None for default)
        mode: 'greenfield' (new project) or 'brownfield' (existing codebase)
        handoff_path: Path to handoff.json for brownfield mode (None for default: <worktree>/handoff.json)
        no_archon: If True, disable all Archon integration updates
    """
    global _archon_project
    
    # Load Archon reference if available (graceful fallback if not)
    if no_archon:
        logger.info("Archon integration disabled (--no-archon flag)")
        _archon_project = None
    else:
        _archon_project = archon_integration.load_archon_reference(project_dir)
        if _archon_project:
            logger.info(f"Archon integration active: {_archon_project.title}")
            logger.info(f"  Project ID: {_archon_project.project_id}")
            logger.info(f"  Task mappings: {len(_archon_project.task_ids)}")
        else:
            logger.debug("No Archon integration (no .run.json or no archon section)")
    
    mode_label = "GREENFIELD" if mode == "greenfield" else "BROWNFIELD"
    logger.info("\n" + "=" * 70)
    logger.info(f"  AUTONOMOUS CODING AGENT ({mode_label})")
    logger.info("=" * 70)
    logger.info(f"\nProject directory: {project_dir}")
    logger.info(f"Model: {model}")
    logger.info(f"Mode: {mode}")
    if handoff_path:
        logger.info(f"Handoff: {handoff_path}")
    if max_iterations:
        logger.info(f"Max iterations: {max_iterations}")
    else:
        logger.info("Max iterations: Unlimited (will run until completion)")
    logger.info("")

    # Create project directory
    project_dir.mkdir(parents=True, exist_ok=True)

    # Check if this is a fresh start or continuation
    tests_file = project_dir / "handoff.json"
    is_first_run = not tests_file.exists()

    if is_first_run:
        if mode == "brownfield" and handoff_path:
            # Brownfield mode: copy handoff.json from external location
            import shutil
            handoff_source = Path(handoff_path).expanduser().resolve()
            if not handoff_source.exists():
                logger.error(f"Handoff file not found: {handoff_source}")
                return
            shutil.copy(handoff_source, tests_file)
            logger.info(f"Copied handoff.json from: {handoff_source}")
            logger.info("Starting brownfield mode - working on existing codebase")
            is_first_run = False  # Don't use initializer, we have a handoff
        elif mode == "brownfield":
            logger.error("Brownfield mode requires --handoff-path to be specified")
            return
        else:
            # Greenfield mode: fresh start
            logger.info("Fresh start - will use initializer agent")
            logger.info("")
            logger.info("=" * 70)
            logger.info("  NOTE: First session takes 10-20+ minutes!")
            logger.info("  The agent is generating 200 detailed test cases.")
            logger.info("  This may appear to hang - it's working. Watch for [Tool: ...] output.")
            logger.info("=" * 70)
            logger.info("")
            # Copy the app spec into the project directory for the agent to read
            copy_spec_to_project(project_dir, spec_path)
    else:
        logger.info("Continuing existing project")
        
        # Validate schema before continuing
        errors = schema.validate_handoff_file(tests_file)
        if errors:
            logger.error(f"\nError: handoff.json is invalid:")
            for error in errors:
                logger.error(f"  - {error}")
            logger.error("\nPlease fix the schema errors before continuing.")
            return

        print_progress_summary(project_dir)

    # Initialize file watcher for handoff.json (for real-time Archon updates)
    handoff_file = project_dir / "handoff.json"
    file_watcher = None
    if handoff_file.exists() and not is_first_run:
        # The file watcher callback will be set up to handle task changes
        # For now, we create it but don't start it yet
        # It will be started inside the agent session
        pass

    # Main loop
    iteration = 0

    # Main loop
    iteration = 0
    consecutive_errors = 0
    backoff_seconds = 1

    while True:
        iteration += 1

        # Check max iterations
        if max_iterations and iteration > max_iterations:
            logger.info(f"\nReached max iterations ({max_iterations})")
            logger.info("To continue, run the script again without --max-iterations")
            break

        # Print session header
        # TODO: Update progress.py to use logging or capture its output
        print_session_header(iteration, is_first_run)

        # Update Archon with current task status (if not initializer run)
        if not is_first_run:
            current_task = get_current_task_id(project_dir)
            if current_task:
                update_archon_task_status(current_task, "doing")

        # Capture task states before session (for detecting completions)
        tasks_before = get_task_pass_states(project_dir)

        # Create client (fresh context)
        client = create_client(project_dir, model)

        # Choose prompt based on session type
        if is_first_run:
            prompt = get_initializer_prompt()
            is_first_run = False  # Only use initializer once
        else:
            prompt = get_prompt_for_mode(mode)

        # Start file watcher before agent session (for real-time Archon updates)
        if handoff_file.exists() and file_watcher is None:
            # Store previous task states for comparison
            previous_task_states = get_task_states(project_dir)

            # Create a callback that will handle task changes
            def on_handoff_changed(data: dict):
                """Called when handoff.json changes during agent session."""
                try:
                    # Get new task states from the changed data
                    new_task_states = {task.get("id"): task for task in data.get("tasks", []) if task.get("id")}

                    # Detect what changed
                    changes = detect_task_changes(previous_task_states, new_task_states)

                    # Process each change and update Archon in real-time
                    for change in changes:
                        task_id = change["task_id"]
                        change_type = change["change_type"]

                        if change_type == "started":
                            # Agent started working on a new task
                            logger.info(f"Real-time: Agent started task {task_id}")
                            update_archon_task_status(task_id, "doing")
                        elif change_type == "completed":
                            # Task completed (passes: false -> true)
                            logger.info(f"Real-time: Task {task_id} completed")
                            update_archon_task_status(task_id, "review")
                        elif change_type == "modified":
                            # Task content changed (description, files, etc.)
                            logger.debug(f"Real-time: Task {task_id} modified")

                    # Update previous states for next comparison
                    previous_task_states.clear()
                    previous_task_states.update(new_task_states)

                except Exception as e:
                    logger.warning(f"Error in handoff change callback: {e}")

            file_watcher = HandoffFileWatcher(handoff_file, on_handoff_changed)
            file_watcher.start()
            logger.info("Real-time Archon updates enabled")

        # Run session with async context manager
        try:
            async with client:
                status, response = await run_agent_session(client, prompt, project_dir)
        finally:
            # Stop file watcher after session
            if file_watcher:
                file_watcher.stop()
                file_watcher = None

        # Handle status
        if status == "continue":
            # Success! Reset backoff
            consecutive_errors = 0
            backoff_seconds = 1
            
            # Check for newly completed tasks and update Archon
            tasks_after = get_task_pass_states(project_dir)
            newly_completed = check_newly_completed_tasks(tasks_before, tasks_after)
            for task_id in newly_completed:
                update_archon_task_status(task_id, "review")
            
            # Log session summary to Archon
            log_session_summary(project_dir, iteration, newly_completed)
            
            logger.info(f"\nAgent will auto-continue in {AUTO_CONTINUE_DELAY_SECONDS}s...")
            print_progress_summary(project_dir)
            await asyncio.sleep(AUTO_CONTINUE_DELAY_SECONDS)

        elif status == "error":
            consecutive_errors += 1
            logger.error("\nSession encountered an error")
            
            if consecutive_errors > 5:
                logger.critical("Too many consecutive errors. Aborting.")
                break
                
            logger.warning(f"Retrying in {backoff_seconds}s... (Attempt {consecutive_errors}/5)")
            await asyncio.sleep(backoff_seconds)
            backoff_seconds *= 2  # Exponential backoff

        # Small delay between sessions if not error
        if status != "error" and (max_iterations is None or iteration < max_iterations):
            logger.info("\nPreparing next session...\n")
            await asyncio.sleep(1)

    # Final summary
    print("\n" + "=" * 70)
    print("  SESSION COMPLETE")
    print("=" * 70)
    print(f"\nProject directory: {project_dir}")
    print_progress_summary(project_dir)

    # Print instructions for running the generated application
    print("\n" + "-" * 70)
    print("  TO RUN THE GENERATED APPLICATION:")
    print("-" * 70)
    print(f"\n  cd {project_dir.resolve()}")
    print("  ./init.sh           # Run the setup script")
    print("  # Or manually:")
    print("  npm install && npm run dev")
    print("\n  Then open http://localhost:3000 (or check init.sh for the URL)")
    print("-" * 70)

    print("\nDone!")
