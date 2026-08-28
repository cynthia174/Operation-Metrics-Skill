# 经营分析智能体标准 Demo Case

这是一个不含真实客户、个人信息或商业秘密的 synthetic 黄金路径。输入包含 2025 年 1–6 月、4 个品类和 3 个三级渠道；每月同时有月初与月末记录，因此能被当前实现识别为完整自然月。

## What happens?

上传经营数据后，Skill 先识别文件、页签、日期范围和字段语义，再按 `month + channel`、`month + category` 聚合金额与数量，重算 CAC、CAC 率、ROI、Revenue Mix 等指标，执行当前可执行规则，最后把事实和命中规则编排为报告并生成可编辑 Word。

## Input

数据使用中文业务语义字段，不要求调用方理解内部标准字段名。当前映射支持的典型字段包括：统计日期、所属品类、三级渠道、线索数、首单订单数、获客总成本、首单营收、首单净流水，以及正式营收/退款/重复线索字段。实际别名解析以 `config/field_aliases.yaml` 和 Preflight 输出为准。

## Pipeline

`Preflight → Plan → Metrics → Rules → Report → Word`

本 Demo 的实际 CLI 还会记录一次 approval 状态、事实 QA、Semantic Blocks、DOCX QA、OOXML QA 和 artifact lineage QA。

## Example Findings

以下内容均来自本 Demo 的真实输出，不是手工添加的报告结论：

1. **品类营收集中度规则在 2025-01 至 2025-04 命中。** 基础版 Top1 首单营收占比依次为 60.00%、56.70%、52.63%、50.54%，来源 `expected/rule_results.json` 的 R3 和 `expected/category_metrics.csv` 的 `revenue_share`；这是 Rule Finding，不是 Derived Fact。
2. **基础版在 2025-01 至 2025-06 持续下行。** 2025-01 为 795.00，2025-03 为 662.50，2025-06 为 543.25，来源 `expected/category_metrics.csv`；规则证据由 `expected/rule_results.json` 的 R5 给出。连续下行判断是规则结果，具体金额是 Metrics 事实。
3. **展示广告的 CAC 率连续上升。** 2025-01 至 2025-03 从 1.600000 升至 1.684211，2025-04 至 2025-06 升至 1.777830，来源 `expected/channel_metrics.csv` 和 R36；这是 Rule Finding，数值本身是 Metrics 事实。
4. **搜索广告出现 CAC 率连续上升及多次单月跳升。** R36 在 2025-01 至 2025-03、2025-02 至 2025-04、2025-03 至 2025-05、2025-04 至 2025-06 命中；R37 在 2025-01→02、03→04、04→05、05→06 命中，来源 `expected/rule_results.json`。这是 Rule Finding，非人工 Derived Fact。

当前规则没有命中 R61；这不表示整体投放健康，只表示本 Demo 的 ROI<0.5 成本占比没有超过该规则阈值。R6、R8、R9 等规则也按当前输入和正式规则结果原样保留，未人为制造命中。

## How to run

从项目根目录执行：

```powershell
& '.venv\Scripts\python.exe' scripts\integration_plan.py --input demo\demo_business_data.xlsx
```

## Expected Output

成功后，运行产物位于 `outputs/runtime/`：`preflight.json`、`execution_plan.json`、`channel_metrics.csv`、`category_metrics.csv`、`rule_results.json`、`report_model.json`、`semantic_blocks.json`、`report.docx`、各项 QA JSON，以及 `task_state.json`（状态为 `DONE`）。本目录的 `expected/` 是本次干净运行复制出的黄金结果。

## Boundaries

当前报告编排器输出的是由事实和命中规则组成的紧凑可编辑报告模型；它不会展示尚未实现的竞品、市场份额、客户级复购或固定渠道类型映射。Demo 没有修改核心指标口径、规则阈值或 Demo 专属业务分支。
