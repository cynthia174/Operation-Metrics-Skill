# Agent Native Golden Example

## 目的

本目录固化 `manual_check_004_agent_native` 的一次完整成功 Agent Skill E2E，作为回归验证、人工对照和 Skill 行为说明的 Golden Example。

它不是未来新 Run 的正文模板，也不是报告内容输入。正式 Pipeline 不得读取 `examples/agent_native_demo/modules/*.md` 或 `examples/agent_native_demo/report.docx` 作为新报告内容。

## 输入

本 Demo 使用的 Excel 是：

`raw_data/兴趣岛五年渠道真实数据_分卷03_20240703-20241229.xlsx`

该文件未复制到 Demo 目录，原因是体积和真实业务数据提交风险。运行时应提供该文件，并以 `demo_manifest.json` 中的观察期和行数作为对照。

## 完整成功链路

`Excel → Preflight → Metrics → Rules → CapabilityFacts → ModuleContexts → 当前宿主 Agent → ChannelPrompt → ProductPrompt → EfficiencyPrompt → GrowthQualityPrompt → SummaryPrompt → 五个 Markdown → assemble_report.py → semantic_blocks.json → semantic_blocks_to_docx.py → report.docx`

Prompt Modules 由当前宿主 Agent 执行，不依赖外部模型 API。该次运行的五个正式 Markdown 位于 `modules/`，Semantic Blocks 和最终 Word 是本次运行的固化产物。

## 主要输出

- `modules/channel.md`
- `modules/product.md`
- `modules/efficiency.md`
- `modules/growth_quality.md`
- `modules/summary.md`
- `semantic_blocks.json`（92 个 blocks）
- `report.docx`
- `capabilities.json`
- `rule_results.json`（527 条结果，175 条命中）
- `contexts/*.json`

## 当前 Demo 展示的能力

- 区分 CAC 单期跳升与连续上行
- 识别品类连续下行和结构分化
- 区分规则未命中与整体健康
- 在 Summary 汇总跨模块经营信号
- 保留 Evidence、数据缺口和结论边界

## 数据边界

观察期为 2024-07-03 至 2024-12-29。当前输出中的经营判断只能依据本次 Rule Result、CapabilityFacts 和模块上下文；缺少渠道类型、利润及品类 × 渠道交叉证据时，不扩展为归因结论。

## 人工检查

1. 查看 `demo_manifest.json`，确认 run 名称、观察期、指标行数和规则计数。
2. 检查五个 `modules/*.md` 均存在，并分别包含对应屏幕标题。
3. 打开 `semantic_blocks.json`，确认可解析且包含五个一级模块标题。
4. 打开 `report.docx`，确认五个模块、表格、证据文字均可见且文档非空。
5. 对照 `rule_results.json` 检查模块中的规则数量和命中表述；不要要求未来 Agent 输出逐字相同。

## 未来回归

运行 `pytest -q tests/test_agent_native_demo.py`。该测试只检查结构性 Contract：五模块、Semantic Blocks 可解析、Word 可打开且包含五个报告章节、不包含明显 debug dump，并确认 Demo 文件没有进入正式 runtime lineage。它不做逐字 Golden Snapshot 比较。

本目录中的 Markdown、Semantic Blocks 和 Word 仅用于回归与展示；未来新报告必须由正式 Pipeline 从新的输入和当前 Prompt 重新生成。
