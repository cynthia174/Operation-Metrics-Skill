---
name: operation-metrics-all-report
description: Run the complete经营分析 workflow from raw data preflight through validated metrics, Rule Result, report, semantic blocks, DOCX, and final QA. Use a partial workflow only when the user explicitly asks for one step.
metadata:
  short-description: Workflow-First 经营分析全链路
---

# Operation Metrics Workflow-First Skill

本 Skill 的默认终点是完整经营分析交付，不是某个单独屏幕、规则、Markdown 或 DOCX 文件。完整链路为：

`Raw Data → Preflight → Field Resolution → Rule Coverage → /plan → User Approval → Normalize → Aggregate → Metrics → Rules → Capability/Facts → Module Contexts → Agent Prompt Modules → Markdown Modules → Assemble → Semantic Blocks → DOCX → DOCX QA → OOXML QA → Final Delivery`

## 入口与路由

- 默认请求进入 [`workflows/full-report.md`](workflows/full-report.md)。
- 数据、字段或规则可执行性检查进入 [`workflows/preflight.md`](workflows/preflight.md)。
- 已有报告/文档的验证进入 [`workflows/qa.md`](workflows/qa.md)。
- 中断、失败或缺口恢复进入 [`workflows/recovery.md`](workflows/recovery.md)。
- 只有用户明确说“只做某一步”时，才允许把局部能力作为独立终点。

## 强制状态机

`INIT → PREFLIGHT → AWAITING_PLAN_APPROVAL → AUTONOMOUS_EXECUTION → VALIDATING → DONE`

Preflight 完成后必须输出 `/plan` 并停止，等待用户确认。确认后进入 `AUTONOMOUS_EXECUTION`，不得在 Normalize、Aggregate、Metrics、Rules、Report 或 DOCX 等中间节点再次询问是否继续。单个节点完成不等于整体任务完成；只有 Definition of Done 满足时才能进入 `DONE`。

## 不可变边界

- 不修改现有 Rule Engine、指标口径、报告五屏结构或 Word 样式参数。
- 正式数字只能来自 validated raw data 和 deterministic metrics；正式经营判断只能来自 official Rule Result。
- 不自行计算、换算、补全或猜测事实；缺口使用“数据不足/待确认”或 `NOT_EXECUTABLE`。
- 结构与格式不能反向改变内容；semantic blocks 若作为上游契约提供，保留其文本、顺序和语义角色。

## 合同与规范

字段、指标、规则、证据、报告和 Word 约束分别见 `references/` 下对应合同。现有实现的事实来源和执行命令仍以 `README.md`、`src/` 及 `docs/rule_result.schema.json` 为准；本 Skill 只编排工作流，不替代业务计算实现。

<!-- 详细的现行五屏内容规范保留在历史实现文档和 report-contract 中；入口不重复承载业务规则。 -->

## Skill-native Prompt Runtime

Python deterministic stages stop after `Module Contexts`. The current host
Agent is the Prompt Runner; the Skill must never call Anthropic, OpenRouter,
an HTTP LLM endpoint, or require an API key for the formal path.

After Module Contexts, execute these Agent Interaction Stages in order:

1. `ChannelPrompt`: read `prompts/shared.md`, `prompts/channel.md`, and
   `contexts/channel.json`; write `modules/channel.md`.
2. `ProductPrompt`: read `prompts/shared.md`, `prompts/product.md`, and
   `contexts/product.json`; write `modules/product.md`.
3. `EfficiencyPrompt`: read `prompts/shared.md`, `prompts/efficiency.md`, and
   `contexts/efficiency.json`; write `modules/efficiency.md`.
4. `GrowthQualityPrompt`: read `prompts/shared.md`,
   `prompts/growth-quality.md`, and `contexts/growth_quality.json`; write
   `modules/growth_quality.md`.
5. `SummaryPrompt`: only after the first four files exist, read
   `prompts/shared.md`, `prompts/summary.md`, `contexts/summary.json`, and
   the four Markdown files; write `modules/summary.md`.

Each module must output only Markdown and use the supplied evidence. It must
not recalculate metrics, invent causes, or state trends when the context does
not support complete periods. Record each Agent stage in the run manifest with
`status`, `prompt_file`, `context_file`, `output_file`, timestamps, output size,
and evidence/input references. A failed module is `FAILED`; never reuse a
previous run's Markdown.

After all five Markdown files are present, return to deterministic execution:

```text
scripts/assemble_report.py
  --channel modules/channel.md
  --product modules/product.md
  --efficiency modules/efficiency.md
  --growth-quality modules/growth_quality.md
  --summary modules/summary.md
  --output semantic_blocks.json
scripts/semantic_blocks_to_docx.py
  --input-blocks semantic_blocks.json
  --output report.docx
```

