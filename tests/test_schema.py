import unittest
import json
import tempfile
import shutil
from pathlib import Path
import schema

class TestSchema(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.handoff_path = Path(self.test_dir) / "handoff.json"

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_valid_handoff(self):
        """Test parsing a valid handoff.json file."""
        data = {
            "meta": {"project": "test-proj"},
            "tasks": [
                {
                    "id": "1", "category": "api", "title": "T1", "description": "D1", 
                    "acceptance_criteria": ["ac1"], "passes": False
                },
                {
                    "id": "2", "category": "api", "title": "T2", "description": "D2", 
                    "acceptance_criteria": ["ac2"], "passes": False
                },
                {
                    "id": "3", "category": "api", "title": "T3", "description": "D3", 
                    "acceptance_criteria": ["ac3"], "passes": True
                }
            ]
        }
        with open(self.handoff_path, "w") as f:
            json.dump(data, f)

        handoff = schema.load_handoff(self.handoff_path)
        passing, total = handoff.count_passing()
        
        self.assertEqual(total, 3)
        self.assertEqual(passing, 1)

    def test_invalid_json_format(self):
        """Test handling of malformed JSON."""
        with open(self.handoff_path, "w") as f:
            f.write("{ invalid json }")

        with self.assertRaises(json.JSONDecodeError):
            schema.load_handoff(self.handoff_path)

    def test_missing_tasks_field(self):
        """Test validation for missing required fields."""
        data = {
            "meta": {"project": "test-proj"},
            # 'tasks' is missing
        }
        with open(self.handoff_path, "w") as f:
            json.dump(data, f)
            
        handoff = schema.load_handoff(self.handoff_path)
        # It should return empty tasks list, but validation should fail if we call validate()
        errors = handoff.validate()
        self.assertIn("Handoff has no tasks", errors)

    def test_task_count_logic(self):
        """Verify task counting logic directly."""
        # Create tasks manually
        t1 = schema.Task(
            id="1", category="api", title="t1", description="d1", 
            acceptance_criteria=["ac"], passes=True
        )
        t2 = schema.Task(
            id="2", category="api", title="t2", description="d2", 
            acceptance_criteria=["ac"], passes=False
        )
        
        handoff = schema.Handoff(
            meta=schema.HandoffMeta(project="test"), 
            tasks=[t1, t2]
        )
        passing, total = handoff.count_passing()
        self.assertEqual(total, 2)
        self.assertEqual(passing, 1)

if __name__ == "__main__":
    unittest.main()
