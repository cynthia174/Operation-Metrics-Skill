import json
from pathlib import Path

from scripts.run_manifest import UNKNOWN_LINEAGE, safe_write, summarize, update_stage


def test_manifest_initialization_and_stage_update(tmp_path):
    path = tmp_path / "run_manifest.json"
    safe_write(path, {"schema_version": "1.0", "pipeline_status": "RUNNING", "stages": {}})
    output = tmp_path / "metrics.csv"
    output.write_text("month,channel,cost\n2025-01,A,1\n", encoding="utf-8")
    stage = {"id": "metrics", "outputs": ["metrics.csv"]}
    update_stage(path, stage, "DONE", tmp_path, 0)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["stages"]["metrics"]["status"] == "DONE"
    assert data["stages"]["metrics"]["output"][0]["row_count"] == 1


def test_failure_persistence_and_unknown_lineage(tmp_path):
    path = tmp_path / "run_manifest.json"
    safe_write(path, {"stages": {"metrics": {"status": "DONE"}}, "pipeline_status": "RUNNING"})
    update_stage(path, {"id": "report", "outputs": []}, "FAILED", tmp_path, error="missing facts")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["pipeline_status"] == "FAILED"
    assert data["stages"]["report"]["errors"] == ["missing facts"]
    assert UNKNOWN_LINEAGE["status"] == "unknown"
    assert data["stages"]["metrics"]["status"] == "DONE"


def test_manifest_write_failure_is_best_effort(tmp_path, monkeypatch):
    path = tmp_path / "run_manifest.json"
    monkeypatch.setattr(Path, "replace", lambda self, target: (_ for _ in ()).throw(OSError("disk full")))
    safe_write(path, {"pipeline_status": "RUNNING"})
    assert not path.exists()


def test_rules_zero_trigger_is_successful_observation(tmp_path):
    result = tmp_path / "rule_results.json"
    result.write_text(json.dumps({"results": [{"hit": False}, {"hit": False}]}), encoding="utf-8")
    summary = summarize({"id": "rules", "outputs": ["rule_results.json"]}, tmp_path)
    assert summary["evaluated_count"] == 2
    assert summary["triggered_count"] == 0
    assert summary["skipped_count"] == 0


def test_future_stage_and_open_summary_are_not_schema_rejected(tmp_path):
    path = tmp_path / "run_manifest.json"
    safe_write(path, {"stages": {}})
    custom = {"custom_metric": 123, "some_future_field": "abc"}
    update_stage(path, {"id": "future_prompt_stage", "outputs": []}, "DONE", tmp_path, summary=custom)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["stages"]["future_prompt_stage"]["summary"] == custom
