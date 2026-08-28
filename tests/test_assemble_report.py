import json
import subprocess
import sys
from pathlib import Path


def test_assemble_report_accepts_growth_quality_key(tmp_path):
    names = ["channel", "product", "efficiency", "growth_quality", "summary"]
    paths = {}
    for name in names:
        path = tmp_path / f"{name}.md"
        path.write_text(f"# {name}\n\n## 发现：{name}\n\n证据：{name}\n", encoding="utf-8")
        paths[name] = path
    output = tmp_path / "semantic_blocks.json"
    command = [
        sys.executable,
        "scripts/assemble_report.py",
        "--channel", str(paths["channel"]),
        "--product", str(paths["product"]),
        "--efficiency", str(paths["efficiency"]),
        "--growth-quality", str(paths["growth_quality"]),
        "--summary", str(paths["summary"]),
        "--output", str(output),
    ]
    subprocess.run(command, cwd=Path(__file__).resolve().parents[1], check=True)
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert len(payload["blocks"]) == 21
    headings = [b["text"] for b in payload["blocks"] if b["type"] == "section_heading"]
    assert [
        "第一屏 · 渠道全景", "第二屏 · 品类营收结构", "第三屏 · 获客成本信号",
        "第四屏 · 投放有效性", "第五屏 · 总结",
    ] == [x for x in headings if x.startswith(("第一屏", "第二屏", "第三屏", "第四屏", "第五屏"))]
    assert any(b.get("text") == "证据：growth_quality" for b in payload["blocks"])
