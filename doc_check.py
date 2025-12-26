#!/usr/bin/env python3
"""
Documentation Trust Protocol (DTP)
==================================

Implements detection, engagement, assistance, and persistence for documentation drift.

The DTP ensures that code changes (new CLI flags, new public files) are properly
documented in README.md and AGENT_GUIDE.md.
"""

import ast
import re
import json
from pathlib import Path
from typing import List, Dict, Set, Tuple, Optional
from dataclasses import dataclass, asdict
import argparse


@dataclass
class DocDrift:
    """Represents a documentation drift item."""
    type: str  # 'cli_flag' or 'public_file'
    item: str  # flag name or file path
    location: str  # where it should be documented
    context: str  # additional context


@dataclass
class DocDecision:
    """Represents a user decision about documentation drift."""
    item: str  # unique identifier for the drift item
    decision: str  # 'documented', 'internal', 'deferred'
    timestamp: str  # ISO timestamp
    description: Optional[str] = None  # user-provided description if documented


class DocChecker:
    """Detects and tracks documentation drift."""

    def __init__(self, project_dir: Path, readme_path: Path = None, agent_guide_path: Path = None):
        self.project_dir = Path(project_dir)
        self.readme_path = readme_path or (self.project_dir / "README.md")
        self.agent_guide_path = agent_guide_path or (self.project_dir / "AGENT_GUIDE.md")
        self.drift_items: List[DocDrift] = []

    def detect_cli_flag_drift(self, harness_file: Path = None) -> List[DocDrift]:
        """
        Detect CLI flags in harness.py that are not documented in README.md.

        Returns:
            List of DocDrift items for undocumented CLI flags
        """
        harness_file = harness_file or (self.project_dir / "harness.py")
        if not harness_file.exists():
            return []

        # Parse harness.py to extract CLI argument definitions
        cli_flags = self._extract_cli_flags(harness_file)

        # Extract documented flags from README
        documented_flags = self._extract_documented_flags(self.readme_path)

        # Find undocumented flags
        undocumented = []
        for flag in cli_flags:
            # Skip common flags that don't need documentation
            if flag in ['--version', '-V', '--help', '-h']:
                continue

            if flag not in documented_flags:
                undocumented.append(DocDrift(
                    type='cli_flag',
                    item=flag,
                    location='README.md',
                    context=f'CLI flag {flag} found in harness.py but not documented in README.md'
                ))

        return undocumented

    def detect_public_file_drift(self, agent_guide_file: Path = None) -> List[DocDrift]:
        """
        Detect public .py files that are not listed in AGENT_GUIDE.md Repository Map.

        Returns:
            List of DocDrift items for undocumented public files
        """
        agent_guide_file = agent_guide_file or self.agent_guide_path
        if not agent_guide_file.exists():
            return []

        # Get all public .py files in project root
        public_files = self._get_public_python_files(self.project_dir)

        # Extract documented files from AGENT_GUIDE.md
        documented_files = self._extract_documented_files(agent_guide_file)

        # Find undocumented files
        undocumented = []
        for file_path in public_files:
            if file_path not in documented_files:
                undocumented.append(DocDrift(
                    type='public_file',
                    item=file_path,
                    location='AGENT_GUIDE.md',
                    context=f'Public file {file_path} not in Repository Map'
                ))

        return undocumented

    def detect_all_drift(self) -> List[DocDrift]:
        """
        Detect all documentation drift (CLI flags and public files).

        Returns:
            Combined list of all drift items
        """
        drift = []

        # Detect CLI flag drift
        cli_drift = self.detect_cli_flag_drift()
        drift.extend(cli_drift)

        # Detect public file drift
        file_drift = self.detect_public_file_drift()
        drift.extend(file_drift)

        self.drift_items = drift
        return drift

    def _extract_cli_flags(self, harness_file: Path) -> Set[str]:
        """Extract all CLI argument flags from harness.py."""
        flags = set()

        try:
            content = harness_file.read_text()

            # Find all add_argument calls
            pattern = r'add_argument\(["\']--?[\w-]+["\']'
            matches = re.findall(pattern, content)

            for match in matches:
                # Extract the flag name
                flag_match = re.search(r'["\'](--?[\w-]+)["\']', match)
                if flag_match:
                    flags.add(flag_match.group(1))

        except Exception as e:
            print(f"Warning: Could not parse {harness_file}: {e}")

        return flags

    def _extract_documented_flags(self, readme_file: Path) -> Set[str]:
        """Extract all documented CLI flags from README.md."""
        flags = set()

        try:
            content = readme_file.read_text()

            # Find code blocks with CLI examples
            pattern = r'`(--?[\w-]+)`'
            matches = re.findall(pattern, content)

            for match in matches:
                flags.add(match)

        except Exception as e:
            print(f"Warning: Could not read {readme_file}: {e}")

        return flags

    def _get_public_python_files(self, project_dir: Path) -> Set[str]:
        """Get all public .py files in project root (excluding test_, __)."""
        files = set()

        for py_file in project_dir.glob("*.py"):
            # Skip test files and private files
            if not py_file.name.startswith('_') and not py_file.name.startswith('test_'):
                files.add(py_file.name)

        return files

    def _extract_documented_files(self, agent_guide_file: Path) -> Set[str]:
        """Extract documented files from AGENT_GUIDE.md Repository Map."""
        files = set()

        try:
            content = agent_guide_file.read_text()

            # Find references to .py files in the repository map section
            # Look for patterns like: **`filename.py`** or `filename.py`
            pattern = r'\*?\*?`([\w]+\.py)`\*?\*?'
            matches = re.findall(pattern, content)

            for match in matches:
                files.add(match)

        except Exception as e:
            print(f"Warning: Could not read {agent_guide_file}: {e}")

        return files


