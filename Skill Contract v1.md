# Skill Contract v1

> 状态：架构与产品行为定义（基于当前仓库实现的审计）
>
> 本文定义 Skill 的输入、能力、交互、分析、证据、降级和输出边界。它不修改现有指标口径、规则阈值、报告五屏结构或 Word 样式。

## 0. Contract 总原则

Skill 不是“上传 Excel 后默认执行所有分析”，而是一个**能力受数据支持程度约束的、审批门控的证据链工作流**。

正式链路为：

`Raw Input → Preflight → Field Resolution → Capability / Rule Coverage → Plan → User Approval → Normalize → Aggregate → Metrics → Rules → Rule Result → Report → Fact QA → Semantic Blocks → DOCX → DOCX QA / OOXML QA`

只有适用阶段完成且验证通过，才能宣称整体成功。单个 CSV、Rule Result、报告或 DOCX 生成成功，不等于分析成功。

---

## 1. 现状审计：当前系统实际上如何工作

### 1.1 入口与工作流

- `SKILL.md` 将完整报告设为默认路径；只有用户明确要求某一步时才允许局部终点。
- 工作流状态是 `INIT → PREFLIGHT → AWAITING_PLAN_APPROVAL → AUTONOMOUS_EXECUTION → VALIDATING → DONE`。
- Preflight 后必须停在 `/plan`，等待用户批准；批准后运行时不应在中间阶段再次询问。
- `scripts/workflow_runner.py` 按依赖执行 stage、保存 state、校验输出、按策略重试，并在所有必需 stage 完成后检查 DoD。
- 当前 runner 的批准校验依赖 state 中的 `workflow_status == AUTONOMOUS_EXECUTION`；计划版本、批准版本和输入哈希的一致性并未在 runner 这一层完整表达。

### 1.2 输入、字段和 Preflight

- `src/preflight.py` 可读取 `.xlsx`、`.csv`；XLSX 在未指定 sheet 时遍历全部 sheet，CSV 使用单一虚拟 sheet。
- XLSX 下游默认仍是 `数据源`，`src/aggregate_metrics.py` 只按一个 sheet 读取；因此 Preflight 的多 Sheet 发现能力大于正式计算能力。
- `src/field_mapping.py` 当前标准字段包括统计日期、品类、三级渠道、线索、首单订单、成本、首单营收/正式营流水/净流水/退款流水、重复线索及 90 天重复线索。
- 当前代码的默认映射声明以固定中文源列为主；`preflight.py` 另外有 alias resolution，但正式聚合层仍依赖标准字段及既定映射。
- Preflight 记录行数、表头、数据类型、日期范围、映射状态和规则覆盖；缺列或不足完整月份会把规则标记为 blocked。
- 下游加载阶段对关键维度空值、金额/数量不能转数值采取显式失败，不静默补零。
- 完整月份按该月最小日期为 1 且最大日期为月末判断；部分月份仍可进入当前周期指标表，但不能满足跨月规则的完整期条件。

### 1.3 Metrics

- 原始数据先按 `month + channel` 或 `month + category` 聚合。
- 加法字段求和，比例在聚合后的分子、分母上重新计算；除零返回缺失/安全结果，不把未知当作零。
- 渠道指标包括成本、线索、首单订单、首单营收、净流水、CAC、CAC 率、转化率、ROI、重复线索率等。
- `first_order_users_proxy` 等于首单订单数，是代理字段，不是真实去重用户数。
- `repeat_lead_rate` 是重复线索率，不是复购率；`cac` 与正式规则使用的 `cac_rate` 不是同一指标。
- 品类指标只从首单营收生成品类营收和营收占比。

### 1.4 Rules / Rule Result

- 当前正式可执行规则是 S1：R3、R4、R5、R6、R8、R9；S2：R36、R37；S3：R61。
- R36/R37 使用 `cac_rate = cost / first_order_net_revenue`；R61 使用渠道 ROI 和成本；规则不应被报告层重新计算。
- 规则只对完整自然月运行；历史月份不足时某些规则不生成评价行，而不是生成“未命中”。
- Rule Result 同时可包含 `hit=true` 和 `hit=false` 记录；缺少依赖应是 `NOT_EXECUTABLE`/blocked 语义，而不是伪造 miss。
- `hit=false` 仅表示本次条件未触发，不表示整体健康、没有风险或检查通过。

