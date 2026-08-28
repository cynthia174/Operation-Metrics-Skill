"""Generic capability detection and evidence-bounded fact extraction."""
from __future__ import annotations
import hashlib, json
from pathlib import Path
from typing import Any
import pandas as pd

CAPABILITIES = {
    "channel_revenue_summary": {"dimension": "channel", "metrics": ["first_order_revenue"]},
    "channel_revenue_rank": {"dimension": "channel", "metrics": ["first_order_revenue"]},
    "channel_cost_summary": {"dimension": "channel", "metrics": ["cost"]},
    "channel_cac": {"dimension": "channel", "metrics": ["cost", "first_order_orders"]},
    "channel_cac_rate": {"dimension": "channel", "metrics": ["cost", "first_order_net_revenue"]},
    "channel_roi": {"dimension": "channel", "metrics": ["cost", "first_order_revenue"]},
    "category_revenue_summary": {"dimension": "category", "metrics": ["category_revenue"]},
    "category_revenue_rank": {"dimension": "category", "metrics": ["category_revenue"]},
    "category_revenue_share": {"dimension": "category", "metrics": ["category_revenue", "revenue_share"]},
    "period_over_period_change": {"dimension": "time", "metrics": [], "time_condition": "at_least_two_complete_periods"},
    "continuous_trend": {"dimension": "time", "metrics": [], "time_condition": "at_least_three_complete_periods"},
}

def _available(df: pd.DataFrame, required: list[str]) -> bool:
    return bool(len(df)) and all(x in df.columns and df[x].notna().any() for x in required)

def detect_capabilities(channel: pd.DataFrame, category: pd.DataFrame) -> list[dict[str, Any]]:
    frames = {"channel": channel, "category": category}
    complete = pd.concat([x.loc[x.get("is_complete_month", pd.Series(dtype=bool)).fillna(False)] for x in frames.values() if len(x)], ignore_index=True)
    complete_periods = complete["month"].nunique() if "month" in complete else 0
    out = []
    for cid, spec in CAPABILITIES.items():
        frame = frames.get(spec["dimension"])
        if spec["dimension"] == "time":
            frame = complete
        ok = frame is not None and (True if spec["dimension"] == "time" else _available(frame, spec["metrics"]))
        reason = None if ok else (f"missing or empty metrics: {', '.join(spec['metrics'])}" if spec["dimension"] != "time" else "no usable time periods")
        if ok and spec.get("time_condition") == "at_least_two_complete_periods" and complete_periods < 2:
            ok, reason = False, "requires at least two complete periods"
        if ok and spec.get("time_condition") == "at_least_three_complete_periods" and complete_periods < 3:
            ok, reason = False, "requires at least three complete periods"
        out.append({"capability_id": cid, "required_dimensions":[spec["dimension"]], "required_metrics":spec["metrics"], "required_time_condition":spec.get("time_condition"), "status":"AVAILABLE" if ok else "UNAVAILABLE", "unavailable_reason":reason})
    return out

def build_facts(channel: pd.DataFrame, category: pd.DataFrame, capabilities: list[dict[str, Any]], source_paths: dict[str, str]) -> list[dict[str, Any]]:
    enabled = {x["capability_id"] for x in capabilities if x["status"] == "AVAILABLE"}
    facts = []
    for cid in enabled:
        spec = CAPABILITIES[cid]; frame = channel if spec["dimension"] == "channel" else category
        metric = "category_revenue" if spec["dimension"] == "category" else ("first_order_revenue" if "revenue" in cid or cid.endswith("roi") else "cost")
        if metric not in frame.columns: continue
        latest = frame.sort_values("month").groupby(spec["dimension"], as_index=False).tail(1)
        if cid.endswith("rank"):
            latest = latest.sort_values(metric, ascending=False).reset_index(drop=True)
        for rank, row in latest.iterrows():
            value = row.get(metric)
            if pd.isna(value): continue
            facts.append({"fact_id": hashlib.sha1(f"{cid}|{row[spec['dimension']]}|{row['month']}|{metric}".encode()).hexdigest()[:16], "capability_id":cid, "dimension":spec["dimension"], "entity":str(row[spec["dimension"]]), "metric":metric, "value":float(value), "period":str(row["month"]), "status":"AVAILABLE", "evidence":{"source":source_paths[spec["dimension"]], "rows":[int(row.name)+2]}})
    return facts

def write_capability_facts(channel_path: Path, category_path: Path, output: Path, capabilities_path: Path) -> None:
    channel, category = pd.read_csv(channel_path), pd.read_csv(category_path)
    caps = detect_capabilities(channel, category); facts = build_facts(channel, category, caps, {"channel":str(channel_path), "category":str(category_path)})
    capabilities_path.write_text(json.dumps({"capabilities":caps}, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    output.write_text(json.dumps({"schema_version":"1.0", "facts":facts}, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
