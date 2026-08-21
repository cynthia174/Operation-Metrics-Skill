from __future__ import annotations

import math
import pandas as pd

from src.rule_result import Dimension, Period, RuleResult


def _consecutive_months(frame: pd.DataFrame, count: int) -> bool:
    ordinals = frame["month_ordinal"].tolist()
    return len(ordinals) == count and all(
        later - earlier == 1 for earlier, later in zip(ordinals, ordinals[1:])
    )


def evaluate_category_rules(metrics: pd.DataFrame) -> list[RuleResult]:
    results: list[RuleResult] = []
    complete = metrics.loc[metrics["is_complete_month"]].copy()
    complete = complete.sort_values(["category", "month"])
    complete["month_ordinal"] = pd.PeriodIndex(complete["month"], freq="M").astype(int)

    for month, group in complete.groupby("month", sort=True):
        ranked = group.sort_values("category_revenue", ascending=False)
        total = float(ranked["category_revenue"].sum())
        if total == 0:
            continue
        top1_revenue = float(ranked["category_revenue"].iloc[0])
        top3_revenue = float(ranked["category_revenue"].head(3).sum())
        top1_share, top3_share = top1_revenue / total, top3_revenue / total
        results.extend([
            RuleResult("S1", "R3", "营收集中度", top1_share > 0.50,
                Dimension("all_categories", "__ALL__"), Period(str(month), str(month)),
                {"top1_revenue": top1_revenue, "total_revenue": total, "top1_share": top1_share},
                "Top1品类首单营收占比 > 0.50",
                [f"Top1品类 {ranked.iloc[0]['category']}", f"Top1营收 {top1_revenue:.2f}", f"全品类营收 {total:.2f}", f"Top1占比 {top1_share:.6f}"]),
            RuleResult("S1", "R4", "营收过于分散", top3_share < 0.50,
                Dimension("all_categories", "__ALL__"), Period(str(month), str(month)),
                {"top3_revenue": top3_revenue, "total_revenue": total, "top3_share": top3_share},
                "Top3品类首单营收占比 < 0.50",
                [f"Top3营收 {top3_revenue:.2f}", f"全品类营收 {total:.2f}", f"Top3占比 {top3_share:.6f}"])
        ])

    growth_rows: list[dict] = []
    declining_by_month: dict[str, int] = {}
    eligible_starts: dict[str, str] = {}
    for category, group in complete.groupby("category", sort=True):
        group = group.sort_values("month").copy()
        previous = group["category_revenue"].shift(1)
        group["growth"] = (group["category_revenue"] - previous).div(previous.where(previous.ne(0)))
        rows = list(group.itertuples(index=False))
        for index, row in enumerate(rows):
            if index >= 1 and row.month_ordinal - rows[index - 1].month_ordinal == 1:
                growth_rows.append({"month": row.month, "category": category, "growth": row.growth})
            if index >= 2:
                window = group.iloc[index - 2:index + 1]
                if _consecutive_months(window, 3):
                    eligible_starts[str(row.month)] = str(window.iloc[0]["month"])
                    values = [float(value) for value in window["category_revenue"]]
                    declining = values[2] < values[1] < values[0]
                    results.append(RuleResult(
                        "S1", "R5", "核心品类下行趋势", declining,
                        Dimension("category", str(category)), Period(str(window.iloc[0]["month"]), str(row.month)),
                        {"start_revenue": values[0], "previous_revenue": values[1], "current_revenue": values[2]},
                        "连续3个完整月下降",
                        [f"{month_value} 首单营收 {value:.2f}" for month_value, value in zip(window["month"], values)]))
                    if declining:
                        declining_by_month[str(row.month)] = declining_by_month.get(str(row.month), 0) + 1
        for index in range(5, len(group)):
            window = group.iloc[index - 5:index + 1]
            if not _consecutive_months(window, 6):
                continue
            directions = window["category_revenue"].diff().dropna().apply(
                lambda value: 1 if value > 0 else -1 if value < 0 else 0)
            flips = sum(left != 0 and right != 0 and left != right
                        for left, right in zip(directions, directions.iloc[1:]))
            results.append(RuleResult(
                "S1", "R6", "增长一致性", flips >= 3,
                Dimension("category", str(category)), Period(str(window.iloc[0]["month"]), str(window.iloc[-1]["month"])),
                {"direction_change_count": int(flips)}, ">= 3次方向切换/6个完整月",
                [f"6个月营收环比方向切换 {flips} 次"]))

    growth = pd.DataFrame(growth_rows)
    for month, group in growth.groupby("month", sort=True):
        finite = group.loc[group["growth"].map(lambda value: pd.notna(value) and math.isfinite(value))]
        if finite.empty:
            continue
        max_row, min_row = finite.loc[finite["growth"].idxmax()], finite.loc[finite["growth"].idxmin()]
        max_growth, min_growth = float(max_row["growth"]), float(min_row["growth"])
        results.append(RuleResult(
            "S1", "R8", "涨跌两极分化", max_growth > 0.30 and min_growth < -0.30,
            Dimension("all_categories", "__ALL__"), Period(str(pd.Period(month, freq="M") - 1), str(month)),
            {"max_growth_rate": max_growth, "min_growth_rate": min_growth, "growth_spread": max_growth - min_growth},
            "同时存在环比 >30% 与 <-30%",
            [f"最大环比品类 {max_row['category']}，增速 {max_growth:.6f}", f"最小环比品类 {min_row['category']}，增速 {min_growth:.6f}"]))
    for month, start in sorted(eligible_starts.items()):
        count = declining_by_month.get(month, 0)
        results.append(RuleResult(
            "S1", "R9", "系统性下跌", count > 3,
            Dimension("all_categories", "__ALL__"), Period(start, month),
            {"declining_category_count": count}, "> 3个品类连续3个完整月下降",
            [f"满足R5连续下降条件的品类数 {count}"]))
    return results
