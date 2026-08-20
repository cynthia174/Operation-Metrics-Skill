"""Execute current S1-S4 rules supported by the real sample fields."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import pandas as pd


RESULT_COLUMNS = [
    "module",
    "rule_id",
    "month",
    "dimension_type",
    "dimension_value",
    "hit",
    "actual",
    "threshold",
    "reason",
]


def evaluate_channel_rules(metrics: pd.DataFrame) -> list[dict]:
    results: list[dict] = []
    complete = metrics.loc[metrics["is_complete_month"]].copy()
    complete = complete.sort_values(["channel", "month"])

    complete["month_ordinal"] = pd.PeriodIndex(complete["month"], freq="M").astype(int)
    complete["prev_cac_rate"] = complete.groupby("channel")["cac_rate"].shift(1)
    complete["prev2_cac_rate"] = complete.groupby("channel")["cac_rate"].shift(2)
    complete["prev_month_ordinal"] = complete.groupby("channel")["month_ordinal"].shift(1)
    complete["prev2_month_ordinal"] = complete.groupby("channel")["month_ordinal"].shift(2)

    for row in complete.itertuples(index=False):
        has_three_consecutive_months = (
            pd.notna(row.cac_rate)
            and pd.notna(row.prev_cac_rate)
            and pd.notna(row.prev2_cac_rate)
            and row.month_ordinal - row.prev_month_ordinal == 1
            and row.prev_month_ordinal - row.prev2_month_ordinal == 1
        )
        if has_three_consecutive_months:
            hit = row.cac_rate > row.prev_cac_rate > row.prev2_cac_rate
            results.append(
                {
                    "module": "S2",
                    "rule_id": "R36",
                    "month": row.month,
                    "dimension_type": "三级渠道",
                    "dimension_value": row.channel,
                    "hit": bool(hit),
                    "actual": row.cac_rate,
                    "threshold": "连续3个完整月上升",
                    "reason": f"{row.prev2_cac_rate:.6f} -> {row.prev_cac_rate:.6f} -> {row.cac_rate:.6f}",
                }
            )
        has_previous_month = (
            pd.notna(row.cac_rate)
            and pd.notna(row.prev_cac_rate)
            and row.month_ordinal - row.prev_month_ordinal == 1
        )
        if has_previous_month:
            change = row.cac_rate - row.prev_cac_rate
            results.append(
                {
                    "module": "S2",
                    "rule_id": "R37",
                    "month": row.month,
                    "dimension_type": "三级渠道",
                    "dimension_value": row.channel,
                    "hit": bool(change > 0.05),
                    "actual": change,
                    "threshold": "> 0.05（5个百分点）",
                    "reason": f"本月CAC率 {row.cac_rate:.6f} - 上月 {row.prev_cac_rate:.6f}",
                }
            )
    return results


def _consecutive_months(frame: pd.DataFrame, count: int) -> bool:
    ordinals = frame["month_ordinal"].tolist()
    return len(ordinals) == count and all(
        later - earlier == 1 for earlier, later in zip(ordinals, ordinals[1:])
    )


def evaluate_category_rules(metrics: pd.DataFrame) -> list[dict]:
    results: list[dict] = []
    complete = metrics.loc[metrics["is_complete_month"]].copy()
    complete = complete.sort_values(["category", "month"])
    complete["month_ordinal"] = pd.PeriodIndex(complete["month"], freq="M").astype(int)

    for month, group in complete.groupby("month", sort=True):
        ranked = group.sort_values("category_revenue", ascending=False)
        total = ranked["category_revenue"].sum()
        top1_share = ranked["category_revenue"].iloc[0] / total if total else float("nan")
        top3_share = ranked["category_revenue"].head(3).sum() / total if total else float("nan")
        results.extend(
            [
                {
                    "module": "S1",
                    "rule_id": "R3",
                    "month": month,
                    "dimension_type": "全品类",
                    "dimension_value": "__ALL__",
                    "hit": bool(pd.notna(top1_share) and top1_share > 0.50),
                    "actual": top1_share,
                    "threshold": "> 0.50",
                    "reason": "品类首单营收Top1 / 全品类首单营收",
                },
                {
                    "module": "S1",
                    "rule_id": "R4",
                    "month": month,
                    "dimension_type": "全品类",
                    "dimension_value": "__ALL__",
                    "hit": bool(pd.notna(top3_share) and top3_share < 0.50),
                    "actual": top3_share,
                    "threshold": "< 0.50",
                    "reason": "品类首单营收Top3 / 全品类首单营收",
                },
            ]
        )

    growth_rows: list[dict] = []
    declining_by_month: dict[str, int] = {}
    r5_eligible_months: set[str] = set()
    for category, group in complete.groupby("category", sort=True):
        group = group.sort_values("month")
        previous_revenue = group["category_revenue"].shift(1)
        group["growth"] = (group["category_revenue"] - previous_revenue).div(
            previous_revenue.where(previous_revenue.ne(0))
        )
        rows = list(group.itertuples(index=False))
        for index, row in enumerate(rows):
            if index >= 1 and row.month_ordinal - rows[index - 1].month_ordinal == 1:
                growth_rows.append(
                    {"month": row.month, "category": category, "growth": row.growth}
                )
            if index >= 2:
                window = group.iloc[index - 2 : index + 1]
                if _consecutive_months(window, 3):
                    r5_eligible_months.add(row.month)
                    values = window["category_revenue"].tolist()
                    declining = values[2] < values[1] < values[0]
                    results.append(
                        {
                            "module": "S1",
                            "rule_id": "R5",
                            "month": row.month,
                            "dimension_type": "所属品类",
                            "dimension_value": category,
                            "hit": bool(declining),
                            "actual": row.category_revenue,
                            "threshold": "连续3个完整月下降",
                            "reason": " -> ".join(f"{value:.2f}" for value in values),
                        }
                    )
                    if declining:
                        declining_by_month[row.month] = declining_by_month.get(row.month, 0) + 1
        for index in range(5, len(group)):
            window = group.iloc[index - 5 : index + 1]
            if not _consecutive_months(window, 6):
                continue
            changes = window["category_revenue"].diff().dropna()
            directions = changes.apply(lambda value: 1 if value > 0 else -1 if value < 0 else 0)
            flips = sum(
                left != 0 and right != 0 and left != right
                for left, right in zip(directions, directions.iloc[1:])
            )
            results.append(
                {
                    "module": "S1",
                    "rule_id": "R6",
                    "month": window.iloc[-1]["month"],
                    "dimension_type": "所属品类",
                    "dimension_value": category,
                    "hit": bool(flips >= 3),
                    "actual": flips,
                    "threshold": ">= 3次方向切换/6个完整月",
                    "reason": "6个月营收环比方向切换次数",
                }
            )

    growth = pd.DataFrame(growth_rows)
    for month, group in growth.groupby("month", sort=True):
        max_growth = group["growth"].max()
        min_growth = group["growth"].min()
        hit = (
            pd.notna(max_growth)
            and pd.notna(min_growth)
            and math.isfinite(max_growth)
            and math.isfinite(min_growth)
            and max_growth > 0.30
            and min_growth < -0.30
        )
        results.append(
            {
                "module": "S1",
                "rule_id": "R8",
                "month": month,
                "dimension_type": "全品类",
                "dimension_value": "__ALL__",
                "hit": bool(hit),
                "actual": max_growth - min_growth,
                "threshold": "同时存在环比>30%与<-30%",
                "reason": f"最大环比 {max_growth:.6f}；最小环比 {min_growth:.6f}",
            }
        )
    for month in sorted(r5_eligible_months):
        count = declining_by_month.get(month, 0)
        results.append(
            {
                "module": "S1",
                "rule_id": "R9",
                "month": month,
                "dimension_type": "全品类",
                "dimension_value": "__ALL__",
                "hit": bool(count > 3),
                "actual": count,
                "threshold": "> 3个品类连续3个完整月下降",
                "reason": "满足R5下降条件的品类数",
            }
        )
    return results


def evaluate_month_rules(metrics: pd.DataFrame) -> list[dict]:
    results: list[dict] = []
    for month, group in metrics.loc[metrics["is_complete_month"]].groupby("month"):
        total_cost = group["cost"].sum()
        ineffective_cost = group.loc[group["channel_roi"] < 0.5, "cost"].sum()
        share = ineffective_cost / total_cost if total_cost != 0 else float("nan")
        results.append(
            {
                "module": "S3",
                "rule_id": "R61",
                "month": month,
                "dimension_type": "全渠道",
                "dimension_value": "__ALL__",
                "hit": bool(pd.notna(share) and share > 0.20),
                "actual": share,
                "threshold": "> 0.20",
                "reason": "ROI<0.5渠道成本 / 全渠道成本",
            }
        )
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("metrics", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--category-metrics", type=Path)
    args = parser.parse_args()

    metrics = pd.read_csv(args.metrics, dtype={"month": "string", "channel": "string"})
    results = evaluate_channel_rules(metrics) + evaluate_month_rules(metrics)
    if args.category_metrics:
        category_metrics = pd.read_csv(
            args.category_metrics, dtype={"month": "string", "category": "string"}
        )
        results = evaluate_category_rules(category_metrics) + results
    output = pd.DataFrame(results, columns=RESULT_COLUMNS)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(args.output, index=False, encoding="utf-8-sig", float_format="%.8f")
    print(f"evaluated {len(output)} rule rows; hits={int(output['hit'].sum())} -> {args.output}")


if __name__ == "__main__":
    main()
