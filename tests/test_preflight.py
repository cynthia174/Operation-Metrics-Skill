import tempfile
import unittest
import zipfile
import os
from unittest.mock import patch
from pathlib import Path
import pandas as pd
import subprocess
import sys

from src.preflight import build_preflight, resolve_fields, resolve_config


class PreflightTests(unittest.TestCase):
    def test_config_resolution_is_independent_of_cwd(self):
        code = "from src.preflight import resolve_config; print(resolve_config('metric_dependencies.yaml'))"
        result = subprocess.run([sys.executable, "-c", code], cwd=Path(tempfile.mkdtemp()),
                                env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])},
                                capture_output=True, text=True, check=True)
        self.assertEqual(Path(result.stdout.strip()), Path(__file__).resolve().parents[1] / "config/metric_dependencies.yaml")

    def test_explicit_config_path(self):
        config_dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__('shutil').rmtree(config_dir, ignore_errors=True))
        for name in ("metric_dependencies.yaml", "rule_dependencies.yaml", "field_aliases.yaml"):
            (config_dir / name).write_text((Path(__file__).resolve().parents[1] / "config" / name).read_text(encoding="utf-8"), encoding="utf-8")
        self.assertEqual(resolve_config("metric_dependencies.yaml", config_dir), (config_dir / "metric_dependencies.yaml").resolve())

    def test_missing_config_reports_resolved_path(self):
        missing = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__('shutil').rmtree(missing, ignore_errors=True))
        with self.assertRaisesRegex(FileNotFoundError, r"config missing: resolved path=.*metric_dependencies\.yaml"):
            resolve_config("metric_dependencies.yaml", missing)
    def _csv(self, columns):
        temp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
        temp.close()
        path = Path(temp.name)
        pd.DataFrame([{c: ("2025-01-01" if c == "统计日期" else 1) for c in columns}]).to_csv(path, index=False)
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        return path

    def test_exact_and_alias_mapping(self):
        path = self._csv(["统计日期", "三级渠道", "所属品类", "获客成本"])
        rows = build_preflight(path)["field_resolution"]
        self.assertEqual(next(r for r in rows if r["raw_field"] == "三级渠道")["status"], "mapped")
        self.assertEqual(next(r for r in rows if r["raw_field"] == "获客成本")["mapping_method"], "alias")

    def test_ambiguous_and_missing_are_explicit(self):
        path = self._csv(["统计日期", "渠道"])
        payload = build_preflight(path)
        self.assertEqual(next(r for r in payload["field_resolution"] if r["raw_field"] == "渠道")["status"], "mapped")
        self.assertEqual(next(r for r in payload["field_resolution"] if r["canonical_field"] == "cost")["status"], "missing")
        self.assertTrue(any(x["status"] == "blocked" for x in payload["rule_coverage"]))

    def test_ambiguous_header_is_not_guessed(self):
        aliases = {"stat_date": ["日期"], "category": ["业务"], "channel": ["业务"]}
        with patch("src.preflight._load", return_value={"aliases": aliases}):
            row = resolve_fields(["业务"], "x.csv", "__csv__")[0]
        self.assertEqual(row["status"], "ambiguous")
        self.assertIsNone(row["canonical_field"])

    def test_unknown_rule_is_not_created_and_no_conclusion(self):
        payload = build_preflight(self._csv(["统计日期"]))
        self.assertNotIn("R999", {x["rule_id"] for x in payload["rule_coverage"]})
        self.assertFalse(payload["conclusion_generated"])
        self.assertNotIn("conclusions", payload)

    def test_xlsx_without_dimension_uses_real_rows(self):
        fd, source_name = tempfile.mkstemp(suffix=".xlsx")
        os.close(fd)
        source = Path(source_name)
        stripped = source.with_name(source.stem + "_no_dimension.xlsx")
        self.addCleanup(lambda: source.unlink(missing_ok=True))
        self.addCleanup(lambda: stripped.unlink(missing_ok=True))
        pd.DataFrame([
            {"统计日期": "2025-01-01", "所属品类": "品类A", "三级渠道": "渠道A"},
            {"统计日期": "2025-01-02", "所属品类": "品类A", "三级渠道": "渠道A"},
        ]).to_excel(source, index=False, sheet_name="数据源")
        with zipfile.ZipFile(source) as zin, zipfile.ZipFile(stripped, "w") as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename == "xl/worksheets/sheet1.xml":
                    data = data.replace(b'<dimension ref="A1:C3"/>', b"")
                zout.writestr(item, data)
        payload = build_preflight(stripped)
        discovery = payload["discoveries"][0]
        self.assertEqual(discovery["source_sheet"], "数据源")
        self.assertEqual(discovery["row_count"], 2)
        self.assertEqual(len(discovery["headers"]), 3)
        self.assertEqual(next(r for r in payload["field_resolution"] if r["raw_field"] == "三级渠道")["status"], "mapped")


if __name__ == "__main__":
    unittest.main()
