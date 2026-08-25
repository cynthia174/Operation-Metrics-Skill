# Operation Metrics Skill — 经营指标规则引擎 + 报告生成

给通用编码 agent（如 Claude Code）使用的一项"技能"：把一份原始经营数据 Excel，转成可直接引用、不能编造的结构化事实（指标表 + 规则命中结果 + LLM 上下文），再由 agent 依据这些事实手写分析报告正文，最终渲染成排版好的 `.docx`。

**这不是一个会自动生成报告结论的黑盒。** 它只负责"计算"和"渲染"，不调用任何 LLM API，不用模板拼报告正文——所有分析性文字都必须由调用它的 agent 参照真实数据事实亲自撰写。这是本技能刻意的设计边界：数值和规则判定必须可追溯、可复现；叙事和洞察留给 agent，因为那部分依赖业务语境，不该被硬编码。

## 输入 → 输出总览

```
Excel（经营数据） ──▶ [规则引擎]  ──▶ llm_context.json / rule_results.json / 指标 CSV
                                              │
                                              ▼
                              agent 阅读事实 + 提示词规范，手写 Markdown 报告正文
                                              │
                                              ▼
                                       [render]  ──▶  最终 .docx 报告
```

- **输入**：一份 Excel 工作表，每行是某天某渠道某品类的经营流水（详见下方"输入字段"）。
- **中间产物**：月度指标表（CSV）、规则命中结果（CSV + JSON）、供 agent 阅读的分组事实上下文（JSON）。
- **agent 的工作**（本技能不代劳）：读完上述事实和 `docs/dify-prompts/` 下的写作规范后，手写 Markdown 报告正文。
- **输出**：一份按固定样式排版的 `.docx` 经营分析报告。

## 中间链路（详细）

```
Excel
  │  src/field_mapping.py  ——  中文列名 → 标准业务字段名、类型校验
  ▼
字段语义映射
  │  src/aggregate_metrics.py + src/metrics/{common,channel,category}.py
  ▼
指标计算层  ——  按 month+channel / month+category 聚合，再算率类指标
  │  src/run_rules.py + src/rules/{category_rules,channel_rules}.py
  ▼
Rule Engine（S1-S4 规则评价）
  │  src/rule_result.py  ——  校验、去重、序列化
  ▼
rule_results.csv / rule_results.json   ◀── 正式 JSON Schema: docs/rule_result.schema.json
  │  src/formatter.py
  ▼
llm_context.json  ——  按「模块→维度→周期」分组，保留原始 fact 不改写
  │
  │  （agent 在此处介入：阅读 docs/dify-prompts/*，对照事实手写 Markdown 报告正文）
  ▼
report_draft.md（agent 撰写，本技能不生成）
  │  src/report_docx.py :: markdown_to_docx
  ▼
最终 .docx 报告
```

整条链路由 `s3_report_generator.py` 编排成两个可独立调用的子命令：`pipeline`（Excel → llm_context.json，即上图前半段）和 `render`（Markdown → .docx，即上图后半段）。中间"agent 手写 Markdown"这一步是刻意留白的人工/agent 介入点，不属于任何子命令。

## 输入文件要求

Excel 需要包含以下列（列名为中文，`src/field_mapping.py::FIELD_MAP` 是权威映射表，以后列名变化只改这一处）：

| 标准字段 | Excel 列名 | 类型 | 说明 |
|---|---|---|---|
| `stat_date` | 统计日期 | 日期 | 用于聚合出自然月 |
| `category` | 所属品类 | 字符串 | S1 品类维度分析用 |
| `channel` | 渠道名称 | 字符串 | S2/S3 渠道维度分析用 |
| `leads` | 线索数 | 数值 | 可加总 |
| `first_order_orders` | 首单订单数 | 数值 | 可加总，也是首购用户代理 |
| `cost` | 获客总成本 | 数值 | 可加总 |
| `first_order_revenue` | 首单营收 | 数值 | 可加总 |
| `first_order_formal_revenue` | 首单正式营流水 | 数值 | 可加总 |
| `first_order_net_revenue` | 首单净流水 | 数值 | 可加总，CAC率分母 |
| `first_order_refund_revenue` | 首单正式营退款流水 | 数值 | 可加总 |
| `repeat_leads` | 本品重复线索数 | 数值 | 可加总 |
| `repeat_leads_90d` | 本品重复线索数(90天内) | 数值 | 可加总 |

