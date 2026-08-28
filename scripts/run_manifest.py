"""Best-effort, dependency-free run manifest persistence and artifact summaries."""
from __future__ import annotations

import csv
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


UNKNOWN_LINEAGE = {"status": "unknown", "reason": "consumer lineage is not emitted by current stage"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def file_ref(path: Path, root: Path | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {"path": str(path)}
    if path.is_file():
        item["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        item["size_bytes"] = path.stat().st_size
    if root:
        try: item["relative_path"] = str(path.resolve().relative_to(root.resolve()))
        except ValueError: pass
    return item


def csv_summary(path: Path, root: Path) -> dict[str, Any]:
    result = file_ref(path, root)
    if path.is_file():
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle); rows = list(reader)
        result["row_count"] = len(rows)
        result["columns"] = reader.fieldnames or []
        result["metric_types"] = [x for x in (reader.fieldnames or []) if x not in {"month", "channel", "category", "is_complete_month"}]
    return result


def summarize(stage: dict[str, Any], root: Path) -> dict[str, Any]:
    sid = stage.get("id", "")
    outputs = [root / x for x in stage.get("outputs", [])]
    summary: dict[str, Any] = {}
    if sid == "preflight":
        data = _json(outputs[0]); resolutions = data.get("field_resolution", [])
        summary.update(mapped_fields=[x.get("canonical_field") for x in resolutions if x.get("status") == "mapped"],
                       missing_fields=[x.get("canonical_field") for x in resolutions if x.get("status") == "missing"],
                       source_row_count=sum(x.get("row_count", 0) for x in data.get("discoveries", [])),
                       warnings=data.get("data_gaps", []))
    elif sid == "metrics":
        files = [csv_summary(x, root) for x in outputs if x.suffix.lower() == ".csv"]
        summary["generated_metric_files"] = files
        summary["metric_families"] = [x.get("relative_path", x["path"]).split("_")[0] for x in files]
        summary["metric_types"] = sorted({c for x in files for c in x.get("metric_types", [])})
    elif sid == "rules":
        data = _json(next(x for x in outputs if x.suffix.lower() == ".json"))
        results = data.get("results", []); summary.update(evaluated_count=len(results), triggered_count=sum(r.get("hit") is True for r in results), skipped_count=0)
    elif sid == "capability_facts":
        caps = _json(next(x for x in outputs if x.name == "capabilities.json"))
        summary["unavailable_capabilities"] = [{"capability_id": x.get("capability_id"), "reason": x.get("unavailable_reason")} for x in caps.get("capabilities", []) if x.get("status") == "UNAVAILABLE"]
    elif sid == "report":
        data = _json(outputs[0]); summary.update(metric_facts_available=data.get("facts_count", 0), rule_facts_available=None,
                       facts_used=UNKNOWN_LINEAGE, facts_unused=UNKNOWN_LINEAGE,
                       fallback=not bool(data.get("facts_count")) or not any("规则与跨周期判断" in str(x) for x in data.get("blocks", [])))
    elif sid == "semantic_blocks":
        data = _json(outputs[0]); blocks = data.get("blocks", []); summary.update(block_count=len(blocks), block_types=sorted({x.get("type") for x in blocks if isinstance(x, dict)}))
    elif sid == "docx":
        path = next((x for x in outputs if x.suffix.lower() == ".docx"), outputs[0]); summary.update(output_path=str(path), generation_status="generated" if path.is_file() else "missing")
        qa = root / "outputs/runtime/report.qa.json"
        if qa.is_file(): summary["qa"] = _json(qa)
    return summary


def safe_load(path: Path) -> dict[str, Any]:
    try: return _json(path)
    except Exception: return {}


def safe_write(path: Path, manifest: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(path.name + ".tmp")
        temp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temp.replace(path)
    except Exception:
        return


def update_stage(path: Path, stage: dict[str, Any], status: str, root: Path, started: float | None = None, error: str | None = None, summary: dict[str, Any] | None = None) -> None:
    manifest = safe_load(path); stages = manifest.setdefault("stages", {}); sid = stage.get("id", "unknown")
    rec = stages.setdefault(sid, {"status": "PENDING", "warnings": [], "errors": []})
    try:
        rec["status"] = status
        rec["input"] = [file_ref(root / x, root) for x in stage.get("inputs", []) if (root / x).exists()]
        rec["output"] = [csv_summary(root / x, root) if (root / x).suffix.lower() == ".csv" else file_ref(root / x, root) for x in stage.get("outputs", [])]
        rec["summary"] = summary if summary is not None else summarize(stage, root)
    except Exception as exc:
        rec.setdefault("warnings", []).append(f"manifest observation unavailable: {exc}")
    summary = rec.get("summary", {})
    if summary.get("fallback") or summary.get("unavailable_capabilities"):
        degradation = manifest.setdefault("degradation", {"occurred": False, "reasons": []})
        degradation["occurred"] = True
        if summary.get("fallback"): degradation["reasons"].append("report_fallback")
        if summary.get("unavailable_capabilities"): degradation["reasons"].append("capability_unavailable")
    if started is not None: rec["duration_ms"] = round((time.perf_counter() - started) * 1000, 2)
    if error: rec.setdefault("errors", []).append(error)
    if status in {"FAILED", "BLOCKED"}: manifest["pipeline_status"] = "FAILED"
    safe_write(path, manifest)
