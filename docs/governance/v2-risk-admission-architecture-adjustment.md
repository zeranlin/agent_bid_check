# V2 风险准入层架构调整方案

## 0. 实施状态

本方案对应的实施链路已经完成首轮收官，当前不再是“待实施方案”，而是“已完成架构落地并经过真实文件回放验证的治理文档”。

已完成的实施与验收链路包括：

1. `Task-AR3`
- 已完成真实回放根因闭环单源、回放索引与最小样例建设

2. `Task-RA1 ~ Task-RA3`
- 已完成 `risk_admission` 骨架接入、模板/边界证据硬门禁、提醒项/证据不足项降级与真实回放门禁

3. `Task-Q1 ~ Task-Q7`
- 已完成 formal 准入门禁、主风险吸收与去重、formal 池收紧、registry 单源联动、主源收口、supplemental 压缩与最终 runtime supplemental 关闭

当前架构结论：

- `compare` 负责候选发现，不负责最终层级裁决
- `output_governance` 负责标准化、归并、吸收留痕，不负责最终层级裁决
- `risk_admission` 是唯一三分层出口
- `rules/registry/` 已成为 formal 主源
- `rules/registry/governance-formal/` 承接治理型主源条目
- runtime supplemental 已关闭，`whitelist` 不再作为长期主源资格证明

Q 线收官后，本方案进入“稳定运行 + 持续反馈治理”阶段。

## 1. 背景

近期基于真实文件的持续复核表明，当前系统暴露出的核心问题，已经不再只是“某条规则没识别到”，而是“专题发现结果会直接冲进正式风险输出”。

典型表现包括：

1. 模板、声明函、联合体协议、分包协议等非正文证据被误当成正式风险依据
2. 证据不足、提醒项、边界项被抬升为 `formal_risks`
3. 专题层自由发挥文案缺少正式规则支撑，却仍进入最终输出
4. 客户反馈后的误报整改只能靠补 prompt 或补单条规则，缺少稳定治理抓手

这说明在现有 V2 中，虽然已经有：

- 文档解析与结构召回
- 专题识别与候选风险发现
- compare / output governance / final output

但还缺少一个真正独立的“正式风险准入层”，去回答：

`发现了风险候选，不等于可以作为正式风险输出。`

## 2. 结论

从架构层面看，`需要调整`。

但不建议推翻 V2，也不建议直接起 V3，而应采用：

`在 V2 中新增独立的 risk_admission 风险准入层`

对外口径可表述为：

`V2 在保持识别主链路不变的前提下，补齐正式风险准入中枢，进入“识别 + 准入”双层治理阶段。`

## 3. 本次要解决的问题

### 3.1 专题发现与正式输出没有硬边界

当前更接近：

- topic / compare 发现了什么
- 最终就输出什么

这会导致：

- 专题自由发挥标题直接进入 `formal_risks`
- 纯提醒项、证据不足项进入正式报告
- 模板类文本被混作正文风险

### 3.2 证据类型没有进入正式裁决

系统虽然能召回证据，但尚未把以下类型作为正式准入判断条件：

- 正文条款
- 声明函模板
- 联合体协议模板
- 分包协议模板
- 合同留空模板
- 可选附件说明

于是“有证据”被误理解成“可作为正式风险证据”。

### 3.3 正式风险最小准入条件不清晰

当前系统对“正式风险”的最低门槛缺少统一定义。

至少应明确：

- 是否有稳定证据
- 是否属于正文或有效业务承诺
- 是否有正式规则或明确治理口径支撑
- 是否只是提醒项 / 完整性提示 / 证据缺口提示

### 3.4 客户反馈闭环没有稳定挂点

目前误报整改大多只能补：

- 某条规则
- 某个专题 prompt
- 某个样本

但如果没有统一准入层，后续同类问题还会从别的专题、别的标题再次回流。

## 4. 调整目标

本次架构调整有 5 个核心目标：

1. 把“风险发现”和“正式输出”彻底拆层
2. 让证据类型成为正式风险准入判断条件
3. 让 `formal_risks / pending_review_items / excluded_risks` 的裁决统一由准入层完成
4. 让模板、协议、提醒项、证据不足项无法绕过准入层直接输出
5. 让客户反馈整改有统一治理挂点，而不是只能零散补规则

## 5. 调整后的目标架构

