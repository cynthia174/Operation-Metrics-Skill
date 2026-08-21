"""Stable machine-readable output contract for rule evaluation."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class Dimension:
    type: str
    name: str


@dataclass(frozen=True)
class Period:
    start: str
    end: str


@dataclass(frozen=True)
class RuleResult:
    module: str
    rule_id: str
    rule_name: str
    hit: bool
    dimension: Dimension
    period: Period
    metrics: dict[str, int | float | str | bool | None]
    threshold: str
    evidence: list[str]

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        _assert_finite(value)
        return value

    def to_csv_row(self) -> dict[str, Any]:
        return {
            "module": self.module,
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "hit": self.hit,
            "dimension_type": self.dimension.type,
            "dimension_name": self.dimension.name,
            "period_start": self.period.start,
            "period_end": self.period.end,
            "metrics": json.dumps(self.metrics, ensure_ascii=False, sort_keys=True),
            "threshold": self.threshold,
            "evidence": json.dumps(self.evidence, ensure_ascii=False),
        }


def _assert_finite(value: Any, path: str = "result") -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{path}包含NaN或inf")
    if isinstance(value, dict):
        for key, child in value.items():
            _assert_finite(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_finite(child, f"{path}[{index}]")


def validate_results(results: list[RuleResult]) -> None:
    keys: set[tuple[str, str, str, str, str]] = set()
    for result in results:
        result.to_dict()
        key = (
            result.rule_id,
            result.dimension.type,
            result.dimension.name,
            result.period.start,
            result.period.end,
        )
        if key in keys:
            raise ValueError(f"重复rule结果: {key}")
        keys.add(key)


def write_results(
    results: list[RuleResult], csv_path: Path, json_path: Path
) -> None:
    validate_results(results)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([result.to_csv_row() for result in results]).to_csv(
        csv_path, index=False, encoding="utf-8-sig"
    )
    payload = {
        "schema_version": "1.0",
        "result_count": len(results),
        "hit_count": sum(result.hit for result in results),
        "results": [result.to_dict() for result in results],
    }
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
