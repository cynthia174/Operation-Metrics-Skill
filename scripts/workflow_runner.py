"""Lightweight resumable execution-plan runner; business logic stays in adapters."""
from __future__ import annotations
import argparse, importlib, json, shlex, subprocess, sys, time
from pathlib import Path
from typing import Any
from validate_stage import StageValidationError, validate
from run_manifest import safe_load, safe_write, update_stage, now

RECOVERABLE = "RECOVERABLE"
USER_REQUIRED = "USER_REQUIRED"
NON_RECOVERABLE = "NON_RECOVERABLE"

def _load(path: Path) -> dict: return json.loads(path.read_text(encoding="utf-8"))
def _save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)

def _render(value: Any, root: Path) -> Any:
    if isinstance(value, str): return value.replace("{root}", str(root))
    if isinstance(value, list): return [_render(x, root) for x in value]
    return value

def _run_path(value: str | Path, root: Path) -> Path:
    """Resolve a plan path and reject paths outside the current run root."""
    path = Path(_render(str(value), root)).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise RuntimeError(f"path outside current run directory: {path}") from exc
    return path

def _agent_output_error(stage: dict, root: Path, output: Path) -> str | None:
    if not output.is_file():
        return f"agent output does not exist: {output}"
    if output.suffix.lower() != ".md":
        return f"agent output must be Markdown (.md): {output}"
    if not output.read_text(encoding="utf-8").strip():
        return f"agent output is empty: {output}"
    return None

def _agent_manifest(manifest_path: Path, stage: dict, root: Path, status: str,
                    started_at: str, output: Path, error: str | None = None) -> None:
    """Record Agent Interaction using the same manifest contract as deterministic stages."""
    manifest_stage = dict(stage)
    manifest_stage["inputs"] = [stage["prompt_file"], stage["context_file"]]
    manifest_stage["outputs"] = [str(output)]
    update_stage(manifest_path, manifest_stage, status, root, None, error)
    manifest = safe_load(manifest_path)
    rec = manifest.setdefault("stages", {}).setdefault(stage["id"], {})
    rec.update({
        "stage": stage["id"],
        "status": status,
        "prompt_file": str(_run_path(stage["prompt_file"], root)),
        "context_file": str(_run_path(stage["context_file"], root)),
        "output_file": str(output),
        "started_at": started_at,
        "evidence_input_references": rec.get("input", []),
    })
    if status == "DONE":
        rec["finished_at"] = now()
        rec["output_size"] = output.stat().st_size
    if error:
        rec["error"] = error
    manifest["pipeline_status"] = "FAILED" if status == "FAILED" else "RUNNING"
    safe_write(manifest_path, manifest)

def validate_definition_of_done(plan: dict, state: dict) -> None:
    """Completion is a plan-level contract, never inferred from one artifact."""
    required = plan.get("definition_of_done", {}).get("required_stages")
    if required is None:
        required = [s["id"] for s in plan.get("stages", [])]
    missing = [sid for sid in required if state.get("stages", {}).get(sid, {}).get("status") != "DONE"]
    if missing: raise RuntimeError(f"Definition of Done not satisfied: {missing}")

def execute(stage: dict, root: Path) -> None:
    ex = stage.get("executor")
    if not ex: raise RuntimeError("stage has no executor")
    if isinstance(ex, list):
        subprocess.run(_render(ex, root), cwd=root, check=True)
    elif isinstance(ex, dict) and "command" in ex:
        subprocess.run(_render(ex["command"], root), cwd=root, check=True)
    elif isinstance(ex, dict) and "callable" in ex:
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        mod, fn = ex["callable"].rsplit(":", 1)
        result = getattr(importlib.import_module(mod), fn)(stage=stage, root=root)
        if result is False: raise RuntimeError("adapter returned False")
    else: raise RuntimeError(f"unsupported executor: {ex}")

