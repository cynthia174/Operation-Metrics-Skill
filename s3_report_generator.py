#!/usr/bin/env python3
"""
S3 Business Analysis Report Generator - Universal Tool

两步式工作流，供任意通用编码 agent 使用：

  1. pipeline: Excel → 渠道/品类月度指标 → 规则引擎 → llm_context.json
     只产出真实数据事实，不生成任何报告正文。
  2. agent 阅读 docs/dify-prompts/ 下对应屏幕的提示词规范 + pipeline 产出的
     数据事实，亲自撰写 Markdown 报告正文（本工具不调用 LLM API、不用硬编码
     模板拼报告 —— 正文叙事必须由使用本工具的 agent 完成）。
  3. render: 把 agent 写好的 Markdown 按 test_skill/template.docx 的样式规范
     （字体、标题层级、项目符号、表格边框等）渲染成最终 .docx。

用法：
  python s3_report_generator.py pipeline <excel_file> [--output-dir <dir>] [--sheet-name <sheet>]
  python s3_report_generator.py render <markdown_file> [--output <report.docx>]

示例：
  python s3_report_generator.py pipeline reference/data.xlsx --output-dir outputs/run1
  python s3_report_generator.py render outputs/run1/report_draft.md --output outputs/reports/report.docx
"""

import sys
import json
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.report_docx import markdown_to_docx


class S3ReportGenerator:
    """S3 渠道结构诊断 - 数据管线（Excel → metrics → rules → llm_context.json）"""

    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or self._find_project_root()
        self.src_dir = self.project_root / "src"
        self.docs_dir = self.project_root / "docs"
        self.prompts_dir = self.docs_dir / "dify-prompts"

        self._validate_environment()

    def _find_project_root(self) -> Path:
        """自动查找项目根目录（包含 src/ 和 docs/）"""
        current = Path.cwd()
        for _ in range(5):
            if (current / "src").exists() and (current / "docs").exists():
                return current
            current = current.parent
        raise RuntimeError("无法找到项目根目录，请指定 --project-root")

    def _validate_environment(self):
        """验证必需的文件和目录"""
        required = [
            self.src_dir / "aggregate_metrics.py",
            self.src_dir / "run_rules.py",
            self.src_dir / "formatter.py",
            self.prompts_dir / "shared-context.md",
        ]
        missing = [p for p in required if not p.exists()]
        if missing:
            raise RuntimeError(f"缺失必需文件：{missing}")

    def run_pipeline(self, excel_path: str, output_dir: Optional[str] = None,
                      sheet_name: str = "数据源") -> Dict[str, Path]:
        """
        运行 Excel → metrics → rules → llm_context.json 数据管线

        Args:
            excel_path: Excel 文件路径
            output_dir: 中间产物输出目录，为None时自动生成
            sheet_name: Excel 页签名称

        Returns:
            产物路径字典：channel_metrics/category_metrics/rule_results/llm_context
        """
        excel_path = Path(excel_path)
        if not excel_path.is_absolute():
            excel_path = self.project_root / excel_path

        if not excel_path.exists():
            raise FileNotFoundError(f"Excel 文件不存在：{excel_path}")

        if output_dir:
            output_dir = Path(output_dir)
            if not output_dir.is_absolute():
                output_dir = self.project_root / output_dir
        else:
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            output_dir = self.project_root / "outputs" / "runs" / timestamp

        output_dir.mkdir(parents=True, exist_ok=True)

        print("=" * 70)
        print("S3 BUSINESS ANALYSIS - DATA PIPELINE")
        print("=" * 70)
        print(f"📥 Input:  {excel_path}")
        print(f"📁 Output: {output_dir}")
        print(f"📊 Sheet:  {sheet_name}")
        print()

        channel_metrics = output_dir / "channel_month_metrics.csv"
        category_metrics = output_dir / "category_month_metrics.csv"
        rule_results_csv = output_dir / "rule_results.csv"
        rule_results_json = output_dir / "rule_results.json"
        llm_context = output_dir / "llm_context.json"

        try:
            print("▶ Step 1/3: Computing metrics...")
            self._run_python_script(
                self.src_dir / "aggregate_metrics.py",
                [
                    str(excel_path),
                    str(channel_metrics),
                    "--category-output", str(category_metrics),
                    "--sheet-name", sheet_name,
                ]
            )
            print("✓ Metrics computed")

            print("\n▶ Step 2/3: Executing rules...")
            self._run_python_script(
                self.src_dir / "run_rules.py",
                [
                    str(channel_metrics),
                    str(rule_results_csv),
                    "--category-metrics", str(category_metrics),
                    "--json-output", str(rule_results_json),
                ]
            )
            print("✓ Rules executed")

            print("\n▶ Step 3/3: Formatting LLM context...")
            self._run_python_script(
                self.src_dir / "formatter.py",
                [str(rule_results_json), str(llm_context)]
            )
            print("✓ LLM context prepared")

        except Exception as e:
            print(f"\n✗ Error: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

        rules_data = json.loads(rule_results_json.read_text(encoding="utf-8"))

        print("\n" + "=" * 70)
        print("✓ PIPELINE COMPLETE")
        print("=" * 70)
        print(f"📄 channel_month_metrics: {channel_metrics}")
        print(f"📄 category_month_metrics: {category_metrics}")
        print(f"📄 rule_results:          {rule_results_json}")
        print(f"📄 llm_context:           {llm_context}")
        print(f"✅ Rules hit: {rules_data.get('hit_count', 0)}/{rules_data.get('result_count', 0)}")
        print()
        print("下一步（由使用本工具的 agent 完成，本工具不会自动生成报告正文）：")
        print(f"  1. 阅读 {self.prompts_dir} 下对应屏幕的提示词规范")
        print(f"  2. 阅读上述 llm_context.json / rule_results.json / metrics CSV 中的真实数据事实")
        print(f"  3. 按提示词规范手写 Markdown 报告正文（结构/语言风格对齐规范，内容忠于真实数据）")
        print(f"  4. 运行 `python s3_report_generator.py render <markdown_file> --output <report.docx>` "
              f"把 Markdown 渲染为最终 docx")

        return {
            "channel_metrics": channel_metrics,
            "category_metrics": category_metrics,
            "rule_results_csv": rule_results_csv,
            "rule_results_json": rule_results_json,
            "llm_context": llm_context,
        }

    def _run_python_script(self, script_path: Path, args: list) -> str:
        """运行 Python 脚本"""
        cmd = [sys.executable, str(script_path)] + args
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=300
            )
            if result.returncode != 0:
                raise RuntimeError(f"Script failed:\n{result.stderr}")
            return result.stdout
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Script timeout: {script_path}")