### 1.5 Capability / Fact / Report / Word

- `src/capability_facts.py` 当前能力检测覆盖渠道/品类当前周期摘要、排序、成本、CAC、CAC 率、ROI、品类占比，以及“至少 2 个完整期的环比”和“至少 3 个完整期的趋势”这类通用时间条件。
- 当前事实抽取主要保留各实体最新月份的事实；它不是完整的历史事实导出器。
- `scripts/report_composer.py` 是一个通用事实块组合器：有规则结果时只加 hit 规则标题；无规则结果时保留当前周期事实并声明不生成趋势结论。
- `SKILL.md` 同时规定现行五屏报告：渠道全景、品类营收结构、获客成本信号、投放有效性、总结。两者的结构和能力入口尚未统一。
- Semantic Blocks 是内容与结构之间的中间合同；若作为上游输入，应保留文本、顺序和 semantic role。
- Word 生成器将 semantic blocks 渲染为可编辑文本/表格，并有独立 DOCX/OOXML/round-trip QA；Word 是交付载体，不是新的分析事实来源。

---

## 2. 当前已经隐含存在的 Contract

1. 输入必须可读，并能解析出日期、维度和所需 measure；缺关键字段显式失败。
2. 标准业务字段与源列解耦；指标层只消费 canonical field。
3. 指标由确定性计算产生；先聚合加法项，再计算率。
4. 完整自然月是跨期比较和规则评价的时间边界。
5. 规则只能使用既有规则、阈值、周期和含义。
6. Rule Result 保留 rule identity、hit、dimension、period、metrics、threshold、evidence。
7. 正式报告数字来自 validated raw data / deterministic metrics，正式判断来自官方 Rule Result。
8. 未命中规则不能写成“没有风险”；未检查不能写成“检查通过”。
9. 报告缺口必须披露；第五屏只能总结前四屏已有内容。
10. 完整工作流必须经过用户批准；中间 stage 完成不是整体完成。
11. Semantic Blocks 与 Word 生成分离；Word 保持可编辑并进行独立 QA。

## 3. 当前 Contract 不一致、未定义和危险模糊边界

### 3.1 不一致

- Preflight 支持多 Sheet 发现，但聚合默认只读 `数据源`；“发现了”不等于“会计算”。
- alias mapping 的能力与 `FIELD_MAP` 固定源列校验并存，自动映射的优先级、冲突处理和下游使用条件未统一。
- `field-contract` 说缺失字段显式失败；Preflight 又可以输出 blocked plan；两者没有明确“哪些缺失允许降级、哪些必须停止”。
- capability 状态实现只有 `AVAILABLE/UNAVAILABLE`，用户要求的 `SUPPORTED/PARTIALLY_SUPPORTED/UNAVAILABLE` 尚未形成正式枚举。
- capability facts 主要抽最新周期；报告规范要求趋势、集中度和规则诊断，历史事实与规则事实的消费边界未统一。
- `report_composer.py` 的通用块结构与 SKILL.md 的五屏结构存在分叉。
- Rule Result schema、运行时 state、report QA、semantic blocks、DOCX QA 各自校验，但缺少统一的 run-level success status 和 lineage contract。

### 3.2 未定义行为

- 多个 XLSX Sheet 是否合并、选择、逐 Sheet 分析，或要求用户指定。
- 空 Sheet、只有表头、全是空值、没有完整月份时的精确输出。
- 日期无法解析、混合日期格式、重复列名、重复记录、同一实体同月多行的处理边界。
- “字段存在但全为空”“字段可计算但样本过少”“分母为零”分别属于 unavailable、partial 还是 failed。
- 没有 Rule Result 时，报告是否消费 Metrics Facts；当前组合器有行为，但全局 Contract 没有明确原则。
- 没有任何 rule hit 时，关键发现、风险、建议关注事项的最小结构。
- 报告、Semantic Blocks 和 DOCX 生成失败时，是否仍交付已验证的 Metrics/Rule Result。
- 用户提供已有 metrics/rules/report 时，哪些可以作为可信上游，哪些必须重算或验证。
- 输入覆盖范围是否按自然日、完整月、实体维度分别报告。

