import unittest
import json
import tempfile
from pathlib import Path

import pandas as pd

from src.field_mapping import FIELD_MAP, source_to_standard
from src.rule_result import write_results
from src.rules import evaluate_category_rules, evaluate_channel_rules, evaluate_month_rules


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
        results = evaluate_category_rules(pd.DataFrame(rows))
        self.assertTrue(next(result for result in results if result.rule_id == "R5" and result.dimension.name == "A" and result.period.end == "2025-03").hit)
        self.assertEqual({result.period.end for result in results if result.rule_id == "R9"}, set(months[2:]))
        self.assertEqual(len([result for result in results if result.rule_id == "R6"]), 4)

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
        results = evaluate_channel_rules(metrics)
        self.assertTrue(next(result for result in results if result.rule_id == "R36").hit)
        self.assertTrue(next(result for result in results if result.rule_id == "R37" and result.period.end == "2025-03").hit)
        month_results = evaluate_month_rules(metrics)
        self.assertTrue(next(result for result in month_results if result.period.end == "2025-01").hit)

        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "results.csv"
            json_path = Path(temp_dir) / "results.json"
            write_results(results + month_results, csv_path, json_path)
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], "1.0")
            self.assertEqual(payload["result_count"], len(results + month_results))
            self.assertIn("metrics", payload["results"][0])
            self.assertIn("evidence", payload["results"][0])

    def test_field_mapping_is_the_only_excel_name_boundary(self):
        self.assertEqual(FIELD_MAP["cost"].source, "获客总成本")
        self.assertEqual(source_to_standard()["获客总成本"], "cost")


if __name__ == "__main__":
    unittest.main()
