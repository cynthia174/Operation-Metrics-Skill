import json
from pathlib import Path

def render_plan(plan_path):
    p = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    lines = ["# /plan", "", f"Task Goal: {p['goal']}", f"Current Status: {p['status']}", "",
             "## Preflight summary", json.dumps(p.get("preflight_summary", {}), ensure_ascii=False),
             "", "## Field Resolution summary", json.dumps(p.get("field_resolution_summary", {}), ensure_ascii=False),
             "", "## Rule Coverage", json.dumps(p.get("rule_coverage", {}), ensure_ascii=False),
             "", "## Data Gaps", json.dumps(p.get("data_gaps", []), ensure_ascii=False), "", "## 后续步骤"]
    lines += [f"- {s['name']} (`{s['action']}`)" for s in p["steps"]]
    lines += ["", "## Outputs", "- outputs/runtime/execution_plan.json", "- outputs/runtime/task_state.json", "- outputs/runtime/run_manifest.json", "", "当前状态: AWAITING_PLAN_APPROVAL"]
    return "\n".join(lines) + "\n"
