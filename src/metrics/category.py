from __future__ import annotations

import pandas as pd

from src.metrics.common import month_coverage, safe_divide


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