def run(plan_path: Path, state_path: Path, root: Path) -> dict:
    plan = _load(plan_path)
    state = _load(state_path) if state_path.exists() else {"workflow_status":"AWAITING_PLAN_APPROVAL", "stages":{}, "history":[]}
    if plan.get("requires_user_approval") and state.get("workflow_status") != "AUTONOMOUS_EXECUTION":
        raise RuntimeError("user approval required before autonomous execution")
    stages = {s["id"]: s for s in plan["stages"]}
    state.setdefault("stages", {}); state.setdefault("history", [])
    state["status"] = "RUNNING"; _save(state_path, state)
    manifest_path = root / "outputs/runtime/run_manifest.json"
    manifest = safe_load(manifest_path)
    manifest.setdefault("pipeline_status", "RUNNING"); manifest.setdefault("stages", {})
    safe_write(manifest_path, manifest)
    while True:
        done = {k for k,v in state["stages"].items() if v.get("status") == "DONE"}
        awaiting = [s for s in plan["stages"] if state["stages"].get(s["id"], {}).get("status") == "AWAITING_AGENT_INTERACTION"]
        if awaiting:
            stage = awaiting[0]; sid = stage["id"]
            rec = state["stages"][sid]
            try:
                output = _run_path(stage["output_file"], root)
                if sid == "summary_prompt":
                    dependencies = set(stage.get("depends_on", stage.get("dependencies", [])))
                    unfinished = sorted(dependencies - done)
                    if unfinished:
                        error = f"summary dependencies are not DONE: {unfinished}"
                        rec["status"] = "FAILED"; rec["error"] = error
                        state["workflow_status"] = "FAILED"; state["status"] = "FAILED"; _save(state_path, state)
                        _agent_manifest(manifest_path, stage, root, "FAILED", rec.get("started_at", now()), output, error)
                        return state
                error = _agent_output_error(stage, root, output)
            except (OSError, RuntimeError, UnicodeError) as exc:
                error = str(exc)
                output = root / "<invalid-agent-output>"
            if error:
                if "does not exist" in error:
                    state["workflow_status"] = "AWAITING_AGENT_INTERACTION"; state["status"] = "PAUSED"; _save(state_path, state)
                    return state
                rec["status"] = "FAILED"; rec["error"] = error
                state["workflow_status"] = "FAILED"; state["status"] = "FAILED"; _save(state_path, state)
                _agent_manifest(manifest_path, stage, root, "FAILED", rec.get("started_at", now()), output, error)
                return state
            rec.update({"status":"DONE", "finished_at":now(), "output_size":output.stat().st_size})
            rec.pop("error", None)
            state["history"].append({"stage":sid,"status":"DONE"}); done.add(sid)
            _save(state_path, state)
            _agent_manifest(manifest_path, stage, root, "DONE", rec.get("started_at", now()), output)
            state["workflow_status"] = "RUNNING"; state["status"] = "RUNNING"; _save(state_path, state)
            continue
        pending = [s for s in plan["stages"] if state["stages"].get(s["id"], {}).get("status", "PENDING") == "PENDING" and set(s.get("depends_on", s.get("dependencies", []))) <= done]
        if not pending:
            remaining = [s["id"] for s in plan["stages"] if state["stages"].get(s["id"], {}).get("status") != "DONE"]
            if remaining:
                state["workflow_status"] = "BLOCKED"; state["status"] = "BLOCKED"; _save(state_path, state); raise RuntimeError(f"no runnable stage; unresolved: {remaining}")
            validate_definition_of_done(plan, state)
            state["workflow_status"] = "DONE"; state["status"] = "DONE"; state["completed_at"] = time.time(); _save(state_path, state); return state
        stage = pending[0]; sid = stage["id"]; rec = state["stages"].setdefault(sid, {"status":"PENDING", "attempts":0})
        if stage.get("kind") == "agent_interaction":
            started_at = now()
            try:
                output = _run_path(stage["output_file"], root)
            except RuntimeError as exc:
                error = str(exc)
                rec.update({"status":"FAILED", "error":error, "finished_at":now()})
                state["workflow_status"] = "FAILED"; state["status"] = "FAILED"; _save(state_path, state)
                _agent_manifest(manifest_path, stage, root, "FAILED", started_at, root / "<invalid-agent-output>", error)
                return state
            rec.update({"status":"AWAITING_AGENT_INTERACTION", "prompt_file":stage.get("prompt_file"), "context_file":stage.get("context_file"), "output_file":stage.get("output_file"), "manifest":stage.get("manifest"), "started_at":started_at})
            state["workflow_status"] = "AWAITING_AGENT_INTERACTION"; state["status"] = "PAUSED"; _save(state_path, state)
            _agent_manifest(manifest_path, stage, root, "AWAITING_AGENT_INTERACTION", started_at, output)
            return state
        max_attempts = int(stage.get("retry_policy", {}).get("max_attempts", 1))
        while rec.get("attempts", 0) < max_attempts:
            rec["status"] = "RUNNING"; rec["attempts"] = rec.get("attempts", 0) + 1; _save(state_path, state)
            started = time.perf_counter(); update_stage(manifest_path, stage, "RUNNING", root, started)
            try:
                execute(stage, root); validate(stage, root)
            except (subprocess.CalledProcessError, StageValidationError, OSError, RuntimeError) as exc:
                rec["error"] = str(exc); rec["error_class"] = stage.get("retry_policy", {}).get("on_error", RECOVERABLE)
                rec["status"] = "PENDING" if rec["error_class"] == RECOVERABLE and rec["attempts"] < max_attempts else rec["error_class"]
                _save(state_path, state)
                update_stage(manifest_path, stage, "FAILED", root, started, str(exc))
                if rec["status"] == "PENDING": continue
                state["status"] = rec["status"]; _save(state_path, state); raise
            rec["status"] = "DONE"; rec.pop("error", None); state["history"].append({"stage":sid,"attempt":rec["attempts"],"status":"DONE"}); _save(state_path, state)
            update_stage(manifest_path, stage, "DONE", root, started)
            break
    return state

def main() -> None:
    ap=argparse.ArgumentParser(description="Run and resume a complete execution plan")
    ap.add_argument("--plan", required=True, type=Path); ap.add_argument("--state", required=True, type=Path); ap.add_argument("--root", type=Path, default=Path.cwd())
    args=ap.parse_args(); result=run(args.plan, args.state, args.root); print(json.dumps({"status":result["status"],"state":str(args.state)}, ensure_ascii=False))
if __name__ == "__main__": main()