class DocDecisionStore:
    """Manages persistence of documentation decisions."""

    def __init__(self, project_dir: Path):
        self.project_dir = Path(project_dir)
        self.decisions_dir = self.project_dir / ".harness"
        self.decisions_file = self.decisions_dir / "doc_decisions.json"
        self.decisions: Dict[str, DocDecision] = {}

        # Create .harness directory if it doesn't exist
        self.decisions_dir.mkdir(exist_ok=True)

        # Load existing decisions
        self._load()

    def _load(self):
        """Load decisions from storage."""
        if self.decisions_file.exists():
            try:
                data = json.loads(self.decisions_file.read_text())
                for item_id, decision_data in data.items():
                    self.decisions[item_id] = DocDecision(**decision_data)
            except Exception as e:
                print(f"Warning: Could not load doc decisions: {e}")

    def save(self):
        """Save decisions to storage."""
        try:
            data = {
                item_id: asdict(decision)
                for item_id, decision in self.decisions.items()
            }
            self.decisions_file.write_text(json.dumps(data, indent=2))
        except Exception as e:
            print(f"Warning: Could not save doc decisions: {e}")

    def get_decision(self, item_id: str) -> Optional[DocDecision]:
        """Get decision for a drift item."""
        return self.decisions.get(item_id)

    def set_decision(self, item_id: str, decision: str, description: str = None):
        """Set decision for a drift item."""
        from datetime import datetime

        self.decisions[item_id] = DocDecision(
            item=item_id,
            decision=decision,
            timestamp=datetime.now().isoformat(),
            description=description
        )
        self.save()

    def is_internal(self, item_id: str) -> bool:
        """Check if item was marked as internal."""
        decision = self.get_decision(item_id)
        return decision and decision.decision == 'internal'

    def is_deferred(self, item_id: str) -> bool:
        """Check if item was deferred."""
        decision = self.get_decision(item_id)
        return decision and decision.decision == 'deferred'

    def should_ask_again(self, item_id: str, defer_period_days: int = 7) -> bool:
        """
        Check if a deferred item should be asked about again.

        Args:
            item_id: The drift item identifier
            defer_period_days: Days to wait before asking again

        Returns:
            True if the defer period has expired
        """
        decision = self.get_decision(item_id)
        if not decision or decision.decision != 'deferred':
            return False

        from datetime import datetime, timedelta

        decision_time = datetime.fromisoformat(decision.timestamp)
        expiry_time = decision_time + timedelta(days=defer_period_days)

        return datetime.now() > expiry_time

    def get_pending_items(self, drift_items: List[DocDrift]) -> List[DocDrift]:
        """
        Filter drift items to only those that need user attention.

        Returns:
            List of drift items that are not marked as internal or recently deferred
        """
        pending = []

        for drift in drift_items:
            item_id = self._make_item_id(drift)

            # Skip if marked as internal
            if self.is_internal(item_id):
                continue

            # Skip if recently deferred
            if self.is_deferred(item_id) and not self.should_ask_again(item_id):
                continue

            pending.append(drift)

        return pending

    @staticmethod
    def _make_item_id(drift: DocDrift) -> str:
        """Create a unique ID for a drift item."""
        return f"{drift.type}:{drift.item}"


def check_drift_before_finish(project_dir: Path) -> Tuple[bool, List[DocDrift], DocDecisionStore]:
    """
    Main entry point for documentation drift detection in finish command.

    Args:
        project_dir: Path to the project directory

    Returns:
        Tuple of (has_drift, drift_items, decision_store)
    """
    checker = DocChecker(project_dir)
    store = DocDecisionStore(project_dir)

    # Detect all drift
    all_drift = checker.detect_all_drift()

    # Filter to only pending items (not already decided)
    pending_drift = store.get_pending_items(all_drift)

    has_drift = len(pending_drift) > 0

    return has_drift, pending_drift, store
