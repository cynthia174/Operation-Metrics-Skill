from __future__ import annotations

import pandas as pd

from src.field_mapping import ADDITIVE_FIELDS
from src.metrics.common import month_coverage, safe_divide


def build_channel_metrics(raw: pd.DataFrame) -> pd.DataFrame:
    grouped = raw.groupby(
        ["month", "channel"], as_index=False, sort=True
    )[list(ADDITIVE_FIELDS)].sum()
    grouped = grouped.merge(month_coverage(raw), on="month")

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

    return grouped[
        [
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
    ]
