"""Build current S1-S4 metric tables from the real Interest Island sample."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.field_mapping import (
    ADDITIVE_FIELDS,
    source_columns,
    source_dtype,
    source_to_standard,
    validate_source_columns,
)
from src.metrics import build_category_metrics, build_channel_metrics


def load_source(input_path: Path, sheet_name: str = "数据源") -> pd.DataFrame:
    raw = pd.read_excel(
        input_path,
        sheet_name=sheet_name,
        usecols=lambda column: column in set(source_columns()),
        dtype=source_dtype(),
    )
    validate_source_columns(raw.columns.tolist())
    raw = raw.rename(columns=source_to_standard())

    raw["stat_date"] = pd.to_datetime(raw["stat_date"], errors="raise")
    raw["channel"] = raw["channel"].str.strip()
    raw["category"] = raw["category"].str.strip()
    if raw["channel"].isna().any() or raw["channel"].eq("").any():
        raise ValueError("三级渠道存在空值，无法形成稳定的 month + channel 主键")
    if raw["category"].isna().any() or raw["category"].eq("").any():
        raise ValueError("所属品类存在空值，无法形成稳定的 month + category 主键")

    raw["month"] = raw["stat_date"].dt.to_period("M").astype(str)
    for column in ADDITIVE_FIELDS:
        raw[column] = pd.to_numeric(raw[column], errors="raise")
    return raw


def build_metrics(input_path: Path) -> pd.DataFrame:
    """Backward-compatible channel metrics entrypoint."""
    return build_channel_metrics(load_source(input_path))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--category-output", type=Path)
    parser.add_argument("--sheet-name", default="数据源")
    args = parser.parse_args()

    raw = load_source(args.input, args.sheet_name)
    metrics = build_channel_metrics(raw)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(args.output, index=False, encoding="utf-8-sig", float_format="%.8f")
    print(f"generated {len(metrics)} rows -> {args.output}")
    if args.category_output:
        category_metrics = build_category_metrics(raw)
        args.category_output.parent.mkdir(parents=True, exist_ok=True)
        category_metrics.to_csv(
            args.category_output,
            index=False,
            encoding="utf-8-sig",
            float_format="%.8f",
        )
        print(f"generated {len(category_metrics)} rows -> {args.category_output}")


if __name__ == "__main__":
    main()
