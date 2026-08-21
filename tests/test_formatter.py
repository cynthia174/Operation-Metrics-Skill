import json
import tempfile
import unittest
from pathlib import Path

from src.formatter import extract_facts, format_rule_results, load_rule_results, write_context


class FormatterTests(unittest.TestCase):
    def setUp(self):
        self.payload = {
            "schema_version": "1.0", "result_count": 2, "hit_count": 1,
            "results": [
                {"module": "S2", "rule_id": "R36", "rule_name": "CAC连续上升", "hit": True,
                 "dimension": {"type": "channel", "name": "渠道A"},
                 "period": {"start": "2025-08", "end": "2025-10"},
                 "metrics": {"current_cac_rate": 0.61}, "threshold": "连续3个完整月上升",
                 "evidence": ["10月CAC率 0.61"]},
                {"module": "S1", "rule_id": "R3", "rule_name": "营收集中度", "hit": False,
                 "dimension": {"type": "all_categories", "name": "__ALL__"},
                 "period": {"start": "2025-10", "end": "2025-10"},
                 "metrics": {"top1_share": 0.3}, "threshold": "Top1品类首单营收占比 > 0.50",
                 "evidence": ["Top1占比 0.3"]},
            ],
        }

    def test_preserves_every_fact_without_mutation(self):
        context = format_rule_results(self.payload)
        facts = extract_facts(context)
        self.assertCountEqual(
            [json.dumps(fact, ensure_ascii=False, sort_keys=True) for fact in facts],
            [json.dumps(fact, ensure_ascii=False, sort_keys=True) for fact in self.payload["results"]],
        )
        self.assertEqual(context["rule_catalog"][1]["display_name"], "R36｜CAC连续上升")

    def test_groups_by_module_dimension_and_period(self):
        context = format_rule_results(self.payload)
        self.assertEqual([module["id"] for module in context["modules"]], ["S1", "S2"])
        s2 = context["modules"][1]
        self.assertEqual(s2["name"], "客户结构")
        self.assertEqual(s2["dimensions"][0]["type"], "channel")
        self.assertEqual(s2["dimensions"][0]["periods"][0]["start"], "2025-08")

    def test_io_helpers_produce_parseable_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "input.json"
            output_path = Path(temp_dir) / "context.json"
            input_path.write_text(json.dumps(self.payload, ensure_ascii=False), encoding="utf-8")
            context = format_rule_results(load_rule_results(input_path))
            write_context(context, output_path)
            parsed = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(parsed["source"]["result_count"], 2)


if __name__ == "__main__":
    unittest.main()
