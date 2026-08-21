"""Rule Engine CLI: metric CSV files to stable CSV and JSON results."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.rule_result import write_results
from src.rules import evaluate_category_rules, evaluate_channel_rules, evaluate_month_rules


def run_rules(channel_metrics_path: Path, category_metrics_path: Path):
    channel_metrics = pd.read_csv(
        channel_metrics_path, dtype={"month": "string", "channel": "string"}
    )
    category_metrics = pd.read_csv(
        category_metrics_path, dtype={"month": "string", "category": "string"}
    )
    return (
        evaluate_category_rules(category_metrics)
        + evaluate_channel_rules(channel_metrics)
        + evaluate_month_rules(channel_metrics)
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("channel_metrics", type=Path)
    parser.add_argument("output_csv", type=Path)
    parser.add_argument("--category-metrics", type=Path, required=True)
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()

    json_path = args.json_output or args.output_csv.with_suffix(".json")
    results = run_rules(args.channel_metrics, args.category_metrics)
    write_results(results, args.output_csv, json_path)
    print(
        f"evaluated {len(results)} rule rows; hits={sum(result.hit for result in results)} "
        f"-> {args.output_csv}, {json_path}"
    )


if __name__ == "__main__":
    main()
