# Operation Metrics Demo — S1-S4 现行规则

固定处理链路：当前兴趣岛 Excel 真实样例 → 月×品类与月×三级渠道指标表 → S1-S4 中可真实计算的现行规则 → 命中结果。

## 运行

```powershell
$python = 'C:\Users\a\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $python src\aggregate_metrics.py `
  reference\兴趣岛五年渠道真实数据_分卷06_20250713-20251116.xlsx `
  outputs\current\channel_month_metrics.csv `
  --category-output outputs\current\category_month_metrics.csv
& $python src\run_rules.py `
  outputs\current\channel_month_metrics.csv `
  outputs\current\rule_results.csv `
  --category-metrics outputs\current\category_month_metrics.csv
```

## 现行计算口径

- `channel` 固定取 `三级渠道`；`渠道名称`视为更细的投放计划，不参与主键。
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
