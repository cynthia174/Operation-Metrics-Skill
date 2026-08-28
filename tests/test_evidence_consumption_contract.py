import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SHARED = (ROOT / "prompts/shared.md").read_text(encoding="utf-8")
SUMMARY = (ROOT / "prompts/summary.md").read_text(encoding="utf-8")


class EvidenceConsumptionContractTests(unittest.TestCase):
    def test_hit_evidence_fields_are_required(self):
        for token in ("rule_results", "hit == true", "rule_id", "实体", "期间", "evidence"):
            self.assertIn(token, SHARED)

    def test_representative_evidence_not_full_dump(self):
        self.assertIn("按 Rule ID 聚合", SHARED)
        self.assertIn("1—3 条", SHARED)
        self.assertIn("禁止把全部 Rule Results 原样倾倒", SHARED)

    def test_zero_hit_and_semantic_boundaries(self):
        self.assertIn("当前规则体系下未发现命中项", SHARED)
        self.assertIn("单期变化不是长期趋势", SHARED)
        self.assertIn("连续三期下降不是永久恶化", SHARED)
        self.assertNotIn("business health", SHARED.lower())

    def test_summary_propagates_evidence(self):
        for token in ("Rule ID", "命中数量", "代表性实体", "指标值/变化", "不得只写抽象"):
            self.assertIn(token, SUMMARY)


if __name__ == "__main__":
    unittest.main()
