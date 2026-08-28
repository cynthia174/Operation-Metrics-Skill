import json
import zipfile
from pathlib import Path

from docx import Document


ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "agent_native_demo"


def test_agent_native_golden_structure_and_lineage():
    manifest = json.loads((DEMO / "demo_manifest.json").read_text(encoding="utf-8"))
    assert manifest["created_from_run"] == "manual_check_004_agent_native"
    assert manifest["semantic_blocks_count"] == 92

    module_names = manifest["module_names"]
    for name in module_names:
        assert (DEMO / "modules" / f"{name}.md").is_file()

    blocks = json.loads((DEMO / "semantic_blocks.json").read_text(encoding="utf-8"))
    assert len(blocks["blocks"]) == manifest["semantic_blocks_count"]
    section_text = "\n".join(
        str(block.get("text", ""))
        for block in blocks["blocks"]
        if block.get("type") == "section_heading"
    )
    for title in manifest["expected_report_sections"]:
        assert title in section_text

    document = Document(DEMO / "report.docx")
    text = "\n".join(p.text for p in document.paragraphs)
    assert text.strip()
    for title in manifest["expected_report_sections"]:
        assert title in text
    assert "first_order_revenue=" not in text
    assert "category_revenue=" not in text
    with zipfile.ZipFile(DEMO / "report.docx") as package:
        assert "word/document.xml" in package.namelist()

    # Demo artifacts are never valid runtime inputs or lineage sources.
    assert "agent_native_demo" not in json.dumps(blocks, ensure_ascii=False)