### 3.3 最容易导致错误或幻觉的边界

- 把首单订单代理成用户，把重复线索率写成复购率。
- 把 CAC 与 CAC 率混用，或把首单营收与净流水混用。
- 用部分月份做跨月趋势、环比或连续下降判断。
- 把 `hit=false` 当成健康结论，把无评价行当成未命中。
- 从渠道/品类名称猜渠道类型、客户画像、原因或策略。
- 将“CAC 上升”扩写成“获客效率全面恶化”，但没有范围、分母、持续性或规则证据。
- 将 DOCX/QA 通过误写成经营分析正确；格式校验不能证明业务事实正确。

---

## 4. Skill Contract v1：Input Contract

### 4.1 合法输入

- 支持 `.xlsx` 和 `.csv`。
- XLSX 必须至少有一个可读取的工作表；CSV 视为单表输入。
- 输入必须能识别一个时间字段、至少一个业务维度（如渠道或品类）和至少一个可聚合 measure，具体源列名不限，必须通过映射解析到 semantic role。
- 每条记录应具有稳定的业务粒度说明：例如“日期 × 渠道 × 品类”或可被明确聚合的明细粒度。
- 文件、Sheet、输入版本/哈希和用户目标必须在 Preflight 中登记。

### 4.2 最低数据要求

- 最低可分析条件：可解析时间字段 + 至少一个维度 + 至少一个非空、可聚合 measure + 至少一条有效数据记录。
- 最低“当前周期事实”不要求完整月份；最低“趋势/环比/连续规则”要求相应数量的连续完整自然月。
- 时间字段至少应能归一到日或月；无法确定时间粒度或时间语义时必须请求补充信息/停止，不得猜测。
- measure 必须声明语义、单位和可加性。金额、数量、成本等 additive measure 可聚合；率、比例、单价不可直接求和，必须有合法分子分母或原生定义。

### 4.3 缺失字段、异常和空数据

- 缺少某能力的非关键字段：该能力标为 `UNAVAILABLE` 或 `PARTIALLY_SUPPORTED`，报告列入数据缺口，可继续其他能力。
- 缺少所有可分析所需的时间/维度/measure：`FAILED`，停止正式分析。
- 关键字段存在但全为空：等同该语义不可用，不得当作零。
- 关键维度为空、日期无法解析、measure 存在不可修复的类型异常：默认停止受影响的分析。若可明确隔离坏行且用户可接受排除，应先请求确认或在 plan 中声明排除范围。
- 空文件、空 Sheet、只有表头、有效记录为零：停止正式分析，输出输入失败原因，不生成业务结论。
- NaN、inf、除零结果不得进入正式 Rule Result 或报告数字。

### 4.4 多 Sheet

v1 默认采用“显式选择优先”：

1. 用户指定 Sheet：只分析指定 Sheet。
2. 未指定且只有一个非空 Sheet：自动选择。
3. 未指定且多个非空 Sheet：若 schema、字段语义和粒度一致，可在 Plan 中提出合并；否则请求用户选择或补充合并规则。
4. 不能把“Preflight 检查过全部 Sheet”表述成“全部 Sheet 已纳入计算”。

### 4.5 时间覆盖

必须分别记录：原始最早/最晚日期、有效月份、完整自然月列表、缺失月份/断档、当前周期和可用于跨期分析的周期。部分月份可支持描述性当前事实，但不可自动参与要求完整期的比较。

---

## 5. Capability Contract

能力由 semantic role、dimension、measure、time condition 和现有实现共同决定。能力状态只有以下三类：

- `SUPPORTED`：当前代码和输入条件都满足，可正式执行并输出事实。
- `PARTIALLY_SUPPORTED`：可以输出受限事实，但缺少完整历史、部分依赖或覆盖范围不足；必须披露边界。
- `UNAVAILABLE`：当前代码没有实现，或输入缺少必要语义；不得生成该能力结论。

