from __future__ import annotations

import calendar

import pandas as pd


def safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    return numerator.div(denominator.where(denominator.ne(0)))


def month_coverage(raw: pd.DataFrame) -> pd.DataFrame:
    coverage = raw.groupby("month")["stat_date"].agg(["min", "max"]).reset_index()
    coverage["is_complete_month"] = coverage.apply(
        lambda row: row["min"].day == 1
        and row["max"].day == calendar.monthrange(row["max"].year, row["max"].month)[1],
        axis=1,
    )
    return coverage[["month", "is_complete_month"]]
