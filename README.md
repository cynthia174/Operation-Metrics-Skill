# Operation Metrics Demo — S1-S4 现行规则

固定处理链路：Excel → 字段语义映射 → 指标计算层 → Rule Engine → CSV + JSON 结构化结果。

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
└── run_rules.py              # Rule Engine命令行入口
```

正式 JSON Schema 位于 `docs/rule_result.schema.json`。

## 运行

```powershell
$python = 'C:\Users\a\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $python src\aggregate_metrics.py `
  reference\兴趣岛五年渠道真实数据_分卷06_20250713-20251116.xlsx `
  outputs\engine\channel_month_metrics.csv `
  --category-output outputs\engine\category_month_metrics.csv `
  --sheet-name 数据源
& $python src\run_rules.py `
  outputs\engine\channel_month_metrics.csv `
  outputs\engine\rule_results.csv `
  --category-metrics outputs\engine\category_month_metrics.csv `
  --json-output outputs\engine\rule_results.json
```

输入文件名和全部输出路径均由参数提供；代码不依赖当前样例文件名。Excel页签默认是`数据源`，可通过`--sheet-name`修改。

## 字段语义映射

`FIELD_MAP`以标准业务字段为键，保存源Excel列名、字段类型和业务含义。指标层只引用`cost`、`channel`等标准字段，不直接引用中文Excel列名。以后列名变化时，只修改`src/field_mapping.py`中的`source`。

加载阶段会一次性读取映射声明的字段并校验缺列；维度空值、金额或数量无法转为数值时立即失败，不静默补零。

## Rule Result JSON协议

`rule_results.json`顶层包含：

- `schema_version`：当前固定为`1.0`。
- `result_count`、`hit_count`：结果总数和命中数。
- `results`：每次规则评价一条独立记录，包含规则身份、`hit`、维度、观察周期、指标快照、阈值和证据数组。

规则评价包含命中与未命中记录，LLM可直接筛选`hit=true`生成风险分析，也可用未命中记录说明当前检查正常。`metrics`是机器可读数值，`evidence`是可直接引用的事实文本；LLM不应重新计算阈值或比例。

唯一键为`rule_id + dimension.type + dimension.name + period.start + period.end`。导出前会拒绝重复键、NaN和inf；JSON使用严格模式，不允许非标准浮点值。

## LLM数据适配层

formatter读取Rule Engine的原始JSON，并生成按`模块 → 维度 → 周期`组织的Prompt上下文：

```powershell
& $python src\formatter.py `
  outputs\engine\rule_results.json `
  outputs\engine\llm_context.json
```

输入是符合现有`rule_result.schema.json`的`rule_results.json`。输出`llm_context.json`包含：

- `source`：原始Schema版本、结果数和命中数。
- `usage`：Prompt使用约束，明确禁止LLM重新计算指标。
- `rule_catalog`：将`rule_id`和原始`rule_name`组合为可读规则信息。
- `modules[].dimensions[].periods[]`：按模块、维度、周期组织的结果。
- `results[].fact`：未经改写的完整原始Rule Result记录。

formatter只增加展示和分组元数据，不修改`fact`中的`hit`、`metrics`、`threshold`或`evidence`。分组层的`result_count`和`hit_count`只用于上下文导航，不是新的业务指标。

输出使用紧凑JSON，减少直接注入Prompt时的无效空白字符；结构和事实字段保持完整。

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
