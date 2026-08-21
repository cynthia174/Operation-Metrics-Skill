"""Format Rule Engine JSON into an LLM-ready, fact-preserving context."""

from __future__ import annotations

import argparse
import copy
import json
from collections import OrderedDict
from pathlib import Path
from typing import Any

MODULE_NAMES = {"S1": "产品结构", "S2": "客户结构", "S3": "渠道结构", "S4": "市场格局"}
DIMENSION_NAMES = {
    "category": "品类", "channel": "渠道",
    "all_categories": "全品类", "all_channels": "全渠道",
}
REQUIRED_RESULT_FIELDS = {
    "module", "rule_id", "rule_name", "hit", "dimension",
    "period", "metrics", "threshold", "evidence",
}


def load_rule_results(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    validate_input(payload)
    return payload


def validate_input(payload: dict[str, Any]) -> None:
    required_top = {"schema_version", "result_count", "hit_count", "results"}
    missing_top = required_top - payload.keys()
    if missing_top:
        raise ValueError(f"rule_results.json缺少顶层字段: {sorted(missing_top)}")
    if not isinstance(payload["results"], list):
        raise ValueError("results必须是数组")
    if payload["result_count"] != len(payload["results"]):
        raise ValueError("result_count与results记录数不一致")
    for index, result in enumerate(payload["results"]):
        missing = REQUIRED_RESULT_FIELDS - result.keys()
        if missing:
            raise ValueError(f"results[{index}]缺少字段: {sorted(missing)}")
        if set(result["dimension"]) != {"type", "name"}:
            raise ValueError(f"results[{index}].dimension结构不符合协议")
        if set(result["period"]) != {"start", "end"}:
            raise ValueError(f"results[{index}].period结构不符合协议")


def readable_rule_info(result: dict[str, Any]) -> dict[str, str]:
    module = result["module"]
    return {
        "id": result["rule_id"],
        "name": result["rule_name"],
        "display_name": f"{result['rule_id']}｜{result['rule_name']}",
        "module_id": module,
        "module_name": MODULE_NAMES.get(module, module),
    }


def _dimension_key(result: dict[str, Any]) -> tuple[str, str]:
    dimension = result["dimension"]
    return str(dimension["type"]), str(dimension["name"])


def _period_key(result: dict[str, Any]) -> tuple[str, str]:
    period = result["period"]
    return str(period["start"]), str(period["end"])


def format_rule_results(payload: dict[str, Any]) -> dict[str, Any]:
    """Group results for prompting while preserving each input result as ``fact``."""
    validate_input(payload)
    module_groups: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    for result in payload["results"]:
        module_groups.setdefault(result["module"], []).append(result)

    modules: list[dict[str, Any]] = []
    for module_id in sorted(module_groups):
        module_results = module_groups[module_id]
        dimension_groups: OrderedDict[tuple[str, str], list[dict[str, Any]]] = OrderedDict()
        for result in sorted(module_results, key=lambda item: (_dimension_key(item), _period_key(item), item["rule_id"])):
            dimension_groups.setdefault(_dimension_key(result), []).append(result)

        dimensions: list[dict[str, Any]] = []
        for (dimension_type, dimension_name), dimension_results in dimension_groups.items():
            period_groups: OrderedDict[tuple[str, str], list[dict[str, Any]]] = OrderedDict()
            for result in dimension_results:
                period_groups.setdefault(_period_key(result), []).append(result)
            periods = []
            for (start, end), period_results in period_groups.items():
                periods.append({
                    "start": start,
                    "end": end,
                    "result_count": len(period_results),
                    "hit_count": sum(bool(result["hit"]) for result in period_results),
                    "results": [
                        {"rule_info": readable_rule_info(result), "fact": copy.deepcopy(result)}
                        for result in period_results
                    ],
                })
            dimensions.append({
                "type": dimension_type,
                "type_name": DIMENSION_NAMES.get(dimension_type, dimension_type),
                "name": dimension_name,
                "result_count": len(dimension_results),
                "hit_count": sum(bool(result["hit"]) for result in dimension_results),
                "periods": periods,
            })
        modules.append({
            "id": module_id,
            "name": MODULE_NAMES.get(module_id, module_id),
            "result_count": len(module_results),
            "hit_count": sum(bool(result["hit"]) for result in module_results),
            "dimensions": dimensions,
        })

    rules = {(result["module"], result["rule_id"], result["rule_name"]) for result in payload["results"]}
    return {
        "context_version": "1.0",
        "source": {
            "schema_version": payload["schema_version"],
            "result_count": payload["result_count"],
            "hit_count": payload["hit_count"],
        },
        "usage": {
            "purpose": "供LLM基于Rule Engine事实生成经营分析报告",
            "instructions": [
                "仅使用fact中的原始事实，不重新计算metrics。",
                "优先解释hit=true的结果，同时可用hit=false说明已检查但未命中。",
                "引用结论时同时给出rule_info.display_name、dimension、period和evidence。",
                "不要把formatter的分组计数解释为新的业务指标。",
            ],
        },
        "rule_catalog": [
            {
                "module_id": module,
                "module_name": MODULE_NAMES.get(module, module),
                "rule_id": rule_id,
                "rule_name": rule_name,
                "display_name": f"{rule_id}｜{rule_name}",
            }
            for module, rule_id, rule_name in sorted(rules)
        ],
        "modules": modules,
    }


def extract_facts(context: dict[str, Any]) -> list[dict[str, Any]]:
    return [item["fact"] for module in context["modules"]
            for dimension in module["dimensions"] for period in dimension["periods"]
            for item in period["results"]]


def write_context(context: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            context,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    payload = load_rule_results(args.input)
    context = format_rule_results(payload)
    write_context(context, args.output)
    print(f"formatted {payload['result_count']} rule results into {len(context['modules'])} modules -> {args.output}")


if __name__ == "__main__":
    main()