### 5.1 v1 真实能力矩阵

| 能力 | 所需语义 | 时间要求 | v1 状态与边界 |
|---|---|---:|---|
| Channel revenue summary/rank | channel + first_order_revenue | 当前有效周期 | SUPPORTED；当前实现主要抽取最新周期事实 |
| Channel cost summary | channel + cost | 当前有效周期 | SUPPORTED |
| Channel CAC | channel + cost + first_order_orders | 当前有效周期 | SUPPORTED；订单数是首单订单代理，不是真实用户数 |
| Channel CAC rate | channel + cost + first_order_net_revenue | 当前有效周期 | SUPPORTED；不得与 CAC 混用 |
| Channel ROI | channel + cost + first_order_revenue | 当前有效周期 | SUPPORTED；分母为零时不可用 |
| Category revenue summary/rank/share | category + first_order_revenue | 当前有效周期 | SUPPORTED |
| Period-over-period change | 上述可比较 measure + time | 至少 2 个连续完整月 | PARTIALLY_SUPPORTED；现有 capability detector 有条件，但事实抽取/报告消费不覆盖完整历史 |
| Continuous trend | 上述可比较 measure + time | 至少 3 个连续完整月 | PARTIALLY_SUPPORTED；正式连续规则仅限现有 R5/R6/R36 等实现 |
| S1 category rules | category + first_order_revenue | 依 R3/R4/R5/R6/R8/R9 | SUPPORTED，规则范围固定 |
| S2 CAC-rate rules | channel + cost + first_order_net_revenue | 依 R36/R37 | SUPPORTED，规则范围固定 |
| S3 invalid-spend rule | channel + cost + first_order_revenue | 至少 1 个完整月 | SUPPORTED，仅 R61，不等于完整投放健康评估 |
| Customer analysis / retention / repurchase | customer_id + order_date + customer/order facts | 客户级连续记录 | UNAVAILABLE；现有重复线索字段不能替代 |
| Profit analysis | profit 或完整 revenue/cost/profit semantic role | 依定义 | UNAVAILABLE；当前没有利润指标/规则覆盖 |
| Market/competitor/share analysis | market/competitor/share fields | 依定义 | UNAVAILABLE |
| Fixed channel-type diagnosis | versioned channel classification mapping | 依映射 | UNAVAILABLE unless supplied mapping is explicitly validated |

“Revenue + Date → Trend”只有在连续完整期、定义一致且当前实现能产出可追溯历史事实时才可启用；不能仅凭字段存在启用。

---

## 6. Interaction Contract

### 自动继续

- 文件可读，字段映射唯一或高置信，最低数据条件满足。
- 缺少非关键能力字段，但至少有一项能力可执行；Plan 明确跳过项和影响。
- 存在部分月份，但当前周期事实仍可安全计算；跨期能力自动降级并披露。
- Rule 没有 hit，但 Metrics Facts 有效；继续生成事实型报告。

### 必须请求确认/映射/补充信息

- 多个非空 Sheet 无法证明同 schema/同粒度。
- 字段映射歧义、同一 semantic role 有多个候选、单位/币种/时间语义不明。
- 坏行可以隔离但排除会改变覆盖范围或结果。
- 用户目标要求的能力不在当前支持矩阵内，但存在可交付的替代事实；先说明可替代范围。
- 需要渠道分类表、ROI 红线、利润定义、客户 ID 或其他业务口径才能执行某项规则。

### 告知不可执行但可继续

对单个能力缺少依赖时，输出 `UNAVAILABLE`/`NOT_EXECUTABLE`、缺失 semantic role、受影响模块和替代可用能力；不能沉默跳过。

### 完全停止

- 文件不可读、没有有效数据、无法建立时间语义。
- 没有任何可聚合 measure 或任何稳定维度。
- 关键字段类型/维度错误无法隔离，或输入粒度会导致重复计算且没有明确规则。
- 必须审批的 Plan 尚未批准。
- 关键 stage、事实 QA、Rule Result schema、lineage 或最终交付校验失败，且无法安全降级。

