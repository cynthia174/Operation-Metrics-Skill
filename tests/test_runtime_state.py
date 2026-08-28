import json
import tempfile
import unittest
from pathlib import Path

from src.runtime.runner import WorkflowRunner, create_plan
from src.runtime.plan_view import render_plan
from src.runtime.state import RuntimeState, RuntimeStateError, STAGES


class RuntimeStateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_plan_generation_schema_shape_and_view(self):
        plan_path = self.root / "execution_plan.json"
        plan = create_plan({"goal": "test", "summary": {"rows": 1}, "data_gaps": ["x"]}, plan_path)
        self.assertEqual(len(plan["steps"]), 16)
        self.assertEqual({s["name"] for s in plan["steps"]}, set(STAGES))
        view = render_plan(plan_path)
        self.assertIn("Task Goal: test", view)
        self.assertIn("Current Status: AWAITING_PLAN_APPROVAL", view)
        self.assertIn("Data Gaps", view)

    def test_approval_checkpoint_resume_and_no_duplicate_done_stage(self):
        plan_path = self.root / "execution_plan.json"
        create_plan({}, plan_path)
        state_path = self.root / "task_state.json"
        state = RuntimeState(state_path); state.set_plan("2.0")
        runner = WorkflowRunner(self.root)
        runner.approve("2.0")
        self.assertEqual(json.loads(state_path.read_text())["workflow_status"], "AUTONOMOUS_EXECUTION")
        runner.checkpoint("Normalize")
        self.assertEqual(runner.resume()["id"], "stage_02")
        runner.checkpoint("Validate Normalized Data")
        self.assertEqual(runner.resume()["id"], "stage_03")

    def test_mismatched_approval_and_resume_are_rejected(self):
        plan_path = self.root / "execution_plan.json"
        create_plan({}, plan_path)
        state_path = self.root / "task_state.json"
        RuntimeState(state_path).set_plan("1.0")
        runner = WorkflowRunner(self.root)
        with self.assertRaises(RuntimeStateError): runner.approve("2.0")
        with self.assertRaises(RuntimeStateError): runner.resume()


if __name__ == "__main__":
    unittest.main()
