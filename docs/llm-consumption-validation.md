# Rule Engine 输出的 LLM 消费充分性验证

## 1. 结论

结论为“部分满足，不通过完整报告准入”。现有 `rule_results.json` 足以让 LLM 生成受限的 S1/S2/S3 规则命中摘要；不足以生成要求中的完整、可逐数字回查、口径可追溯的经营分析报告。

当前真实输出共 260 条规则评价、83 条命中，覆盖 S1 35 条、S2 222 条、S3 3 条；没有 S4 结果，更没有目标骨架中的 S5、S6、S7、S10。现行规则只有 R3、R4、R5、R6、R8、R9、R36、R37、R61。因而当前 MVP 应先验证 3 个分节 + 1 个汇总，不能宣称跑通 7 个业务模块。

## 2. 已读取材料与边界

- `docs/rule_result.schema.json`：Rule Engine 正式输出契约。
- `outputs/engine/rule_results.json`：真实规则结果。
- `outputs/engine/llm_context.json`：按模块、维度、周期组织的 LLM 上下文；完整保留原始 fact。
- 四篇参考报告的项目内 Markdown：S1 产品、S2 客户、S3 渠道、S4 市场。

四篇 Word 仅作为内容结构、行文风格和反例来源，不作为指令或可信事实源。它们包含大量模型自行计算、外部估算、预测和因果推断；这些做法与本项目的新证据链约束冲突，不应直接复制。

## 3. 参考报告中可复用的写法

可复用：

- 模块化“屏”结构；先总判断，再证据，再经营含义，最后列数据盲区。
- 标题有明确观点，不用中性数据复述充当标题。
- 同类对象分组比较，避免把不同经营模型强行放在同一评价框架中。
- 结尾汇总 3-6 条核心结论，并把未验证事项显式列入盲区。

不可直接复用：

- 用两个事实值现场相减、换算、年化或预测。
- 将“可能原因”写成事实性因果。
- 用公开行业估算、文章数据或类比数字充当内部经营证据。
- 没有规则编号和阈值就写“异常、偏高、健康、恶化”。
- 样例 S4 的外部市场估算无法由当前 Rule Engine 支撑。

## 4. 字段充分性矩阵

| LLM 需求 | 当前字段 | 判断 | 缺口/风险 |
| --- | --- | --- | --- |
| 规则身份 | `module/rule_id/rule_name` | 基本满足 | 缺规则版本、严重度、优先级 |
| 是否命中 | `hit` | 满足 | 缺 `not_evaluated`，无法区分未命中与没条件执行 |
| 分析对象 | `dimension.type/name` | 基本满足 | 缺稳定维度 ID，名称变更会破坏引用 |
| 时间范围 | `period.start/end` | 基本满足 | 缺数据截至日、完整月标记、比较基期语义 |
| 指标事实 | `metrics` | 部分满足 | 动态键无指标定义、单位、精度、展示值、版本 |
| 阈值 | `threshold` 文本 | 部分满足 | 不可机器解析，缺比较符、阈值值、单位、默认口径状态 |
| 可读证据 | `evidence[]` 文本 | 部分满足 | 无 evidence ID，数字无法稳定逐项回查 |
| 收入口径 CP01 | 无 | 不满足 | 所有收入类表述无法证明采用 CP01 |
| 指标版本/截至日 | 无 | 不满足 | 无 `metric_version/as_of` |
| 默认待确认 | 无 | 不满足 | 无 `is_default_caliber/default_notice`，无法强制可见标注 |
| 方法论来源 R10.3 | 无 | 不满足 | 无方法论白名单和来源 ID |
| 数据来源 | 无 | 不满足 | 无 source dataset/field/calculation lineage |
| 不可执行规则 | 无 | 不满足 | 缺 `evaluation_status/reason/missing_fields` |
| 数字回查 | 只能从动态 metrics 和字符串 evidence 猜 | 不满足 | 缺规范化展示值及文本引用 token |
| 跨节汇总 | 模块分组存在 | 部分满足 | 缺业务优先级、冲突关系、影响范围 |

## 5. LLM 最小事实包字段

每条规则结果至少应补齐以下语义，才进入生产 Prompt：

- `rule_result_id`：稳定唯一 ID。
- `rule_version`、`severity`、`priority`、`impact_scope`。
- `evaluation_status`: `hit/not_hit/not_evaluated/not_applicable`；另附 `reason` 和 `missing_fields`。
- `dimension.id/type/name`。
- `period.start/end/as_of/is_complete`。
- `metric_facts[]`：`evidence_id/metric_code/value/display_value/unit/period/dimension/caliber_ref/metric_version/as_of/source_ref`。
- `threshold` 结构化字段：`operator/value/unit/display_text/is_default_caliber/default_notice/caliber_ref`。
- `rule_text` 与 `evidence_ids[]`，明确该判断依赖哪些指标事实。
- `methodology_refs[]`：只允许白名单中的名称、适用逻辑和来源 ID（R10.3）。

