import hashlib, json
from datetime import datetime, timezone
from pathlib import Path
from .state import RuntimeState, RuntimeStateError, STAGES

PLAN_VERSION = "2.0"
ACTION_MAP = {
    "Normalize": "preflight.normalized_data",
    "Validate Normalized Data": "runtime.validate_normalized_data",
    "Aggregate Channel": "src/aggregate_metrics.py --channel-output",
    "Aggregate Category": "src/aggregate_metrics.py --category-output",
    "Acquisition Metrics": "src/metrics/channel.py",
    "Advertising Metrics": "src/metrics/channel.py",
    "Run Rules": "src/run_rules.py",
    "Rule Result Validation": "src/rule_result.py",
    "Five-Screen Report": "scripts/build_vol01_report.py",
    "Fact QA": "runtime.fact_qa",
    "Structure QA": "semantic_blocks_report.qa.json",
    "Semantic Blocks": "semantic_blocks.json",
    "DOCX": "scripts/semantic_blocks_to_docx.py",
    "DOCX QA": "runtime.docx_qa",
    "OOXML QA": "runtime.ooxml_qa",
    "Final Delivery": "runtime.final_delivery",
}


def create_plan(preflight: dict, output_path):
    steps = []
    for i, name in enumerate(STAGES, 1):
        steps.append({"id": f"stage_{i:02d}", "name": name,
                      "depends_on": [f"stage_{i-1:02d}"] if i > 1 else [],
                      "inputs": ["preflight.json"] if i == 1 else [f"stage_{i-1:02d}"],
                      "action": ACTION_MAP[name], "expected_outputs": [f"outputs/runtime/{name.lower().replace(' ', '_')}.json"],
                      "validation": "stage completion and declared outputs", "failure_policy": "block_and_persist"})
    plan = {"plan_version": PLAN_VERSION, "workflow": "operation_metrics", "goal": preflight.get("goal", "Generate evidence-bounded operation metrics report"),
            "requires_user_approval": True, "status": "AWAITING_PLAN_APPROVAL", "preflight_summary": preflight.get("summary", {}),
            "field_resolution_summary": preflight.get("field_resolution", {}), "rule_coverage": preflight.get("rule_coverage", {}),
            "data_gaps": preflight.get("data_gaps", []), "steps": steps}
    path = Path(output_path); path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return plan


def create_run_manifest(run_id, plan_version, input_refs, output_paths, output_path, status="CREATED"):
    def ref(x):
        path = Path(x)
        item = {"path": str(path)}
        if path.exists() and path.is_file():
            item["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        return item
    manifest = {"run_id": run_id, "plan_version": plan_version,
                "input_refs": [ref(x) for x in input_refs], "output_paths": [str(x) for x in output_paths],
                "timestamps": {"created_at": datetime.now(timezone.utc).isoformat()}, "status": status}
    path = Path(output_path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


class WorkflowRunner:
    def __init__(self, runtime_dir):
        self.dir = Path(runtime_dir); self.plan_path = self.dir / "execution_plan.json"; self.state_path = self.dir / "task_state.json"
    def approve(self, plan_version):
        state = RuntimeState.load(self.state_path); state.approve(plan_version)
    def resume(self):
        plan = json.loads(self.plan_path.read_text(encoding="utf-8")); state = RuntimeState.load(self.state_path)
        if state.payload["plan_version"] != plan["plan_version"] or (state.payload["approved_plan_version"] and state.payload["approved_plan_version"] != plan["plan_version"]):
            raise RuntimeStateError("plan_version mismatch; refusing resume")
        return state.next_stage()
    def checkpoint(self, stage_id, status="done"):
        RuntimeState.load(self.state_path).transition_stage(stage_id, status)