加载阶段会一次性校验上述列是否齐全，缺列直接报错终止，不静默补零、不猜测默认值。维度字段（`category`/`channel`）为空、或金额/数量列无法转成数值时同样立即失败。Excel 页签名默认是`数据源`，可通过 `--sheet-name` 参数改成实际页签名。

## 输出文件格式

### 1. 指标表：`channel_month_metrics.csv` / `category_month_metrics.csv`

按 `month + channel` 或 `month + category` 聚合后的月度指标表，率类指标（如 `cac`、`channel_roi`、`repeat_lead_rate`）用聚合后的分子分母重新计算，不对每行原始比率求平均。

### 2. 规则结果：`rule_results.json`（权威 schema：`docs/rule_result.schema.json`）

```json
{
  "schema_version": "1.0",
  "result_count": 0,
  "hit_count": 0,
  "results": [
    {
      "module": "S1",
      "rule_id": "R3",
      "rule_name": "...",
      "hit": true,
      "dimension": { "type": "category", "name": "..." },
      "period": { "start": "2025-08", "end": "2025-08" },
      "metrics": { "...": 0 },
      "threshold": "...",
      "evidence": ["..."]
    }
  ]
}
```

- `module` 固定是 `S1`~`S4`；`hit=false` 的记录同样保留（代表"已检查但未命中"）。
- `metrics` 是机器可读数值快照，`evidence` 是可直接引用的事实文本，agent **不应重新计算**阈值或比例。
- 唯一键为 `rule_id + dimension.type + dimension.name + period.start + period.end`；导出前拒绝重复键、`NaN`、`inf`。
- `rule_results.csv` 是同一批结果的扁平化版本，用于人工查看或表格工具。

### 3. LLM 上下文：`llm_context.json`

`formatter.py` 把 `rule_results.json` 重新分组为 `模块 → 维度 → 周期`，但**不改写**任何 `fact` 内容：

- `source`：原始 schema 版本、结果数、命中数。
- `usage.instructions`：写给 agent 的使用约束（例如"不要重新计算 metrics"）。
- `rule_catalog`：`rule_id` + `rule_name` 的可读规则清单。
- `modules[].dimensions[].periods[].results[].fact`：原始 `rule_results.json` 记录，逐字保留。

输出为紧凑 JSON（无多余空白），方便直接注入 agent 的 Prompt 上下文。

### 4. 最终报告：`.docx`

`render` 子命令把 agent 手写的 Markdown 按以下规则渲染：

- 第一个 `#` → 文档主标题（26pt）；之后每个 `#` → 屏标题（18pt）；`##` → 小节标题（16pt）；`###` → 发现/规则标题（15pt）。
- `- `/`* ` 开头的行 → 项目符号列表；纯文本行 → 正文段落（11pt）。
- 项目符号和正文段落都会自动识别 `【数据事实】`/`【规则结论】`/`【推断】` 前缀，加粗并染色（`#1F4E79`），用于区分陈述的证据等级。
- GFM 表格（`| a | b |` + 分隔行）渲染成带边框（`#DEE0E3`）的 Word 表格。
- 单独一行的 `---` 插入分页，用于分隔报告的不同"屏"。

## 部署方式

本技能没有服务端组件，是一个本地 Python CLI，由 agent 在包含 `src/`、`docs/dify-prompts/`、目标 Excel 文件的工作目录中直接调用。

**环境要求**：Python 3.10+（代码使用 `from __future__ import annotations` 及 `X | None` 风格类型注解）。仓库未提供 `requirements.txt`，需要的第三方包：

```bash
pip install pandas openpyxl python-docx
```

- `pandas` — 指标聚合与规则计算。
- `openpyxl` — `pandas.read_excel` 读取 `.xlsx` 所需的引擎（pandas 本身不带）。
- `python-docx`（导入名 `docx`）— `render` 子命令生成 `.docx`。

