# S3 报告生成工具 — 使用说明

`s3_report_generator.py` 是给通用编码 agent（如 Claude Code）用的两步式工具，不调用任何 LLM API，不用硬编码模板拼报告正文。报告叙事内容永远由使用本工具的 agent 亲自撰写。

## 两步式工作流

```bash
# 第一步：Excel → 渠道/品类月度指标 → 规则引擎 → llm_context.json
python s3_report_generator.py pipeline <excel_file> [--output-dir DIR] [--sheet-name NAME]

# 第二步（agent 手写 Markdown 之后）：Markdown → 按模板样式渲染的 .docx
python s3_report_generator.py render <markdown_file> [--output OUT.docx]
```

### 1. `pipeline`

只产出真实数据事实，不生成任何报告正文：

- `channel_month_metrics.csv` / `category_month_metrics.csv` — 月度指标表
- `rule_results.csv` / `rule_results.json` — 规则引擎命中结果（schema 见 `docs/rule_result.schema.json`）
- `llm_context.json` — 按模块→维度→周期组织的规则命中上下文，供 agent 直接引用

默认输出到 `outputs/runs/{timestamp}/`；也可用 `--output-dir` 指定固定目录。

### 2. agent 撰写 Markdown 正文（本工具不参与这一步）

agent 需要：

1. 阅读 `docs/dify-prompts/` 下对应屏幕的提示词规范（`s3-shared-framework.md`、`shared-context.md`、`screen-02..05-*.md`；screen-01 的内容包含在 `shared-context.md`/`s3-shared-framework.md` 里，没有单独文件）。
2. 阅读 `pipeline` 产出的 `llm_context.json`/`rule_results.json`/指标 CSV 中的真实数据事实。
3. 按提示词规范的结构、语言风格手写 Markdown 报告正文——内容必须忠于真实数据，不得编造。证据类陈述统一使用 `【数据事实】`/`【规则结论】`/`【推断】` 前缀（`render` 会自动识别并加粗染色）。

### 3. `render`

把 agent 写好的 Markdown 渲染为最终 `.docx`，样式规则来自 `test_skill/template.docx` 逆向出的规范（`src/report_docx.py`）：

- 字体：Arial（英文）/ 等线（中文），正文 11pt
- 标题层级：Markdown 中**第一个** `#` = 文档主标题（26pt），**之后每个** `#` = 屏标题（18pt），`##` = 小节标题（16pt），`###` = 发现/规则标题（15pt）
- 项目符号（`- `/`* ` 开头）与正文段落均会自动检测 `【数据事实】`/`【规则结论】`/`【推断】` 前缀并加粗染色（`#1F4E79`）
- GFM 表格（`| a | b |` + 分隔行）会按模板边框样式（`#DEE0E3`）渲染成 Word 表格
- 单独一行的 `---` 会插入分页（用于分隔"屏"）

## 已验证的参考产物

`test_skill/` 保留了一次完整验证的输入与输出，可用于回归检查：

- `interest-island-2026-07-01_2026-07-29.xlsx` — 样例数据
- `generated_report.md` — 已验证结构/语言风格对齐参考报告的手写 Markdown
- `generated_report_v2.docx` — 用当前 `render` 命令从上述 Markdown 生成的最终 docx（99 段落，标题字号/项目符号颜色/证据前缀染色均已核对）
- `template.docx` — 样式来源模板（仅参考其样式，不参考文字内容）
- `build_report_docx.py`/`generate_report_docx.py` — 早期用结构化 `ReportBuilder` API 手写报告的验证脚本，逻辑已并入 `src/report_docx.py`

## 底层数据/规则引擎

`s3_report_generator.py` 的 `pipeline` 子命令只是对以下模块的编排，模块本身的口径说明见根目录 `README.md`：

```
src/field_mapping.py    # Excel列名 → 标准业务字段
src/aggregate_metrics.py
src/metrics/{common,channel,category}.py
src/rules/{channel_rules,category_rules}.py
src/rule_result.py
src/run_rules.py
src/formatter.py        # rule_results.json → llm_context.json
src/report_docx.py      # ReportBuilder + markdown_to_docx
```