def render_docx(markdown_path: Path, output_path: Path) -> Path:
    """把 agent 撰写的 Markdown 报告渲染为按 template.docx 样式排版的 .docx"""
    if not markdown_path.exists():
        raise FileNotFoundError(f"Markdown 文件不存在：{markdown_path}")

    markdown_text = markdown_path.read_text(encoding="utf-8")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_to_docx(markdown_text, output_path)
    return output_path


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description="S3 Business Analysis Report Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python s3_report_generator.py pipeline reference/data.xlsx --output-dir outputs/run1
  python s3_report_generator.py pipeline data.xlsx --sheet-name "Sheet1" --project-root /path/to/project
  python s3_report_generator.py render outputs/run1/report_draft.md --output outputs/reports/report.docx
        """
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    pipeline_parser = subparsers.add_parser(
        "pipeline", help="Excel → metrics → rules → llm_context.json（不生成报告正文）"
    )
    pipeline_parser.add_argument("excel_file", help="Input Excel file path")
    pipeline_parser.add_argument(
        "--output-dir", "-d",
        help="中间产物输出目录（默认: outputs/runs/{timestamp}）"
    )
    pipeline_parser.add_argument(
        "--sheet-name", "-s",
        default="数据源",
        help="Excel sheet name (default: 数据源)"
    )
    pipeline_parser.add_argument(
        "--project-root", "-p",
        help="Project root directory (auto-detected if not specified)"
    )

    render_parser = subparsers.add_parser(
        "render", help="把 agent 撰写的 Markdown 报告渲染为 .docx"
    )
    render_parser.add_argument("markdown_file", help="Agent 撰写的 Markdown 报告文件路径")
    render_parser.add_argument(
        "--output", "-o",
        help="输出 docx 路径（默认: outputs/reports/s3-report-{timestamp}.docx）"
    )

    args = parser.parse_args()

    try:
        if args.command == "pipeline":
            project_root = Path(args.project_root) if args.project_root else None
            generator = S3ReportGenerator(project_root=project_root)
            generator.run_pipeline(
                args.excel_file,
                output_dir=args.output_dir,
                sheet_name=args.sheet_name,
            )
        elif args.command == "render":
            markdown_path = Path(args.markdown_file)
            if args.output:
                output_path = Path(args.output)
            else:
                output_dir = Path.cwd() / "outputs" / "reports"
                timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                output_path = output_dir / f"s3-report-{timestamp}.docx"
            result_path = render_docx(markdown_path, output_path)
            print(f"✓ Report rendered: {result_path}")
        sys.exit(0)
    except Exception as e:
        print(f"\n✗ Fatal error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