---

## 7. Analysis Contract

### Metrics 层

Metrics 负责：字段归一、粒度声明、聚合、确定性派生指标、完整月份标记、单位/定义/来源。Metrics 不负责经营判断、原因解释或策略建议。

### Rules 层

Rules 只执行已实现规则及其既定阈值、周期和定义，输出官方 Rule Result。规则不得用报告层重新计算或改变口径。`hit=true` 是规则发现；`hit=false` 是条件未触发；无评价行或缺依赖是未检查/不可执行。

### Report 层

Report 消费 Metrics Facts、规则结果和数据覆盖信息，负责面向业务表达、边界披露和优先关注事项。Report 不产生新的指标，不将格式 QA 当成业务 QA，不从名称推断原因。

### 没有 Rule Result 时的明确原则

**没有 Rule Result 不得阻止已验证 Metrics Facts 的事实型报告；但报告必须降级为 Metrics-only，不能生成规则发现、风险确认、健康判断、趋势判断或原因解释。**

如果存在有效的跨期 Metrics Facts，仍可报告确定性计算出的变化；如果当前实现只能提供最新周期事实，则只报告最新周期事实，并写明趋势不可执行。报告必须有“规则覆盖/不可执行项”段落。

---

## 8. Evidence Contract

| 类型 | 允许证据 | 允许表达 | 禁止扩张 |
|---|---|---|---|
| `DIRECT FACT` | 原始字段、有效行、Metrics 快照 | “某期间某维度的成本为 X” | 不补算、不改单位、不改语义 |
| `DERIVED FACT` | 确定性公式、聚合分子/分母、完整周期 | “按定义计算的 CAC/ROI/占比为 X” | 不把代理升级为真实用户/利润 |
| `RULE FINDING` | 官方 Rule Result，尤其 `hit=true`、阈值、周期、evidence | “R36 在某渠道/期间命中” | `hit=false` 不写成健康；未检查不写成通过 |
| `INTERPRETATION` | 直接事实/派生事实/规则发现的明确范围 | “该范围内显示成本上升信号” | 不扩成全面恶化、原因或因果关系 |
| `RECOMMENDATION` | 已确认发现 + 明确边界 + 可核查对象 | “优先核查某渠道的成本与净流水口径” | 不输出无证据的泛化策略 |

每个结论至少绑定：`source/run_id`、semantic role、dimension/entity、period、definition/unit、evidence_ref；规则结论还必须绑定 `rule_id` 和 `hit`。

---

## 9. Degradation Contract

| 数据/条件 | 继续交付 | 必须跳过/禁止表达 |
|---|---|---|
| 无 cost | revenue、订单等事实仍可用 | CAC、CAC rate、ROI、成本效率、投放有效性 |
| 无 profit | 营收/成本事实（若各自存在） | 利润、利润率、盈利能力、利润贡献 |
| 仅一个完整月份 | 当前周期摘要、排名、份额 | 环比、连续趋势、持续上升/下降规则 |
| 月份不连续或有部分月 | 分段/当前周期事实 | 把断档跨越当作连续月份 |
| 无 Rule Trigger | Metrics-only 报告、规则覆盖表 | 已确认风险、规则诊断结论、整体健康结论 |
| 缺 channel | 品类能力（若满足） | 渠道结构、渠道效率、R36/R37/R61 |
| 缺 category | 渠道能力（若满足） | 品类结构、R3–R9 |
| 缺 customer_id/order history | 渠道/品类事实（若满足） | 客户画像、复购、留存、LTV、沉默用户 |
| 缺 channel classification mapping | 渠道原始维度事实 | 外部/内部/转介绍等类型判断 |
| 规则依赖缺失 | 记录 `NOT_EXECUTABLE` | 用 `hit=false` 代替未检查 |

降级后的报告状态不是失败，只要仍有可验证的交付内容；降级范围必须进入输出。

---

## 10. Output Contract

最终交付至少包含：

