"""
Harness Commander - State Management
====================================

Core state management system for Harness Commander with atomic file writes,
crash recovery, and UUID-based IDs.
"""

import os
import json
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


# Home directory for Commander state
COMMANDER_HOME = Path.home() / ".cloud-harness"
STATE_FILE = COMMANDER_HOME / "state.json"
STATE_FILE_TMP = STATE_FILE.with_suffix(".json.tmp")


@dataclass
class InboxItem:
    """An item in the inbox."""
    id: str
    text: str
    createdAt: str
    triageStatus: Optional[str] = None

    def __post_init__(self):
        """Ensure ID is set."""
        if not self.id:
            self.id = str(uuid.uuid4())


@dataclass
class Task:
    """A Commander task."""
    id: str
    projectId: str
    title: str
    column: str  # e.g., "todo", "doing", "preview", "blocked", "done"
    createdAt: str

    def __post_init__(self):
        """Ensure ID is set."""
        if not self.id:
            self.id = str(uuid.uuid4())


@dataclass
class Run:
    """A Commander run (harness worktree)."""
    id: str
    projectId: str
    runName: str
    state: str  # e.g., "running", "finished", "cleaned"
    worktreePath: Optional[str] = None
    branchName: Optional[str] = None
    lastCommand: Optional[str] = None
    lastResult: Optional[str] = None
    lastTouchedAt: Optional[str] = None

    def __post_init__(self):
        """Ensure ID is set."""
        if not self.id:
            self.id = str(uuid.uuid4())


@dataclass
class Project:
    """A Commander project (repository)."""
    id: str
    name: str
    repoPath: str
    status: str
    lastTouchedAt: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    def __post_init__(self):
        """Ensure ID is set."""
        if not self.id:
            self.id = str(uuid.uuid4())


@dataclass
class State:
    """Complete Commander state."""
    focusProjectId: Optional[str] = None
    projects: list[Project] = field(default_factory=list)
    runs: list[Run] = field(default_factory=list)
    tasks: list[Task] = field(default_factory=list)
    inbox: list[InboxItem] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "State":
        """Create State from dictionary."""
        return cls(
            focusProjectId=data.get("focusProjectId"),
            projects=[Project(**p) for p in data.get("projects", [])],
            runs=[Run(**r) for r in data.get("runs", [])],
            tasks=[Task(**t) for t in data.get("tasks", [])],
            inbox=[InboxItem(**i) for i in data.get("inbox", [])],
        )


class StateManager:
    """Manages Commander state with atomic writes and crash recovery."""

    def __init__(self, state_path: Path = STATE_FILE):
        """Initialize state manager.

        Args:
            state_path: Path to state.json file
        """
        self.state_path = state_path
        self.state_tmp_path = state_path.with_suffix(".json.tmp")
        self.state: Optional[State] = None

    def ensure_directories(self) -> None:
        """Ensure Commander home directory exists."""
        COMMANDER_HOME.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Ensured Commander directory: {COMMANDER_HOME}")

    def recover_from_crash(self) -> None:
        """Clean up incomplete writes from previous crash.

        If state.json.tmp exists, delete it (incomplete write).
        """
        if self.state_tmp_path.exists():
            logger.warning(f"Found incomplete state write: {self.state_tmp_path}")
            self.state_tmp_path.unlink()
            logger.info("Cleaned up incomplete state file")

    def atomic_write(self, data: dict) -> None:
        """Write state atomically (temp + fsync + rename).

        This ensures that crashes during write don't corrupt state.

        Args:
            data: Dictionary to write to state file
        """
        # Write to temp file
        with open(self.state_tmp_path, "w") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())

        # Atomic rename (POSIX guarantees this is atomic)
        self.state_tmp_path.replace(self.state_path)

        logger.debug(f"Atomic state write complete: {self.state_path}")

    def load_state(self) -> State:
        """Load state from disk, handling missing or corrupt files.

        Returns:
            State object (empty State if file doesn't exist)
        """
        self.ensure_directories()
        self.recover_from_crash()

        if not self.state_path.exists():
            logger.info("State file does not exist, creating new state")
            self.state = State()
            return self.state

        try:
            with open(self.state_path, "r") as f:
                data = json.load(f)

            self.state = State.from_dict(data)
            logger.debug(f"Loaded state from {self.state_path}")
            return self.state

        except json.JSONDecodeError as e:
            logger.error(f"State file is corrupt: {e}")
            raise ValueError(
                f"State file is corrupt. Run 'c-harness doctor --repair-state' to fix.\n"
                f"Error: {e}"
            )
        except Exception as e:
            logger.error(f"Error loading state: {e}")
            raise

    def save_state(self) -> None:
        """Save current state to disk atomically.

        Raises:
            RuntimeError: If no state is loaded
        """
        if self.state is None:
            raise RuntimeError("No state loaded. Call load_state() first.")

        self.ensure_directories()
        self.atomic_write(self.state.to_dict())
        logger.info("State saved successfully")

    def update_state(self, new_state: State) -> None:
        """Replace current state and save atomically.

        Args:
            new_state: New state to save
        """
        self.state = new_state
        self.save_state()

    def get_project(self, project_id: str) -> Optional[Project]:
        """Get a project by ID.

        Args:
            project_id: UUID of the project

        Returns:
            Project if found, None otherwise
        """
        if not self.state:
            return None
        return next((p for p in self.state.projects if p.id == project_id), None)

    def get_run(self, run_id: str) -> Optional[Run]:
        """Get a run by ID.

        Args:
            run_id: UUID of the run

        Returns:
            Run if found, None otherwise
        """
        if not self.state:
            return None
        return next((r for r in self.state.runs if r.id == run_id), None)

    def get_inbox_item(self, item_id: str) -> Optional[InboxItem]:
        """Get an inbox item by ID.

        Args:
            item_id: UUID of the inbox item

        Returns:
            InboxItem if found, None otherwise
        """
        if not self.state:
            return None
        return next((i for i in self.state.inbox if i.id == item_id), None)


def generate_uuid() -> str:
    """Generate a new UUID v4.

    Returns:
        UUID string
    """
    return str(uuid.uuid4())


def get_timestamp() -> str:
    """Get current ISO 8601 timestamp.

    Returns:
        ISO 8601 formatted timestamp
    """
    return datetime.utcnow().isoformat() + "Z"
