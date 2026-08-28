import json
from datetime import datetime, timezone
from pathlib import Path


STAGES = [
    "Normalize", "Validate Normalized Data", "Aggregate Channel", "Aggregate Category",
    "Acquisition Metrics", "Advertising Metrics", "Run Rules", "Rule Result Validation",
    "Five-Screen Report", "Fact QA", "Structure QA", "Semantic Blocks", "DOCX",
    "DOCX QA", "OOXML QA", "Final Delivery",
]
WORKFLOW_TRANSITIONS = {
    "INIT": {"PREFLIGHT"}, "PREFLIGHT": {"AWAITING_PLAN_APPROVAL"},
    "AWAITING_PLAN_APPROVAL": {"AUTONOMOUS_EXECUTION"},
    "AUTONOMOUS_EXECUTION": {"VALIDATING", "DONE"}, "VALIDATING": {"AUTONOMOUS_EXECUTION", "DONE"},
    "DONE": set(), "BLOCKED": set(), "FAILED": set(),
}


def _now():
    return datetime.now(timezone.utc).isoformat()


class RuntimeStateError(ValueError):
    pass


class RuntimeState:
    def __init__(self, path: Path, payload=None):
        self.path = Path(path)
        self.payload = payload or self.initial()

    @staticmethod
    def initial():
        return {"workflow": "operation_metrics", "workflow_status": "INIT",
                "plan_version": None, "approved_plan_version": None,
                "current_stage": None,
                "stages": [{"id": f"stage_{i:02d}", "name": s, "status": "pending"} for i, s in enumerate(STAGES, 1)]}

    @classmethod
    def load(cls, path):
        return cls(Path(path), json.loads(Path(path).read_text(encoding="utf-8")))

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def set_plan(self, version):
        self.payload["plan_version"] = version
        self.payload["workflow_status"] = "AWAITING_PLAN_APPROVAL"
        self.save()

    def transition_workflow(self, status):
        current = self.payload["workflow_status"]
        if status not in WORKFLOW_TRANSITIONS.get(current, set()):
            raise RuntimeStateError(f"invalid workflow transition: {current} -> {status}")
        self.payload["workflow_status"] = status
        self.save()

    def approve(self, version):
        if self.payload["workflow_status"] != "AWAITING_PLAN_APPROVAL":
            raise RuntimeStateError("approval is only valid while awaiting plan approval")
        if version != self.payload["plan_version"]:
            raise RuntimeStateError("approved plan_version does not match execution plan")
        self.payload["approved_plan_version"] = version
        self.payload["workflow_status"] = "AUTONOMOUS_EXECUTION"
        self.save()

    def next_stage(self):
        return next((s for s in self.payload["stages"] if s["status"] not in {"done"}), None)

    def transition_stage(self, stage_id, status):
        if status not in {"pending", "running", "done", "blocked", "failed"}:
            raise RuntimeStateError(f"invalid stage status: {status}")
        stage = next((s for s in self.payload["stages"] if s["id"] == stage_id or s.get("name") == stage_id), None)
        if not stage:
            raise RuntimeStateError(f"unknown stage: {stage_id}")
        stage["status"] = status
        self.payload["current_stage"] = stage["id"] if status != "done" else (self.next_stage() or {}).get("id")
        if status == "done" and not self.next_stage():
            self.payload["workflow_status"] = "DONE"
        elif status in {"blocked", "failed"}:
            self.payload["workflow_status"] = status.upper()
        elif status == "running":
            self.payload["workflow_status"] = "VALIDATING" if stage.get("name") in {"Fact QA", "Structure QA", "DOCX QA", "OOXML QA"} else "AUTONOMOUS_EXECUTION"
        self.save()