1. 分析范围：文件/Sheet、时间范围、完整月份、纳入的维度与粒度。
2. 数据覆盖：有效记录、字段映射、缺失/异常、部分月份和断档。
3. 核心事实：Metrics Facts 及其定义、单位、周期和来源。
4. 关键发现：仅限直接事实、派生事实和 `hit=true` Rule Findings 支持的范围。
5. 无法分析的部分：能力状态、缺失依赖、`NOT_EXECUTABLE`、未覆盖规则。
6. 建议关注事项：只针对已确认事实/发现，使用“核查/关注”而不是无证据的确定性策略。
7. Evidence / lineage：至少在内部 artifact 中可追溯；面向用户的报告应提供可理解的证据引用。
8. 若交付 DOCX：Semantic Blocks、DOCX QA、OOXML QA 和可编辑性状态分开标记。

### 状态定义

- `SUCCESS`：最低目标能力全部满足；适用的 Metrics、Rules、Report 和要求的交付 QA 均通过；无未披露的关键缺口。
- `PARTIAL_SUCCESS`：至少有一项可验证分析结果和正式交付物，但部分请求能力、规则、时间覆盖或 QA 不可用；缺口、降级和未执行项已明确列出。
- `FAILED`：没有任何合法可分析结果，或关键前置条件/审批/事实校验/lineage 失败，不能安全交付经营分析结论。可以交付诊断信息，但不能称为分析报告。

状态按用户请求的目标能力评估，不按“是否生成了某个文件”评估。

---

## 11. Gap Analysis：CURRENT → TARGET → GAP → RECOMMENDED CHANGE

| 优先级 | CURRENT | TARGET | GAP | RECOMMENDED CHANGE |
|---|---|---|---|---|
| P0 正确性 | 缺失字段、空值、不可执行规则在不同层有不同处理 | 统一 critical / degradable / unavailable / failed 分类 | 没有单一决策表和 run-level 状态 | 增加 Contract decision model；Preflight、metrics、rules、report 共用 |
| P0 正确性 | 规则无结果、无评价、未命中语义容易混淆 | `HIT / NOT_HIT / NOT_EXECUTABLE / NOT_EVALUATED` 明确区分 | 现有 schema/报告未统一呈现 | 扩展 Rule Result/coverage contract，禁止伪造 miss |
| P0 正确性 | lineage 分散在 manifest、fact QA、report QA、DOCX QA | 每个结论、指标和交付物可追溯到 run/input/字段/周期 | 缺统一 lineage schema 和最终状态聚合 | 增加 run-level artifact lineage validator |
| P1 泛化性 | alias/固定映射、多 Sheet、下游单 Sheet 行为不一致 | semantic role 映射后可明确选择/合并 Sheet | Preflight 泛化能力超出计算层 | 统一输入适配器、Sheet policy 和 mapping resolution |
| P1 泛化性 | capability detector 与实际历史事实/报告消费不一致 | 能力状态反映“可计算且可交付” | `AVAILABLE` 过于乐观，facts 只取最新周期 | capability evaluator 增加 output coverage/time-history 条件 |
| P1 泛化性 | 报告存在通用 composer 与五屏规范两套入口 | 一个 canonical report contract | 结构路由不唯一 | 选定一个报告编排入口，其他仅作为适配层 |
| P2 体验 | 缺口能被记录但用户看到的交付状态不统一 | 明确告诉用户继续了什么、跳过什么、为什么 | 缺少标准缺口摘要和状态文案 | 增加 output summary / capability matrix / degradation summary |
| P2 体验 | 多 Sheet、歧义映射、坏行处理的询问时机不清晰 | 只在影响结果的选择上询问 | 交互规则未固化 | 将 Interaction Contract 写入 workflow prompt 和 plan schema |
| P3 未来增强 | 客户、利润、市场、渠道分类等未实现 | 新能力有独立依赖和证据边界 | 容易被误写进报告 | 以 capability registry 方式预留，但 v1 保持 unavailable |

---

## 12. 当前最危险的 5 个 Contract 缺口

