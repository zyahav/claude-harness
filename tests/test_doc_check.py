import unittest
import tempfile
import shutil
import json
from pathlib import Path
from datetime import datetime, timedelta
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import doc_check


class TestDocDrift(unittest.TestCase):
    """Test DocDrift dataclass."""

    def test_create_doc_drift(self):
        """Test creating a DocDrift instance."""
        drift = doc_check.DocDrift(
            type='cli_flag',
            item='--test-flag',
            location='README.md',
            context='Test context'
        )
        self.assertEqual(drift.type, 'cli_flag')
        self.assertEqual(drift.item, '--test-flag')
        self.assertEqual(drift.location, 'README.md')
        self.assertEqual(drift.context, 'Test context')


class TestDocDecision(unittest.TestCase):
    """Test DocDecision dataclass."""

    def test_create_doc_decision(self):
        """Test creating a DocDecision instance."""
        decision = doc_check.DocDecision(
            item='cli_flag:--test-flag',
            decision='internal',
            timestamp=datetime.now().isoformat(),
            description='Test description'
        )
        self.assertEqual(decision.decision, 'internal')
        self.assertIsNotNone(decision.timestamp)


class TestDocChecker(unittest.TestCase):
    """Test DocChecker class."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.test_dir_path = Path(self.test_dir)

        # Create sample README.md
        self.readme_path = self.test_dir_path / "README.md"
        self.readme_path.write_text("""
# Test Project

## Usage

```bash
c-harness start my-app `--repo-path` ../target `--mode` greenfield
c-harness finish my-app `--force`
```
""")

        # Create sample AGENT_GUIDE.md
        self.agent_guide_path = self.test_dir_path / "AGENT_GUIDE.md"
        self.agent_guide_path.write_text("""
# Agent Guide

## Core Architecture