建议将 V2 主链路收敛为以下 6 层：

```text
第1层：文档解析与结构切分层
第2层：证据召回与专题发现层
第3层：compare / 候选风险聚合层
第4层：risk_admission 风险准入层
第5层：最终结果装配层
第6层：Web / 报告 / 历史展示层
```

其中真正新增且最关键的是：

`第4层：risk_admission 风险准入层`

## 6. risk_admission 的职责

风险准入层不负责重新识别风险，而只负责判断：

`哪些候选风险能进正式风险，哪些要降级，哪些要排除。`

### 6.1 输入

输入对象包括：

- compare clusters
- topic risk points
- 已命中的正式规则信息
- evidence metadata
- 输出治理前的候选标题与文案

### 6.2 输出

输出必须是唯一三分层结果：

- `formal_risks`
- `pending_review_items`
- `excluded_risks`

并附带：

- 准入原因
- 降级原因
- 排除原因
- 命中的边界规则或拦截规则

### 6.3 必须承担的判断职责

1. 证据类型判定
2. 风险来源判定
3. 正式风险准入判定
4. 提醒项 / 证据不足项降级
5. 模板 / 协议 / 声明函排除
6. 准入理由留痕

## 7. 证据类型模型

建议在 risk_admission 中引入统一的 `evidence_kind`：

- `body_clause`
- `scoring_clause`
- `qualification_clause`
- `acceptance_clause`
- `contract_template`
- `declaration_template`
- `joint_venture_template`
- `subcontract_template`
- `attachment_instruction`
- `optional_form`
- `unknown`

用途：

- `body_clause / scoring_clause / qualification_clause / acceptance_clause` 可参与正式风险准入
- `contract_template / declaration_template / joint_venture_template / subcontract_template / optional_form` 默认不得直接作为正式风险主证据
- `attachment_instruction / unknown` 默认需更高门槛才能进正式风险

## 8. 风险来源模型

建议在 risk_admission 中统一标记 `admission_source_type`：

- `formal_rule`
- `candidate_rule`
- `compare_rule`
- `topic_inference`
- `completeness_hint`
- `warning_only`

准入优先级建议：

1. `formal_rule`
2. `candidate_rule`
3. `compare_rule`
4. `topic_inference`
5. `completeness_hint`
6. `warning_only`

原则：

- `topic_inference` 不得默认直接进入正式风险
- `completeness_hint / warning_only` 默认不能进入正式风险

## 9. 正式风险最小准入条件

建议将以下条件定义为正式风险最小准入门槛：

1. 存在可定位的有效证据
2. 证据类型不是模板/声明函/协议类排除对象
3. 有正式规则、治理规则或明确稳定口径支撑
4. 不是纯“未看到 / 需确认 / 需警惕 / 建议核实”型结论
5. 风险标题与文案能够稳定复现，不依赖专题自由发挥

若不满足，则只能：

- 转 `pending_review_items`
- 或进入 `excluded_risks`

## 10. 五条硬规则

### 10.1 模板文本默认不得直接进入正式风险

包括但不限于：

- 联合体协议
- 分包协议
- 声明函模板
- 留空合同模板

### 10.2 纯专题推断不得直接进入正式风险

若一个候选仅来自专题自由推断，且没有正式规则或稳定 compare 依据，则不得直接进入 `formal_risks`。

### 10.3 证据不足类标题默认进待补证

例如：

- 关键条款缺失，需人工复核
- 节能环保政策适用性需进一步核实
- 证据片段未覆盖，需补证

### 10.4 提醒项不得直接进正式风险

例如：

- 需警惕
- 需确认
- 建议评估
- 可能需进一步核实

### 10.5 正式风险必须能解释“为何准入”

每个 `formal_risks` 条目都必须可回写：

- 为什么能进正式风险
- 依据哪类规则 / 哪类边界
- 哪些证据支撑它不是模板或提醒项

## 11. 针对福建文件暴露问题的架构收益

以本次福建文件为例：

- `评分标准中设置特定品牌倾向性条款`
  - 可保留正式风险
- `商务条款中关于“无犯罪证明”的提交时限及无效投标处理存在法律风险`
  - 可保留正式风险
- `验收标准模糊且依赖后续合同确定，存在需求条款合规风险`
  - 应被 risk_admission 拦截或降级
  - 因为关键证据之一来自 `subcontract_template`
