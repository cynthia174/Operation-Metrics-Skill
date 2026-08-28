import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from workflow_runner import run


def _plan(tmp_path):
    stages = []
    previous = []
    for name in ["channel", "product", "efficiency", "growth_quality", "summary"]:
        sid = f"{name}_prompt"
        stages.append({
            "id": sid, "kind": "agent_interaction", "depends_on": previous[:],
            "prompt_file": str(tmp_path / "prompts" / f"{name}.md"),
            "context_file": str(tmp_path / "contexts" / f"{name}.json"),
            "output_file": str(tmp_path / "modules" / f"{name}.md"),
        })
        previous = [sid]
    stages += [{"id": "assemble", "depends_on": ["summary_prompt"], "executor": [sys.executable, "-c", "from pathlib import Path; Path('assembled').write_text('ok')"], "outputs": ["assembled"]}]
    plan = {"stages": stages, "definition_of_done": {"required_stages": [x["id"] for x in stages]}}
    path = tmp_path / "plan.json"; path.write_text(json.dumps(plan), encoding="utf-8")
    state = tmp_path / "state.json"; state.write_text(json.dumps({"workflow_status": "AUTONOMOUS_EXECUTION", "stages": {}, "history": []}), encoding="utf-8")
    for stage in stages[:5]:
        Path(stage["prompt_file"]).parent.mkdir(parents=True, exist_ok=True); Path(stage["prompt_file"]).write_text("prompt", encoding="utf-8")
        Path(stage["context_file"]).parent.mkdir(parents=True, exist_ok=True); Path(stage["context_file"]).write_text("{}", encoding="utf-8")
    return plan, path, state


def test_agent_stage_waits_then_resumes_to_next(tmp_path):
    plan, plan_path, state_path = _plan(tmp_path)
    first = run(plan_path, state_path, tmp_path)
    assert first["status"] == "PAUSED"
    assert first["workflow_status"] == "AWAITING_AGENT_INTERACTION"
    Path(plan["stages"][0]["output_file"]).parent.mkdir(parents=True, exist_ok=True)
    Path(plan["stages"][0]["output_file"]).write_text("# channel\n", encoding="utf-8")
    second = run(plan_path, state_path, tmp_path)
    assert second["stages"]["channel_prompt"]["status"] == "DONE"
    assert second["stages"]["product_prompt"]["status"] == "AWAITING_AGENT_INTERACTION"


def test_agent_missing_output_stays_awaiting(tmp_path):
    _, plan_path, state_path = _plan(tmp_path)
    run(plan_path, state_path, tmp_path)
    again = run(plan_path, state_path, tmp_path)
    assert again["workflow_status"] == "AWAITING_AGENT_INTERACTION"


def test_agent_invalid_outputs_fail(tmp_path):
    plan, plan_path, state_path = _plan(tmp_path)
    run(plan_path, state_path, tmp_path)
    output = Path(plan["stages"][0]["output_file"]); output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("   ", encoding="utf-8")
    failed = run(plan_path, state_path, tmp_path)
    assert failed["status"] == "FAILED"
    assert failed["stages"]["channel_prompt"]["status"] == "FAILED"


def test_all_five_agent_stages_resume_in_order(tmp_path):
    plan, plan_path, state_path = _plan(tmp_path)
    for index, stage in enumerate(plan["stages"][:5]):
        waiting = run(plan_path, state_path, tmp_path)
        assert waiting["workflow_status"] == "AWAITING_AGENT_INTERACTION"
        output = Path(stage["output_file"]); output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(f"# {stage['id']}\n", encoding="utf-8")
        resumed = run(plan_path, state_path, tmp_path)
        assert resumed["stages"][stage["id"]]["status"] == "DONE"
        if index < 4:
            assert resumed["workflow_status"] == "AWAITING_AGENT_INTERACTION"
    final = json.loads(state_path.read_text(encoding="utf-8"))
    assert all(final["stages"][f"{name}_prompt"]["status"] == "DONE" for name in ["channel", "product", "efficiency", "growth_quality", "summary"])
    assert final["stages"]["assemble"]["status"] == "DONE"


def test_agent_output_outside_run_fails(tmp_path):
    plan, plan_path, state_path = _plan(tmp_path)
    outside = tmp_path.parent / "historical-channel.md"
    plan["stages"][0]["output_file"] = str(outside)
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    failed = run(plan_path, state_path, tmp_path)
    assert failed["status"] == "FAILED"
    assert failed["stages"]["channel_prompt"]["status"] == "FAILED"


def test_summary_cannot_complete_before_dependencies(tmp_path):
    plan, plan_path, state_path = _plan(tmp_path)
    summary = plan["stages"][4]
    state = {"workflow_status": "AUTONOMOUS_EXECUTION", "status": "PAUSED", "history": [], "stages": {
        summary["id"]: {"status": "AWAITING_AGENT_INTERACTION", "started_at": "now"}
    }}
    state_path.write_text(json.dumps(state), encoding="utf-8")
    Path(summary["output_file"]).parent.mkdir(parents=True, exist_ok=True)
    Path(summary["output_file"]).write_text("# summary\n", encoding="utf-8")
    result = run(plan_path, state_path, tmp_path)
    assert result["status"] == "FAILED"
    assert result["stages"]["summary_prompt"]["status"] == "FAILED"