- **`harness.py`**: Main CLI entry point
- **`lifecycle.py`**: Git lifecycle management
""")

        # Create sample harness.py with CLI flags
        self.harness_path = self.test_dir_path / "harness.py"
        self.harness_path.write_text("""
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--test-flag", help="Test flag")
parser.add_argument("--another-flag", help="Another flag")
parser.add_argument("--mode", choices=["greenfield", "brownfield"])
""")

        # Create sample public Python files
        (self.test_dir_path / "public_module.py").write_text("# Public module")
        (self.test_dir_path / "another_public.py").write_text("# Another public module")
        (self.test_dir_path / "_private.py").write_text("# Private module")
        (self.test_dir_path / "test_should_be_ignored.py").write_text("# Test file")

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_dir)

    def test_extract_cli_flags(self):
        """Test extracting CLI flags from harness.py."""
        checker = doc_check.DocChecker(self.test_dir_path)
        flags = checker._extract_cli_flags(self.harness_path)

        self.assertIn('--test-flag', flags)
        self.assertIn('--another-flag', flags)
        self.assertIn('--mode', flags)

    def test_extract_documented_flags(self):
        """Test extracting documented flags from README."""
        checker = doc_check.DocChecker(self.test_dir_path)
        flags = checker._extract_documented_flags(self.readme_path)

        # README has --repo-path, --mode, --force
        self.assertIn('--repo-path', flags)
        self.assertIn('--mode', flags)
        self.assertIn('--force', flags)

    def test_detect_cli_flag_drift(self):
        """Test detection of undocumented CLI flags."""
        checker = doc_check.DocChecker(self.test_dir_path)
        drift = checker.detect_cli_flag_drift(self.harness_path)

        # --test-flag and --another-flag are in harness.py but not in README
        drift_items = [d for d in drift if d.item == '--test-flag']
        self.assertEqual(len(drift_items), 1)

        drift_items = [d for d in drift if d.item == '--another-flag']
        self.assertEqual(len(drift_items), 1)

        # --mode is documented, so should not appear in drift
        drift_items = [d for d in drift if d.item == '--mode']
        self.assertEqual(len(drift_items), 0)

    def test_get_public_python_files(self):
        """Test getting public Python files."""
        checker = doc_check.DocChecker(self.test_dir_path)
        files = checker._get_public_python_files(self.test_dir_path)

        # Should include public files
        self.assertIn('public_module.py', files)
        self.assertIn('another_public.py', files)

        # Should exclude private and test files
        self.assertNotIn('_private.py', files)
        self.assertNotIn('test_should_be_ignored.py', files)

    def test_extract_documented_files(self):
        """Test extracting documented files from AGENT_GUIDE."""
        checker = doc_check.DocChecker(self.test_dir_path)
        files = checker._extract_documented_files(self.agent_guide_path)

        # AGENT_GUIDE has harness.py and lifecycle.py
        self.assertIn('harness.py', files)
        self.assertIn('lifecycle.py', files)

    def test_detect_public_file_drift(self):
        """Test detection of undocumented public files."""
        checker = doc_check.DocChecker(self.test_dir_path)
        drift = checker.detect_public_file_drift(self.agent_guide_path)

        # public_module.py and another_public.py are not documented
        drift_items = [d for d in drift if d.item == 'public_module.py']
        self.assertEqual(len(drift_items), 1)

        drift_items = [d for d in drift if d.item == 'another_public.py']
        self.assertEqual(len(drift_items), 1)

    def test_detect_all_drift(self):
        """Test detection of all drift types."""
        checker = doc_check.DocChecker(self.test_dir_path)
        drift = checker.detect_all_drift()

        # Should have both CLI flag drift and public file drift
        types = set(d.type for d in drift)
        self.assertIn('cli_flag', types)
        self.assertIn('public_file', types)

        # Should have multiple items
        self.assertGreater(len(drift), 0)


class TestDocDecisionStore(unittest.TestCase):
    """Test DocDecisionStore class."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.test_dir_path = Path(self.test_dir)
        self.store = doc_check.DocDecisionStore(self.test_dir_path)

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_dir)

    def test_create_harness_directory(self):
        """Test that .harness directory is created."""
        self.assertTrue(self.store.decisions_dir.exists())
        self.assertEqual(self.store.decisions_dir.name, '.harness')

    def test_set_and_get_decision(self):
        """Test setting and getting decisions."""
        item_id = 'cli_flag:--test-flag'
        self.store.set_decision(item_id, 'internal', 'Test description')

        decision = self.store.get_decision(item_id)
        self.assertIsNotNone(decision)
        self.assertEqual(decision.decision, 'internal')
        self.assertEqual(decision.description, 'Test description')

    def test_save_and_load(self):
        """Test persisting decisions to disk."""
        item_id = 'cli_flag:--test-flag'
        self.store.set_decision(item_id, 'deferred', 'Test description')

        # Create new store instance to test loading
        new_store = doc_check.DocDecisionStore(self.test_dir_path)
        decision = new_store.get_decision(item_id)

        self.assertIsNotNone(decision)
        self.assertEqual(decision.decision, 'deferred')

    def test_is_internal(self):
        """Test checking if item is marked as internal."""
        item_id = 'cli_flag:--test-flag'
        self.assertFalse(self.store.is_internal(item_id))

        self.store.set_decision(item_id, 'internal')
        self.assertTrue(self.store.is_internal(item_id))

    def test_is_deferred(self):
        """Test checking if item is deferred."""
        item_id = 'cli_flag:--test-flag'
        self.assertFalse(self.store.is_deferred(item_id))

        self.store.set_decision(item_id, 'deferred')
        self.assertTrue(self.store.is_deferred(item_id))

    def test_should_ask_again(self):
        """Test defer period expiration."""
        item_id = 'cli_flag:--test-flag'

        # No decision = don't ask
        self.assertFalse(self.store.should_ask_again(item_id))

        # Just deferred = don't ask yet
        self.store.set_decision(item_id, 'deferred')
        self.assertFalse(self.store.should_ask_again(item_id))

        # Modify timestamp to simulate expired defer
        decision_data = json.loads(self.store.decisions_file.read_text())
        old_time = (datetime.now() - timedelta(days=8)).isoformat()
        decision_data[item_id]['timestamp'] = old_time
        self.store.decisions_file.write_text(json.dumps(decision_data))

        # Reload store
        self.store._load()
        self.assertTrue(self.store.should_ask_again(item_id))

    def test_get_pending_items(self):
        """Test filtering drift items to pending ones."""
        drift_items = [
            doc_check.DocDrift(
                type='cli_flag',
                item='--internal-flag',
                location='README.md',
                context='Internal flag'
            ),
            doc_check.DocDrift(
                type='cli_flag',
                item='--public-flag',
                location='README.md',
                context='Public flag'
            ),
        ]

        # Mark --internal-flag as internal
        self.store.set_decision('cli_flag:--internal-flag', 'internal')

        pending = self.store.get_pending_items(drift_items)

        # Only --public-flag should be pending
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].item, '--public-flag')


class TestIntegration(unittest.TestCase):
    """Integration tests for doc_check module."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.test_dir_path = Path(self.test_dir)

        # Create minimal project structure
        self.readme_path = self.test_dir_path / "README.md"
        self.readme_path.write_text("# Test\n")

        self.agent_guide_path = self.test_dir_path / "AGENT_GUIDE.md"
        self.agent_guide_path.write_text("# Guide\n")

        self.harness_path = self.test_dir_path / "harness.py"
        self.harness_path.write_text('parser.add_argument("--new-flag")')

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_dir)

    def test_check_drift_before_finish(self):
        """Test main entry point for drift detection."""
        has_drift, drift_items, store = doc_check.check_drift_before_finish(self.test_dir_path)

        # Should detect drift
        self.assertTrue(has_drift)
        self.assertGreater(len(drift_items), 0)

        # Should return valid store
        self.assertIsInstance(store, doc_check.DocDecisionStore)

    def test_no_drift_scenario(self):
        """Test scenario with no documentation drift."""
        # Document the flag in README with backticks
        self.readme_path.write_text('# Test\n\nUsage: `--new-flag`\n')
        
        # Document harness.py in AGENT_GUIDE
        self.agent_guide_path.write_text('# Guide\n\n- **`harness.py`**: CLI entry\n')

        has_drift, drift_items, store = doc_check.check_drift_before_finish(self.test_dir_path)

        # Should not detect any drift now
        self.assertEqual(len(drift_items), 0)


if __name__ == "__main__":
    unittest.main()