`semantic_blocks.json` must come from the five Markdown files through
`assemble_report.py`; it must not be copied from `report_model.json`.

## Word 字体规范

当需要将本 Skill 生成的 Markdown 报告转换为 Word 时，默认采用用户提供的参考文档《模型测试v1.4——v3 v4两版提示词.docx》的字体规范：

- 全文主字体：Arial；中文字符也优先保持 Arial 字体设置，由 Word 的字体回退机制显示中文。
- 正文：Arial，11 磅。
- 标题层级：沿用参考文档的字号层级；一级标题默认 18 磅，二级标题默认 16 磅，三级标题默认 15 磅。
- 文档主标题：Arial，26 磅。
- 表格文字：Arial，11 磅；除非用户另行指定，不切换为微软雅黑或宋体。
- 生成 Word 后必须保留可编辑文本和表格，不将整页内容作为图片嵌入。

该规范只约束字体和字号，不替代本 Skill 的报告结构、事实边界和数据缺口规则。若用户提供新的模板或明确指定字体，以最新明确要求为准。

当输入选项为 `all` 时，严格按以下顺序输出一份 Markdown 报告。只输出最终报告，不输出思考过程、分析步骤、推理链、自我解释、数据审查过程或格式选择说明；禁止出现 `<think>` 标签及类似内部工作语言。

## 总体规则

- 所有数字、结论和规则状态必须来自输入事实或正式规则结果；不自行计算、改阈值、补数字或猜测缺失字段。
- 报告面向业务负责人，结论应表达经营含义，不要机械罗列月度指标。
- 每个“发现”写成 `## 发现：一句具有经营含义的标题`，正文 2—4 句话，并附证据列表。先描述变化，再解释经营意义，最后指出风险、机会或边界。
- 缺少某部分数据时直接跳过对应章节，末尾统一保留 `## 数据缺口`，列出“缺少 XXX，影响 XXX 分析”。
- 未命中规则不能写成“没有风险”；未检查不能写成“检查通过”；推断不能升级为确定性结论。
- 除非输入明确提供，不讨论用户画像、复购、运营策略，也不把首单营收写成全量营收或利润。

## 报告结构

### 第一屏 · 渠道全景

```markdown
# 第一屏 · 渠道全景

## 渠道结构
表格。

## 渠道效率趋势
表格。

## 关键发现
最多3条。

## 规则诊断

## 数据缺口
```

只讨论渠道结构、渠道效率趋势及其经营风险；不讨论产品、品类、用户画像、复购或运营策略。可使用“结构性风险、渠道单一、依赖增强、效率改善、规模收缩、获客入口、增长来源”等经营表达。

### 第二屏 · 品类营收结构

```markdown
# 第二屏 · 品类营收结构

## 品类营收概览
表格。

## 持续下行品类
表格。

## 关键发现
最多3条。

## 规则诊断

## 数据缺口
```

只讨论品类首单营收结构、持续下行、集中度和分化。集中度与下行结论必须引用输入中的正式规则结果；不得依据品类名称自行贴“获客型”“深耕型”“核心品类”等标签。极端增速若基数很小，必须同时说明基数影响。

### 第三屏 · 获客成本信号

```markdown
# 第三屏 · 获客成本信号

## 获客成本趋势
表格。

## 关键发现
最多3条。

## 规则诊断

## 数据缺口
```

本屏只讨论渠道获客成本/CAC 率及其变化，不讨论客户结构、客户分层、复购、留存、用户生命周期或运营策略。没有足够证据时，不把成本变化解释成客户质量变化。

### 第四屏 · 投放有效性

```markdown
# 第四屏 · 投放有效性

## 检查结果
表格。

## 关键发现
最多2条。

## 覆盖边界

## 数据缺口
```

本屏只讨论低效消耗占比这一项风险。规则命中状态必须按输入原样表达；未命中只表示该规则条件未触发，不代表整体投放健康。`覆盖边界`说明规则实际检查了什么、没有覆盖什么。

### 第五屏 · 总结

```markdown
# 第五屏 · 总结

## 核心结论
最多4条。

## 已确认风险
表格。

## 优先核查顺序

## 数据缺口
```

本屏只消费前四屏内容，不重新读取明细数据，不引入前四屏没有出现的数字、结论或规则。不要逐屏复述；按覆盖范围和持续时间排序，提炼核心矛盾、已确认风险和优先核查事项。不要输出泛化行动建议，如“优化投放”“加强品牌”“调整 KPI”。

## 输出边界

最终输出只能包含可选的测试标识和上述 Markdown 报告正文。模型名称、时间等变量若未由系统提供，保留变量格式，不自行猜测。