**调用方式**：

```bash
# 第一步：Excel → 指标 → 规则 → llm_context.json（不生成报告正文）
python s3_report_generator.py pipeline <excel_file> [--output-dir DIR] [--sheet-name 数据源]

# 第二步（agent 手写 Markdown 报告正文之后）
python s3_report_generator.py render <markdown_file> [--output report.docx]
```

`S3ReportGenerator` 会自动向上查找同时包含 `src/` 和 `docs/` 的目录作为项目根（最多向上找 5 层），找不到时需要显式传 `--project-root`。`pipeline` 默认把中间产物写到 `outputs/runs/{timestamp}/`，可用 `--output-dir` 固定到指定目录。两个子命令都不需要网络访问或任何 API key。

也可以绕过 CLI，分别单独调用底层脚本（`src/aggregate_metrics.py` → `src/run_rules.py` → `src/formatter.py`），历史命令示例见 `TOOL_OVERVIEW.md`。

## 代码结构

```text
src/
├── field_mapping.py          # Excel列名 → 标准业务字段、类型、含义
├── aggregate_metrics.py      # Excel输入和指标表输出编排
├── metrics/
│   ├── common.py             # 完整月与安全除法
│   ├── channel.py            # month + channel 指标
│   └── category.py           # month + category 指标
├── rules/
│   ├── channel_rules.py      # S2、S3规则
│   └── category_rules.py     # S1规则
├── rule_result.py            # Rule Result对象、校验、CSV/JSON序列化
├── formatter.py              # Rule Result JSON → LLM分析上下文
├── run_rules.py              # Rule Engine命令行入口
└── report_docx.py            # Markdown → .docx 渲染（ReportBuilder）
s3_report_generator.py        # pipeline / render 两个子命令的统一入口
docs/
├── rule_result.schema.json   # rule_results.json 的正式 JSON Schema
└── dify-prompts/              # agent 撰写报告正文时参考的写作规范
```

更详细的 `s3_report_generator.py` 使用说明、Markdown 写作约定、已验证的参考产物见 `TOOL_OVERVIEW.md`。

## 现行计算口径

- `channel` 固定取 `渠道名称`（见 `src/field_mapping.py`）。
- 所有金额和计数先按 `month + channel` 求和，率类指标再用聚合后的分子、分母重算。
- `first_order_users_proxy = 首单订单数`，仅作首购用户代理；源表没有去重用户 ID。
- `cac = 获客总成本 / 首单订单数`，用于指标展示。
- 现有 R36/R37 的正式规则字段是 `cac_rate = 获客总成本 / 首单净流水`，不能与 `cac` 混用。
- `channel_roi = 首单营收 / 获客总成本`。
- `repeat_lead_rate` 只是重复线索率，不是复购率。
- 仅完整自然月进入跨月规则；当前样例中 2025-07 和 2025-11 不完整。
- S1 品类收入使用源字段 `所属品类` 与 `首单营收`，不把渠道或投放计划冒充品类。
- R3：Top1 品类首单营收占比 `>50%`；R4：Top3 占比 `<50%`。
- R5：同品类首单营收连续 3 个完整自然月下降。
- R6：连续 6 个完整自然月中，营收环比方向切换至少 3 次；样例历史不足时不生成该规则评价行。
- R8：同月同时存在品类营收环比 `>30%` 和 `<-30%`。
- R9：超过 3 个品类满足 R5 的连续下降条件。
- R36：CAC率连续 3 个完整月上升；R37：CAC率单月环比增加超过 5 个百分点。
- R61：`ROI<0.5` 的渠道消耗占全渠道消耗比例 `>20%`。

当前现行且可实际执行：S1 的 R3、R4、R5、R6、R8、R9；S2 的 R36、R37；S3 的 R61。S4 没有竞品或市场份额真实数据，因此不生成规则。R38/R39/R48/R49 需要业务提供固定渠道类型或 ROI 红线映射；复购、沉默用户规则需要客户级购买记录，不能用重复线索字段替代。
