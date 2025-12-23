"""
Handoff Schema Definition
=========================

Canonical schema for handoff.json files.
This is the single source of truth for the task format.
"""

from dataclasses import dataclass, field
from typing import Optional
import json
from pathlib import Path


# Valid categories for tasks
VALID_CATEGORIES = {
    "security",
    "oidc",
    "roles",
    "infrastructure",
    "cli",
    "testing",
    "docs",
    "functional",
    "style",
    "api",
    "database",
    "auth",
    "ui",
}


@dataclass
class Task:
    """A single task in the handoff.
    
    Required fields:
        id: Unique identifier (e.g., "HUB-001", "TASK-042")
        category: One of VALID_CATEGORIES
        title: Short, action-oriented title
        description: What must be implemented
        acceptance_criteria: List of verifiable criteria
        passes: Whether the task is complete (default: false)
    
    Optional fields:
        files_expected: Hint for files that will be touched
        steps: Verification steps (for testing)
    """
    id: str
    category: str
    title: str
    description: str
    acceptance_criteria: list[str]
    passes: bool = False
    files_expected: list[str] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)
    
    def validate(self) -> list[str]:
        """Validate the task and return list of errors (empty if valid)."""
        errors = []
        
        if not self.id:
            errors.append("Task missing 'id'")
        if not self.category:
            errors.append(f"Task {self.id}: missing 'category'")
        elif self.category not in VALID_CATEGORIES:
            errors.append(f"Task {self.id}: invalid category '{self.category}'. Must be one of: {VALID_CATEGORIES}")
        if not self.title:
            errors.append(f"Task {self.id}: missing 'title'")
        if not self.description:
            errors.append(f"Task {self.id}: missing 'description'")
        if not self.acceptance_criteria:
            errors.append(f"Task {self.id}: missing 'acceptance_criteria' (must have at least one)")
        if not isinstance(self.passes, bool):
            errors.append(f"Task {self.id}: 'passes' must be a boolean")
            
        return errors


@dataclass
class HandoffMeta:
    """Metadata for the handoff file."""
    project: str
    phase: str = "Phase 1"
    source: str = ""
    lock: bool = True
    
    def validate(self) -> list[str]:
        """Validate metadata and return list of errors."""
        errors = []
        if not self.project:
            errors.append("Meta: missing 'project' name")
        return errors


@dataclass  
class Handoff:
    """Complete handoff structure."""
    meta: HandoffMeta
    tasks: list[Task]
    
    def validate(self) -> list[str]:
        """Validate entire handoff and return list of errors."""
        errors = []
        errors.extend(self.meta.validate())
        
        if not self.tasks:
            errors.append("Handoff has no tasks")
            return errors
        
        # Check for duplicate IDs
        ids = [t.id for t in self.tasks]
        duplicates = [id for id in ids if ids.count(id) > 1]
        if duplicates:
            errors.append(f"Duplicate task IDs: {set(duplicates)}")
        
        # Validate each task
        for task in self.tasks:
            errors.extend(task.validate())
            
        return errors
    
    def count_passing(self) -> tuple[int, int]:
        """Return (passing_count, total_count)."""
        passing = sum(1 for t in self.tasks if t.passes)
        return passing, len(self.tasks)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "meta": {
                "project": self.meta.project,
                "phase": self.meta.phase,
                "source": self.meta.source,
                "lock": self.meta.lock,
            },
            "tasks": [
                {
                    "id": t.id,
                    "category": t.category,
                    "title": t.title,
                    "description": t.description,
                    "acceptance_criteria": t.acceptance_criteria,
                    "passes": t.passes,
                    "files_expected": t.files_expected,
                    "steps": t.steps,
                }
                for t in self.tasks
            ]
        }


def parse_handoff(data: dict) -> Handoff:
    """Parse a dictionary into a Handoff object.
    
    Supports both new format (with meta) and legacy format (array of tasks).
    """
    # Handle legacy format: just an array of tasks
    if isinstance(data, list):
        tasks = []
        for i, item in enumerate(data):
            task = Task(
                id=item.get("id", f"TASK-{i+1:03d}"),
                category=item.get("category", "functional"),
                title=item.get("title", item.get("description", "")[:50]),
                description=item.get("description", ""),
                acceptance_criteria=item.get("acceptance_criteria", item.get("steps", [])),
                passes=item.get("passes", False),
                files_expected=item.get("files_expected", []),
                steps=item.get("steps", []),
            )
            tasks.append(task)
        
        meta = HandoffMeta(project="Unknown (legacy format)")
        return Handoff(meta=meta, tasks=tasks)
    
    # New format with meta
    meta_data = data.get("meta", {})
    meta = HandoffMeta(
        project=meta_data.get("project", "Unknown"),
        phase=meta_data.get("phase", "Phase 1"),
        source=meta_data.get("source", ""),
        lock=meta_data.get("lock", True),
    )
    
    tasks = []
    for item in data.get("tasks", []):
        task = Task(
            id=item.get("id", ""),
            category=item.get("category", "functional"),
            title=item.get("title", ""),
            description=item.get("description", ""),
            acceptance_criteria=item.get("acceptance_criteria", []),
            passes=item.get("passes", False),
            files_expected=item.get("files_expected", []),
            steps=item.get("steps", []),
        )
        tasks.append(task)
    
    return Handoff(meta=meta, tasks=tasks)


def load_handoff(path: Path) -> Handoff:
    """Load and parse a handoff.json file."""
    with open(path, "r") as f:
        data = json.load(f)
    return parse_handoff(data)


def save_handoff(handoff: Handoff, path: Path) -> None:
    """Save a handoff to a JSON file."""
    with open(path, "w") as f:
        json.dump(handoff.to_dict(), f, indent=2)


def validate_handoff_file(path: Path) -> list[str]:
    """Validate a handoff.json file and return list of errors."""
    try:
        handoff = load_handoff(path)
        return handoff.validate()
    except json.JSONDecodeError as e:
        return [f"Invalid JSON: {e}"]
    except Exception as e:
        return [f"Error loading handoff: {e}"]