- `专门面向中小企业采购的评审细节需确认`
  - 应进入 `pending_review_items`
- `人员证书评分项设置需警惕变相指定特定资质或人员`
  - 更适合作为 `pending_review_items`

也就是说，risk_admission 的价值不是“再发现风险”，而是：

`把正式输出变得可信。`

## 12. 模块与目录建议

建议新增独立目录：

```text
app/pipelines/v2/risk_admission/
  schemas.py
  evidence_classifier.py
  source_classifier.py
  rules.py
  decision_engine.py
  pipeline.py
```

职责建议：

- `schemas.py`
  - 准入层输入输出对象
- `evidence_classifier.py`
  - 证据类型判定
- `source_classifier.py`
  - 风险来源分类
- `rules.py`
  - 硬准入规则、降级规则、排除规则
- `decision_engine.py`
  - 准入决策器
- `pipeline.py`
  - 与现有 output governance / assembler 串联

## 13. 测试与样本建议

必须新增以下样本族：

1. 模板误报样本
2. 联合体/分包协议误报样本
3. 声明函误报样本
4. 纯提醒项降级样本
5. 证据不足降级样本
6. 正文硬风险保留样本

至少新增以下测试：

1. `risk_admission` 单元测试
2. 福建文件真实回放测试
3. 模板类条目不得进正式风险测试
4. 证据不足类条目只能进待补证测试
5. 正式规则命中项不被误伤测试

## 14. 实施建议

以下任务已全部完成并通过验收：

1. `Task-RA1`
- 风险准入层骨架搭建

2. `Task-RA2`
- 模板/协议/声明函边界识别与硬排除

3. `Task-RA3`
- 提醒项 / 证据不足项降级机制与真实文件回放门禁

4. `Task-Q1`
- formal 准入首轮门禁落地

5. `Task-Q2`
- 主风险吸收与附属项去重门禁落地

6. `Task-Q3`
- 正式风险池收紧为“稳定家族 + 正文硬证据”双门禁

7. `Task-Q4`
- formal 准入与规则注册表联动

8. `Task-Q5`
- formal 主源继续向 `rules/registry` 收口

9. `Task-Q6`
- governance-formal 主源迁入 `rules/registry/governance-formal/`

10. `Task-Q7`
- 剩余 supplemental 过渡项终局处理，runtime supplemental 正式关闭

本节保留原始实施拆分逻辑，主要用于回溯实施顺序：

1. `Task-RA1`
- 风险准入层骨架搭建

2. `Task-RA2`
- 模板/协议/声明函边界识别与硬排除

3. `Task-RA3`
- 提醒项 / 证据不足项降级机制与真实文件回放门禁

## 15. 管理建议

后续所有客户反馈都建议统一映射到以下三类：

1. `规则缺失`
2. `证据边界错误`
3. `风险准入错误`

其中：

- 规则缺失，交给规则治理
- 证据边界错误，交给 evidence / structure 治理
- 风险准入错误，统一交给 risk_admission 治理

这样后续不会再把所有问题都混成“补规则”。

## 16. 结论

本次建议不是推翻 V2，也不是直接升级 V3。

建议路线是：

`继续保留 V2 主识别能力 + 新增独立 risk_admission 风险准入层`

这是当前阶段最有性价比、也最能直接提升“正式风险可信度”的架构调整方向。

## 17. 收官结果

截至 `Task-Q7` 验收完成，V2 风险准入治理线已经完成本轮主目标，可以按“架构收口线已完成”口径收官。

本轮收官结果包括：

1. `compare` 已去裁决化
2. `output_governance` 已去最终分层裁决化
3. `risk_admission` 已成为唯一正式风险出口
4. formal 准入已从代码白名单推进到 registry 主源
5. governance-formal 条目已进入 `rules/registry/governance-formal/`
6. runtime supplemental 已关闭
7. `whitelist` 仅保留历史保护作用，不再作为长期 formal 主源资格
8. 柴油 / 福州 / 福建 replay 已覆盖关键收口点

因此，后续工作重心不再是继续开新的 Q 线，而是：

1. 继续按真实文件与客户反馈推进 `R / W / G` 线任务
2. 对 `prepare_standalone_rule_task` 类型条目按业务价值再决定是否单独立项
3. 持续维护规则注册表、回放门禁和台账一致性
