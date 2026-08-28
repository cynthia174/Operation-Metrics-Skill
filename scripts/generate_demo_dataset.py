"""Create the stable, non-sensitive golden-path workbook used by demo/README.md."""
from pathlib import Path
from datetime import date
import calendar
from openpyxl import Workbook

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "demo" / "demo_business_data.xlsx"
HEADERS = [
    "统计日期", "所属品类", "三级渠道", "线索数", "首单订单数", "获客总成本",
    "首单营收", "首单正式营流水", "首单净流水", "首单正式营退款流水",
    "本品重复线索数", "本品重复线索数(90天内)",
]

def main():
    months = [(2025, m) for m in range(1, 7)]
    categories = {"基础版": [600, 550, 500, 470, 440, 410],
                  "专业版": [180, 220, 270, 300, 330, 360],
                  "增值服务": [120, 105, 90, 75, 65, 55],
                  "培训服务": [100, 95, 90, 85, 80, 75]}
    channels = {"搜索广告": (1.00, [80, 90, 100, 110, 120, 130]),
                "内容投放": (0.90, [70, 70, 75, 75, 80, 80]),
                "展示广告": (0.75, [300, 300, 300, 300, 300, 300])}
    wb = Workbook(); ws = wb.active; ws.title = "数据源"; ws.append(HEADERS)
    for mi, (year, month) in enumerate(months):
        days = calendar.monthrange(year, month)[1]
        for category, revenues in categories.items():
            for channel, (share, costs) in channels.items():
                revenue = round(revenues[mi] * share / 2, 2)
                orders = max(1, round(revenue / 10))
                cost = round(costs[mi] / 2, 2)
                for day in (1, days):
                    ws.append([date(year, month, day), category, channel,
                           orders * 2, max(1, orders // 2), cost / 2, revenue / 2,
                           revenue / 2, revenue / 2, 0,
                           max(0, orders // 5), max(0, orders // 8)])
    OUT.parent.mkdir(parents=True, exist_ok=True); wb.save(OUT)
    print(OUT)

if __name__ == "__main__":
    main()
