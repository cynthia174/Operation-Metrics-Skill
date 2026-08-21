from __future__ import annotations

import pandas as pd

from src.rule_result import Dimension, Period, RuleResult


def evaluate_channel_rules(metrics: pd.DataFrame) -> list[RuleResult]:
    results: list[RuleResult] = []
    complete = metrics.loc[metrics["is_complete_month"]].copy()
    complete = complete.sort_values(["channel", "month"])
    complete["month_ordinal"] = pd.PeriodIndex(complete["month"], freq="M").astype(int)
    for lag in (1, 2):
        complete[f"prev{lag}_cac_rate"] = complete.groupby("channel")["cac_rate"].shift(lag)
        complete[f"prev{lag}_month"] = complete.groupby("channel")["month"].shift(lag)
        complete[f"prev{lag}_ordinal"] = complete.groupby("channel")["month_ordinal"].shift(lag)

    for row in complete.itertuples(index=False):
        has_previous = (
            pd.notna(row.cac_rate)
            and pd.notna(row.prev1_cac_rate)
            and row.month_ordinal - row.prev1_ordinal == 1
        )
        if has_previous:
            change = row.cac_rate - row.prev1_cac_rate
            results.append(
                RuleResult(
                    module="S2",
                    rule_id="R37",
                    rule_name="CAC环比跳升",
                    hit=bool(change > 0.05),
                    dimension=Dimension("channel", str(row.channel)),
                    period=Period(str(row.prev1_month), str(row.month)),
                    metrics={
                        "current_cac_rate": float(row.cac_rate),
                        "previous_cac_rate": float(row.prev1_cac_rate),
                        "change_percentage_points": float(change),
                    },
                    threshold="> 0.05（5个百分点）",
                    evidence=[
                        f"{row.prev1_month} CAC率 {row.prev1_cac_rate:.6f}",
                        f"{row.month} CAC率 {row.cac_rate:.6f}",
                        f"环比变化 {change:.6f}",
                    ],
                )
            )
        has_three = (
            has_previous
            and pd.notna(row.prev2_cac_rate)
            and row.prev1_ordinal - row.prev2_ordinal == 1
        )
        if has_three:
            values = [row.prev2_cac_rate, row.prev1_cac_rate, row.cac_rate]
            results.append(
                RuleResult(
                    module="S2",
                    rule_id="R36",
                    rule_name="CAC连续上升",
                    hit=bool(values[2] > values[1] > values[0]),
                    dimension=Dimension("channel", str(row.channel)),
                    period=Period(str(row.prev2_month), str(row.month)),
                    metrics={
                        "start_cac_rate": float(values[0]),
                        "previous_cac_rate": float(values[1]),
                        "current_cac_rate": float(values[2]),
                    },
                    threshold="连续3个完整月上升",
                    evidence=[
                        f"{row.prev2_month} CAC率 {values[0]:.6f}",
                        f"{row.prev1_month} CAC率 {values[1]:.6f}",
                        f"{row.month} CAC率 {values[2]:.6f}",
                    ],
                )
            )
    return results


def evaluate_month_rules(metrics: pd.DataFrame) -> list[RuleResult]:
    results: list[RuleResult] = []
    for month, group in metrics.loc[metrics["is_complete_month"]].groupby("month"):
        total_cost = float(group["cost"].sum())
        ineffective_cost = float(group.loc[group["channel_roi"] < 0.5, "cost"].sum())
        if total_cost == 0:
            continue
        share = ineffective_cost / total_cost
        results.append(
            RuleResult(
                module="S3",
                rule_id="R61",
                rule_name="无效投放(P0)",
                hit=bool(share > 0.20),
                dimension=Dimension("all_channels", "__ALL__"),
                period=Period(str(month), str(month)),
                metrics={
                    "ineffective_cost": ineffective_cost,
                    "total_cost": total_cost,
                    "ineffective_cost_share": share,
                },
                threshold="ROI<0.5渠道消耗占比 > 0.20",
                evidence=[
                    f"ROI<0.5渠道成本 {ineffective_cost:.2f}",
                    f"全渠道成本 {total_cost:.2f}",
                    f"无效投放占比 {share:.6f}",
                ],
            )
        )
    return results
