"""Semantic mapping between source Excel columns and standard business fields."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FieldSpec:
    source: str
    type: str
    description: str


FIELD_MAP: dict[str, FieldSpec] = {
    "stat_date": FieldSpec("统计日期", "date", "指标归属的统计日期"),
    "category": FieldSpec("所属品类", "dimension", "产品所属业务品类"),
    "channel": FieldSpec("三级渠道", "dimension", "三级渠道标准名称"),
    "leads": FieldSpec("线索数", "count", "渠道获得的线索数量"),
    "first_order_orders": FieldSpec("首单订单数", "count", "首单订单数量"),
    "cost": FieldSpec("获客总成本", "money", "渠道获客投入成本"),
    "first_order_revenue": FieldSpec("首单营收", "money", "首单确认营收"),
    "first_order_formal_revenue": FieldSpec(
        "首单正式营流水", "money", "首单正式营收入流水"
    ),
    "first_order_net_revenue": FieldSpec("首单净流水", "money", "首单净收入流水"),
    "first_order_refund_revenue": FieldSpec(
        "首单正式营退款流水", "money", "首单正式营退款流水"
    ),
    "repeat_leads": FieldSpec("本品重复线索数", "count", "本品重复线索数量"),
    "repeat_leads_90d": FieldSpec(
        "本品重复线索数(90天内)", "count", "90天内本品重复线索数量"
    ),
}

ADDITIVE_FIELDS = (
    "leads",
    "first_order_orders",
    "cost",
    "first_order_revenue",
    "first_order_formal_revenue",
    "first_order_net_revenue",
    "first_order_refund_revenue",
    "repeat_leads",
    "repeat_leads_90d",
)


def source_columns() -> list[str]:
    return [spec.source for spec in FIELD_MAP.values()]


def source_to_standard() -> dict[str, str]:
    return {spec.source: standard for standard, spec in FIELD_MAP.items()}


def source_dtype() -> dict[str, str]:
    return {
        spec.source: "string"
        for spec in FIELD_MAP.values()
        if spec.type == "dimension"
    }


def validate_source_columns(columns: list[str]) -> None:
    missing = [spec.source for spec in FIELD_MAP.values() if spec.source not in columns]
    if missing:
        raise ValueError(f"Excel缺少字段映射要求的列: {', '.join(missing)}")
