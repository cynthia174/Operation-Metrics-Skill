"""Hard-coded assembly of independently generated report modules.

This script does not generate, summarize, or rewrite module content. It only
parses the five module Markdown outputs and places them in the fixed report
order expected by semantic_blocks_to_docx.py.
"""
import argparse
import json
import re
from pathlib import Path


MODULES = (
    ("channel", "第一屏 · 渠道全景"),
    ("product", "第二屏 · 品类营收结构"),
    ("efficiency", "第三屏 · 获客成本信号"),
    ("growth_quality", "第四屏 · 投放有效性"),
    ("summary", "第五屏 · 总结"),
)


def inline_runs(text):
    """Keep inline-code spans distinguishable to the DOCX renderer."""
    runs = []
    for i, part in enumerate(re.split(r"(`[^`]*`)", text)):
        if not part:
            continue
        if part.startswith("`") and part.endswith("`"):
            runs.append({"type": "inline_code", "text": part[1:-1]})
        else:
            runs.append({"text": part})
    return runs


def add_text_block(blocks, text, role):
    if text.strip():
        block = {"type": role, "text": text.strip()}
        if "`" in text:
            block.pop("text")
            block["runs"] = inline_runs(text.strip())
        blocks.append(block)


def parse_markdown(markdown, expected_title):
    blocks = []
    paragraph = []
    table_rows = []
    in_code = False

    def flush_paragraph():
        nonlocal paragraph
        if paragraph:
            add_text_block(blocks, " ".join(paragraph), "body")
            paragraph = []

    def flush_table():
        nonlocal table_rows
        if table_rows:
            blocks.append({"type": "table", "rows": table_rows})
            table_rows = []

    for raw in markdown.splitlines():
        line = raw.strip()
        if line.startswith("```"):
            flush_paragraph()
            in_code = not in_code
            continue
        if in_code or not line:
            if not line:
                flush_paragraph()
            continue

        heading = re.match(r"^(#{1,3})\s+(.*)$", line)
        if heading:
            flush_paragraph()
            flush_table()
            level, text = len(heading.group(1)), heading.group(2).strip()
            if level == 1:
                # Module headings are fixed by the assembler, not trusted from
                # model output, so the report order cannot drift.
                if text.startswith(("第一屏", "第二屏", "第三屏", "第四屏", "第五屏")):
                    continue
                add_text_block(blocks, text, "section_heading")
            elif text.startswith("发现：") or text.startswith("结论："):
                add_text_block(blocks, text, "finding_heading")
            else:
                add_text_block(blocks, text, "module_heading")
            continue

        if line.startswith("|") and line.endswith("|"):
            flush_paragraph()
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if cells and not all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
                table_rows.append(cells)
            continue
        if line.startswith("- ") or line.startswith("* "):
            flush_paragraph()
            add_text_block(blocks, line[2:].strip(), "list_item")
            continue
        paragraph.append(line)

    flush_paragraph()
    flush_table()
    return [{"type": "section_heading", "text": expected_title}, *blocks]


def main():
    parser = argparse.ArgumentParser(description="Assemble five independent report Markdown outputs.")
    parser.add_argument("--channel", required=True, help="渠道模块 Markdown 输出")
    parser.add_argument("--product", required=True, help="品类模块 Markdown 输出")
    parser.add_argument("--efficiency", required=True, help="获客成本模块 Markdown 输出")
    parser.add_argument("--growth-quality", required=True, help="投放有效性模块 Markdown 输出")
    parser.add_argument("--summary", required=True, help="总结模块 Markdown 输出")
    parser.add_argument("--output", required=True, help="输出 semantic_blocks.json 路径")
    parser.add_argument("--title", default="经营分析报告", help="Word 文档标题")
    args = parser.parse_args()

    paths = vars(args)
    blocks = [{"type": "document_title", "text": args.title}]
    for key, title in MODULES:
        source = Path(paths["growth-quality"] if key == "growth_quality" else paths[key])
        if not source.is_file():
            parser.error(f"module file not found: {source}")
        blocks.extend(parse_markdown(source.read_text(encoding="utf-8"), title))

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"blocks": blocks}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