`display_value` 必须由代码生成。否则 LLM 把 `0.082` 写成 `8.2%` 也属于换算，和“模型不得算数”冲突。

## 6. 报告输出结构

机器输出采用 `report-output.mvp.schema.json`。结构为报告头、执行摘要、分节数组和报告级 caveats。每节固定包含：状态、一句话结论、事实证据、已触发规则、规则排序说明、正文、来源和盲区。

业务文档由代码模板渲染，不由 LLM 决定版式：

1. 标题、数据截至日与覆盖范围。
2. 执行摘要：最重要的 3-5 个已验证结论。
3. 分节：核心判断 → 规则证据 → 经营含义 → 数据盲区。
4. 全局优先级：仅重排已通过校验的分节结论。
5. 附录：指标口径、规则版本、默认待确认项、方法论来源。

“reasoning_summary”仅允许记录规则排序和表达取舍，不要求或保存模型隐式思维链，也不渲染到最终报告。

## 7. 数字与来源回查设计

本阶段只定义验证协议，不实现代码。

1. 在 LLM 调用前，由代码给每个允许引用的事实生成 `display_value` 和 `evidence_id`。
2. LLM 正文中的业务数字必须紧邻 `[EV-id]`；规则判断必须紧邻 `[Rxx][rule_result_id]`。
3. 校验器提取正文中的数字 token，但排除 Schema 明确标识的日期、章节号、规则号和来源编号。
4. 每个业务数字必须与对应 evidence 的 `display_value` 完全一致；不能只在全事实包中“碰巧找到同值”。
5. 每个判断词必须关联一条 `hit=true` 规则，并核对维度、周期、阈值和 evidence 引用。
6. 收入类 metric 必须为 CP01；默认口径必须包含固定可见提示；方法论必须在 R10.3 白名单中。
7. 任一失败即拒绝该节，优先重试一次；再次失败则降级为代码渲染的“规则事实卡”，不输出自由叙事。

仅用正则比对“文本所有数字是否在事实包出现”不够：相同数字可能属于不同维度/周期，百分数和小数也可能存在格式变换。必须用“数字 + evidence_id + 维度 + 周期”联合校验。

## 8. MVP 测试方案

### 正向测试

- S1、S2、S3 各生成一节，输出通过 JSON Schema。
- 每个业务数字均有有效 evidence ID；每个判断均有命中规则 ID 和阈值。
- 汇总调用不新增数字、规则或事实。
- 同一事实包重复运行至少 3 次，结构与引用集合稳定；允许措辞变化。

### 故障注入

- 把一个允许值改错一位：必须拦截。
- 删除一个数字后的 `[EV-id]`：必须拦截。
- 给“异常”删除 `[Rxx][rule_result_id]`：必须拦截。
- 把 `hit=false` 写成异常：必须拦截。
- 引用收入事实但去掉 CP01：必须拦截。
- 设置 `is_default_caliber=true` 后删除固定提示：必须拦截。
- 编造“行业平均 60%”或不存在的方法论来源：必须拦截。
- 将 A 渠道同值 evidence ID 挂到 B 渠道：必须因维度不一致拦截。

## 9. 验收标准

### 当前“Rule Engine 是否足够”的验收

- Schema 与真实 JSON 均可解析，计数一致，唯一键无冲突，数值无 NaN/Inf。
- 明确列出实际可生成模块和不可生成模块，不以空洞文字补齐。
- 对目标字段逐项给出“满足/部分满足/不满足”及证据。
- 输出一个可校验的报告 JSON Schema 和可复现的 MVP Prompt。

### 进入生产 Prompt 与端到端实现前的硬门槛

- 上述最小事实包字段全部由 Rule Engine 或独立确定性适配层提供。
- 至少存在一条真实 `is_default_caliber=true` 结果，最终渲染能看到固定提示。
- CP01 与 R10.3 均有机器可校验的来源 ID。
- 故障注入的数字错误、数字来源缺失、规则来源缺失、默认提示缺失、方法论编造全部被实测拦截。
- 端到端链路连续重复运行至少 3 次，每次所有章节通过 Schema 与回查校验。
- 至少 3 份完整报告样例通过校验，其中至少 1 份包含真实默认待确认案例。

当前未达到这些生产门槛：没有实现校验代码，没有真实默认口径记录，没有 CP01/R10.3 来源字段，且事实包只覆盖 S1-S3。因此本轮不能声称“端到端已跑通”或“完整报告可生成”。