1. **缺失/不可执行/未命中没有全链路统一语义**：最容易把“未检查”写成“正常”。
2. **多 Sheet 发现与正式计算范围不一致**：最容易漏算或让用户误以为所有 Sheet 已纳入。
3. **能力状态不能代表实际可交付历史事实**：检测到时间能力不等于报告层有完整历史证据。
4. **Metrics-only、Rules-only、完整报告的成功状态没有统一聚合**：容易从中间文件生成成功误判整体成功。
5. **代理指标与业务语义边界容易被报告语言突破**：首单订单→用户、重复线索→复购、CAC→全面效率恶化是最高风险幻觉路径。

## 13. 建议下一步修改的代码模块

按顺序建议：

1. `src/preflight.py`、`src/field_mapping.py`：实现统一 mapping result、Sheet policy、字段严重级别和异常分类。
2. `src/capability_facts.py`：把能力状态改为 `SUPPORTED/PARTIALLY_SUPPORTED/UNAVAILABLE`，并区分输入支持与输出覆盖。
3. `src/metrics/common.py`、`src/metrics/channel.py`、`src/metrics/category.py`：补充 metric metadata、coverage、period lineage 和不可计算原因。
4. `src/rule_result.py`、`src/rules/*`：明确 no-evaluation / not-executable / not-hit 的协议和覆盖摘要。
5. `scripts/report_composer.py` 及报告入口：统一 Metrics Facts、Rule Findings、data gaps 和五屏结构的消费规则。
6. `scripts/workflow_runner.py`、`scripts/validate_stage.py`：增加 plan/version/input hash/lineage 一致性和最终 `SUCCESS/PARTIAL_SUCCESS/FAILED` 聚合。
7. Semantic Blocks/DOCX QA 模块：只补充状态和 lineage 传递，不让渲染层产生事实。

## 14. 现在不要做

- 不要把客户分析、复购、留存、LTV、利润、竞品、市场份额、渠道类型诊断写成 v1 已支持。
- 不要为了“泛化”设计通用 ETL、自动语义猜测平台或无限字段推理。
- 不要重写现有规则阈值、指标口径、五屏结构或 Word 字体规范。
- 不要把所有 Sheet 自动拼接，不要把未知字段/坏值静默补零。
- 不要因为没有 Rule hit 就生成健康结论，也不要为了填满报告而制造原因和建议。
- 不要先做大规模前端、模板或视觉重构；先固化输入、能力、状态和证据协议。

## 15. 可直接转写进 SKILL.md 的 Contract

以下内容可直接作为 Skill 的硬性行为规则：

> Skill 根据输入实际具备的 semantic role、business dimension、measure 和 time dimension，确定可启用能力；不因上传了 Excel 就默认执行全部分析。
>
> 缺少某能力的依赖时，将该能力标记为 `UNAVAILABLE` 或 `PARTIALLY_SUPPORTED`，说明缺失字段和影响；不把缺失当作零，不把不可执行当作未命中。
>
> Metrics Facts 与 Rule Results 是不同证据层。Metrics 负责确定性事实，Rules 负责既有规则评价，Report 只能消费已验证事实和官方 Rule Result。
>
> 没有 Rule Result 时，若 Metrics Facts 有效，仍生成 Metrics-only 事实报告；但不得生成规则发现、风险确认、健康判断或未经证据支持的原因解释。
>
> `hit=false` 只表示规则条件未触发；未检查、缺少依赖或没有评价记录不得写成“没有风险”或“检查通过”。
>
> 每个结论必须区分 `DIRECT FACT`、`DERIVED FACT`、`RULE FINDING`、`INTERPRETATION` 和 `RECOMMENDATION`，并保留 source、dimension、period、definition、evidence_ref；证据不足时使用“数据不足/待确认”。
>
> 部分月份只能支持受限的当前周期事实；环比、连续趋势和跨月规则必须使用满足规则要求的连续完整自然月。
>
> 最终状态为 `SUCCESS`、`PARTIAL_SUCCESS` 或 `FAILED`。生成了中间文件不等于成功；只有适用阶段、验证、缺口披露和 lineage 满足要求时才可宣称成功。

