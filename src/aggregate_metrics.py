"""Build current S1-S4 metric tables from the real Interest Island sample."""

from __future__ import annotations

import argparse
import calendar
from pathlib import Path

import pandas as pd


SOURCE_COLUMNS = {
    "统计日期": "stat_date",
    "所属品类": "category",
    "三级渠道": "channel",
    "线索数": "leads",
    "首单订单数": "first_order_orders",
    "获客总成本": "cost",
    "首单营收": "first_order_revenue",
    "首单正式营流水": "first_order_formal_revenue",
    "首单净流水": "first_order_net_revenue",
    "首单正式营退款流水": "first_order_refund_revenue",
    "本品重复线索数": "repeat_leads",
    "本品重复线索数(90天内)": "repeat_leads_90d",
}

ADDITIVE_COLUMNS = [
    "leads",
    "first_order_orders",
    "cost",
    "first_order_revenue",
    "first_order_formal_revenue",
    "first_order_net_revenue",
    "first_order_refund_revenue",
    "repeat_leads",
    "repeat_leads_90d",
]


def safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    return numerator.div(denominator.where(denominator.ne(0)))


def load_source(input_path: Path) -> pd.DataFrame:
    raw = pd.read_excel(
        input_path,
        sheet_name="数据源",
        usecols=list(SOURCE_COLUMNS),
        dtype={"三级渠道": "string", "所属品类": "string"},
    ).rename(columns=SOURCE_COLUMNS)

    raw["stat_date"] = pd.to_datetime(raw["stat_date"], errors="raise")
    raw["channel"] = raw["channel"].str.strip()
    raw["category"] = raw["category"].str.strip()
    if raw["channel"].isna().any() or raw["channel"].eq("").any():
        raise ValueError("三级渠道存在空值，无法形成稳定的 month + channel 主键")
    if raw["category"].isna().any() or raw["category"].eq("").any():
        raise ValueError("所属品类存在空值，无法形成稳定的 month + category 主键")

    raw["month"] = raw["stat_date"].dt.to_period("M").astype(str)
    for column in ADDITIVE_COLUMNS:
        raw[column] = pd.to_numeric(raw[column], errors="raise")
    return raw


def month_coverage(raw: pd.DataFrame) -> pd.DataFrame:
    coverage = raw.groupby("month")["stat_date"].agg(["min", "max"]).reset_index()
    coverage["is_complete_month"] = coverage.apply(
        lambda row: row["min"].day == 1
        and row["max"].day == calendar.monthrange(row["max"].year, row["max"].month)[1],
        axis=1,
    )
    return coverage[["month", "is_complete_month"]]


def build_channel_metrics(raw: pd.DataFrame) -> pd.DataFrame:

    grouped = (
        raw.groupby(["month", "channel"], as_index=False, sort=True)[ADDITIVE_COLUMNS]
        .sum()
    )

    grouped = grouped.merge(month_coverage(raw), on="month")

    # The sample has orders, not distinct buyers. Keep the proxy explicit.
    grouped["first_order_users_proxy"] = grouped["first_order_orders"]
    grouped["cac"] = safe_divide(grouped["cost"], grouped["first_order_users_proxy"])
    grouped["cac_rate"] = safe_divide(grouped["cost"], grouped["first_order_net_revenue"])
    grouped["first_order_conversion_rate"] = safe_divide(
        grouped["first_order_orders"], grouped["leads"]
    )
    grouped["channel_roi"] = safe_divide(grouped["first_order_revenue"], grouped["cost"])
    grouped["repeat_lead_rate"] = safe_divide(grouped["repeat_leads"], grouped["leads"])
    grouped["repeat_lead_rate_90d"] = safe_divide(
        grouped["repeat_leads_90d"], grouped["leads"]
    )

    ordered = [
        "month",
        "channel",
        "is_complete_month",
        "cost",
        "leads",
        "first_order_orders",
        "first_order_users_proxy",
        "first_order_revenue",
        "first_order_formal_revenue",
        "first_order_net_revenue",
        "first_order_refund_revenue",
        "repeat_leads",
        "repeat_leads_90d",
        "cac",
        "cac_rate",
        "first_order_conversion_rate",
        "channel_roi",
        "repeat_lead_rate",
        "repeat_lead_rate_90d",
    ]
    return grouped[ordered]


def build_category_metrics(raw: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        raw.groupby(["month", "category"], as_index=False, sort=True)[
            ["first_order_revenue"]
        ]
        .sum()
        .rename(columns={"first_order_revenue": "category_revenue"})
    )
    grouped = grouped.merge(month_coverage(raw), on="month")
    totals = grouped.groupby("month")["category_revenue"].transform("sum")
    grouped["revenue_share"] = safe_divide(grouped["category_revenue"], totals)
    return grouped[
        ["month", "category", "is_complete_month", "category_revenue", "revenue_share"]
    ]


def build_metrics(input_path: Path) -> pd.DataFrame:
    """Backward-compatible channel metrics entrypoint."""
    return build_channel_metrics(load_source(input_path))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--category-output", type=Path)
    args = parser.parse_args()

    raw = load_source(args.input)
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
