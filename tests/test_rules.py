import unittest

import pandas as pd

from src.run_rules import evaluate_category_rules, evaluate_channel_rules, evaluate_month_rules


class RuleEvaluationTests(unittest.TestCase):
    def test_category_rules_use_consecutive_complete_months_and_safe_growth(self):
        rows = []
        values = {
            "A": [100, 80, 60, 70, 50, 60],
            "B": [0, 20, 40, 20, 30, 20],
            "C": [40, 60, 20, 50, 20, 50],
            "D": [30, 20, 10, 20, 10, 20],
        }
        months = pd.period_range("2025-01", periods=6, freq="M").astype(str)
        for category, revenues in values.items():
            for month, revenue in zip(months, revenues):
                rows.append(
                    {
                        "month": month,
                        "category": category,
                        "is_complete_month": True,
                        "category_revenue": revenue,
                        "revenue_share": 0.0,
                    }
                )
        results = pd.DataFrame(evaluate_category_rules(pd.DataFrame(rows)))
        self.assertTrue(results.query("rule_id == 'R5' and dimension_value == 'A' and month == '2025-03'").iloc[0].hit)
        self.assertEqual(set(results.query("rule_id == 'R9'").month), set(months[2:]))
        self.assertTrue(results.query("rule_id == 'R8' and month == '2025-03'").actual.map(lambda value: value != float("inf")).all())
        self.assertEqual(len(results.query("rule_id == 'R6'")), 4)

    def test_channel_rules(self):
        metrics = pd.DataFrame(
            {
                "month": ["2025-01", "2025-02", "2025-03"],
                "channel": ["X", "X", "X"],
                "is_complete_month": [True, True, True],
                "cac_rate": [0.10, 0.12, 0.20],
                "cost": [100, 100, 100],
                "channel_roi": [0.4, 0.6, 0.6],
            }
        )
        results = pd.DataFrame(evaluate_channel_rules(metrics))
        self.assertTrue(results.query("rule_id == 'R36'").iloc[0].hit)
        self.assertTrue(results.query("rule_id == 'R37' and month == '2025-03'").iloc[0].hit)
        month_results = pd.DataFrame(evaluate_month_rules(metrics))
        self.assertTrue(month_results.query("month == '2025-01'").iloc[0].hit)


if __name__ == "__main__":
    unittest.main()
