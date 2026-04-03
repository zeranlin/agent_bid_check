# V2 风险召回与分层深审 Backlog

## 1. 文档定位

本清单用于把《V2 风险召回与分层深审系统方案》拆解为可开发、可排期、可验收的任务。

目标不是单纯完成四层链路，而是围绕：

- 尽量精准找到所有风险点
- 降低关键高风险漏检
- 提升跨章节与细节风险召回能力
- 用埋点文件建立稳定回归闭环

来组织开发顺序。

## 2. Backlog 总体原则

### 2.1 排序原则

1. 先补“漏检能力”，后补“展示美化”
2. 先补“第二层召回完整性”，后补“第三层专题扩展”
3. 先建立“回归验证”，后做持续 prompt 微调
4. 不破坏当前 V1
5. V2 任一阶段都应保持可运行

### 2.2 验收原则

每个任务必须有：

- 明确输入
- 明确输出
- 明确成功标准
- 明确与哪一层能力相关

### 2.3 任务分层

本 backlog 分为六类：

1. 第一层任务
2. 第二层任务
3. 第三层任务
4. 第四层任务
5. 埋点回归任务
6. 收口与实施任务


## 3. Phase 1：第一层基线稳定化

### 3.1 目标

- 明确第一层的职责边界
- 建立第一层专项样本和评估方式
- 固化第一层作为 baseline 的输出标准

### 3.2 任务列表

#### Task 1：固化第一层职责边界

内容：

- 在文档中明确第一层擅长识别的问题范围
- 列出第一层不应主承担的问题类型
- 形成第一层与第二、三层的职责边界说明

输出：

- `docs/architecture/v2-risk-recall-system-plan.md` 中第一层职责边界明确版

验收：

- 能明确回答“哪些问题由第一层兜底，哪些问题交给专题层”


#### Task 2：整理第一层专项样本集

内容：

- 建立第一层固定样本集
- 样本覆盖：
  - 明确命中样本
  - 易漏样本
  - 负样本
  - 高风险样本

输出：

- `data/examples/v2_baseline_eval_samples.json`

验收：

- 样本可直接用于 baseline 评估脚本


#### Task 3：补第一层评估脚本

内容：

- 新增 baseline 评估脚本
- 评估指标至少包括：
  - 风险命中率
  - 漏检率
  - 误报率
  - 高风险漏检率

建议文件：

- `scripts/eval_v2_baseline.py`

输出：

- baseline 层评估结果 JSON

验收：

- 可对固定样本集输出稳定评估结果


#### Task 4：补第一层回归测试

内容：

- 增加 baseline 层测试
- 校验：
  - 输出结构稳定
  - 基线结果可被 compare 层消费

输出：

- `tests/test_v2_baseline_eval.py`

验收：

- baseline 回归测试可运行


### 3.3 Phase 1 交付物

- baseline 专项样本
- baseline 评估脚本
- baseline 回归测试
- 第一层职责边界说明


## 4. Phase 2：第二层召回能力建设

### 4.1 目标

- 把第二层真正做成“证据召回层”
- 降低资格、评分、合同/付款/验收类问题的漏召回
- 为第三层专题深审提供完整 EvidenceBundle

### 4.2 任务列表

#### Task 5：固化第二层核心数据契约

内容：

- 统一以下结构：
  - `SectionCandidate`
  - `ModuleHit`
  - `EvidenceBundle`
  - `TopicCoverage`

输出：

- `app/pipelines/v2/schemas.py`

验收：

- 第二层、第三层、第四层可以共享同一套结构


#### Task 6：重构弱结构切分逻辑

内容：

- 将切分逻辑显式拆分为：
  - 标题切分
  - 表格块切分
  - 列表块切分
  - 连续段落聚合

输出：

- 标准化 `SectionCandidate[]`

验收：

- `document_map.json` 可稳定输出


#### Task 7：增强模块概率识别

内容：

- 不再只输出单模块结果
- 支持：
  - `primary_module`
  - `secondary_modules`
  - `confidence`
  - `reason`

输出：

- 更丰富的 `module_hits`

验收：

- 混合章节不再被硬裁断为单模块


#### Task 8：建设 EvidenceBundle 召回逻辑

内容：

- 按专题生成证据包
- 支持：
  - 标题召回
  - 关键词召回
  - 模块召回
  - 相邻上下文补召回

输出：

- `evidence_map.json`

验收：

- 每个专题都能聚合多个 section


#### Task 9：专项补混合章节召回

内容：

- 针对以下组合补召回规则：
  - 资格 + 评分
  - 商务 + 验收
  - 技术 + 验收
  - 样品演示 + 评分

输出：

- 混合章节召回增强版规则

验收：

- 混合章节的副专题漏召回明显下降


#### Task 10：第二层专项样本集建设

内容：

- 建立结构层专项样本，至少覆盖：
  - 资格条件识别准确性
  - 评分办法识别准确性
  - 合同/付款/验收识别准确性
  - 混合章节漏召回情况

输出：

- `data/examples/v2_structure_eval_samples.json`

验收：

- 每类结构问题至少有代表性样本


#### Task 11：第二层评估脚本完善

内容：

- 评估第二层：
  - 主模块归属一致率
  - 证据召回覆盖率
  - 混合章节副召回覆盖率

建议文件：

- `scripts/eval_v2_structure.py`

验收：

- 能输出结构层漏召回明细


### 4.3 Phase 2 交付物

- 完整 `document_map.json`
- 完整 `evidence_map.json`
- 第二层专项样本
- 第二层评估脚本


## 5. Phase 3：第三层专题深审建设

### 5.1 目标

- 让第三层成为真正的专题判断层
- 用专题边界和证据包提高风险判断精度
- 补第一层抓不稳的细节型风险

### 5.2 任务列表

#### Task 12：固化专题 taxonomy

内容：

- 明确专题集合与边界
- 至少覆盖：
  - `qualification`
  - `performance_staff`
  - `scoring`
  - `samples_demo`
  - `technical_bias`
  - `technical_standard`
  - `contract_payment`
  - `acceptance`
  - `procedure`
  - `policy`

输出：

- `app/pipelines/v2/topics.py`
- `topic taxonomy`

验收：

- 每个专题都有清晰主归属与排除范围


#### Task 13：补齐专题 prompt

内容：

- 校准并补齐各专题 prompt 文件
- 确保每个专题只处理单一问题空间

输出：

- `app/pipelines/v2/prompts/topic_*.py`

验收：

- 每个专题 prompt 都能单独解释其职责


#### Task 14：重构专题执行器

内容：

- `topic_review.py` 改为注册表驱动
- 每个专题只吃自己的 `EvidenceBundle`
- 输出：
  - `summary`
  - `risk_points`
  - `coverage_note`
  - `missing_evidence`
  - `need_manual_review`

输出：

- 新版 `topic_review.py`

验收：

- 默认/精简/增强模式可运行


#### Task 15：补专题边界契约

内容：

- 为专题定义：
  - `in_scope`
  - `out_of_scope`
  - `ownership_rule`
  - `merge_hints`

输出：

- 结构化边界定义

验收：

- 易混淆问题有清晰主归属


#### Task 16：建立专题专项样本集

内容：

- 每个专题都补四类样本：
  - 明确命中样本
  - 易混淆样本
  - 负样本
  - 需人工复核样本

输出：

- `data/examples/v2_topic_eval_samples.json`

验收：

- 主要专题均有四类样本


#### Task 17：补专题层评估脚本

内容：

- 评估专题层：
  - 命中率
  - 漏检率
  - 误报率
  - 需人工复核合理率

建议文件：

- `scripts/eval_v2_topics.py`

验收：

- 能输出按专题拆分的评估结果


### 5.3 Phase 3 交付物

- 完整专题 taxonomy
- 完整专题 prompt
- 专题专项样本
- 专题评估脚本


## 6. Phase 4：第四层汇总与补漏建设

### 6.1 目标

- 把 baseline 和 topic 结果稳定整合
- 避免重复、遗漏和无来源结论
- 明确 baseline-only / topic-only / conflict

### 6.2 任务列表

#### Task 18：固化 compare 数据契约

内容：

- 统一以下结构：
  - `RiskSignature`
  - `MergedRiskCluster`
  - `ComparisonArtifact`

输出：

- `app/pipelines/v2/schemas.py`
- `app/pipelines/v2/compare.py`

验收：

- compare 层可稳定接收 baseline + topic 输出


#### Task 19：增强聚类去重规则

内容：

- 聚类维度包括：
  - 标题关键词
  - 审查类型
  - 原文位置接近度
  - 原文摘录相似度
  - 来源专题

输出：

- 更稳定的风险聚类结果

验收：

- 同一风险点的重复输出显著减少


#### Task 20：补 baseline-only / topic-only 分析

内容：

- 明确输出：
  - `baseline_only_risks`
  - `topic_only_risks`
  - `coverage_gaps`

输出：

- 完整 `comparison.json`

验收：

- 能清楚看出专题层补出了哪些新增风险


#### Task 21：补冲突与人工复核整理

内容：

- 识别：
  - 等级冲突
  - 审查类型冲突
  - 是否需人工复核冲突
- 整理：
  - `manual_review_items`
  - `conflict_notes`

输出：

- 更完整的 compare 结果

验收：

- 冲突和人工复核原因可在最终报告中展示


#### Task 22：第四层专项样本集建设

内容：

- 建立汇总层样本：
  - 重复问题合并
  - baseline-only
  - topic-only
  - 冲突等级
  - 人工复核聚合

输出：

- `data/examples/v2_compare_eval_samples.json`

验收：

- 汇总层典型场景均可回归


#### Task 23：补汇总层评估脚本

内容：

- 评估：
  - 聚类准确率
  - 冲突保留准确率
  - baseline-only / topic-only 标记准确率

建议文件：

- `scripts/eval_v2_compare.py`

验收：

- 可输出 compare 层专项评估结果


### 6.3 Phase 4 交付物

- 完整 `comparison.json`
- 汇总层样本
- 汇总层评估脚本
- 最终统一报告装配器


## 7. Phase 5：埋点回归体系建设

### 7.1 目标

- 将“招标文件 + 埋点文件”转化为稳定回归机制
- 自动识别结构漏召回、专题漏检、误报和冲突问题

### 7.2 任务列表

#### Task 24：定义埋点文件映射规则

内容：

- 明确埋点文件如何映射为：
  - 结构层标签
  - 风险层标签

输出：

- 埋点解释规则文档

验收：

- 同一份埋点文件能被稳定转成评估输入


#### Task 25：补结构层埋点转换器

内容：

- 将埋点结果转换为结构层校验格式
- 支持：
  - section 命中
  - 模块命中
  - 召回覆盖校验

输出：

- 结构层金标转换产物

验收：

- 可直接用于第二层回归


#### Task 26：补风险层埋点转换器

内容：

- 将埋点结果转换为风险评估格式
- 支持：
  - 风险标题
  - 风险等级
  - 审查类型
  - 原文位置
  - 是否人工复核

输出：

- 风险层金标转换产物

验收：

- 可直接用于第三层和第四层回归


#### Task 27：实现自动比对脚本

内容：

- 比对：
  - 第二层输出 vs 结构埋点
  - 第三层输出 vs 风险埋点
  - 第四层输出 vs 风险埋点

输出：

- `missed_risks.json`
- `false_positive_risks.json`
- `manual_review_gaps.json`

验收：

- 能自动输出漏点、误报和人工复核差异


#### Task 28：回归结果可视化输出

内容：

- 将回归结果输出为便于研发查看的 Markdown/JSON

输出：

- `regression_report.md`

验收：

- 能直接看出下一轮优化重点


### 7.3 Phase 5 交付物

- 埋点转换规则
- 自动比对脚本
- 漏点和误报清单
- 回归报告


## 8. Phase 6：页面与人工复核收口

### 8.1 目标

- 让多层结果更利于人工审查人员使用
- 突出来源、冲突、人工复核原因

### 8.2 任务列表

#### Task 29：结果页强化来源可见性

内容：

- 在结果页展示：
  - 来源标签
  - baseline/topic 命中关系
  - 冲突标记

验收：

- 审查人员能快速看出风险点来源


#### Task 30：结果页强化人工复核区

内容：

- 集中展示：
  - 需人工复核事项
  - 复核原因
  - 证据缺口提示

验收：

- 人工复核区可独立查看


#### Task 31：接入回归分析结果到研发页面

内容：

- 在研发视图或内部结果页中增加：
  - 漏点清单
  - 误报清单
  - 分层评估摘要

验收：

- 开发人员可直接查看当前系统短板


### 8.3 Phase 6 交付物

- 页面强化版
- 人工复核区
- 内部研发回归视图


## 9. 优先级建议

### 9.1 P0

- Task 2
- Task 3
- Task 10
- Task 11
- Task 16
- Task 17
- Task 24
- Task 27

说明：

- 这些任务直接关系到“找全风险点”的能力验证与提升

### 9.2 P1

- Task 5
- Task 6
- Task 7
- Task 8
- Task 9
- Task 12
- Task 13
- Task 14
- Task 15
- Task 18
- Task 19
- Task 20
- Task 21
- Task 22
- Task 23

说明：

- 这些任务是第二、三、四层能力成熟化的主体

### 9.3 P2

- Task 1
- Task 4
- Task 25
- Task 26
- Task 28
- Task 29
- Task 30
- Task 31

说明：

- 这些任务重要，但可在主能力基本稳定后补强


## 10. 推荐实施顺序

建议按以下顺序推进：

1. 第一层专项样本与评估
2. 第二层召回能力与结构样本
3. 第三层专题样本与边界固化
4. 第四层 compare 样本与聚类收口
5. 埋点文件自动比对
6. 页面和人工复核体验收口


## 11. 一句话结论

这份 backlog 的核心不是“把四层都做一遍”，而是：

- 先把第二层做成不易漏证据的召回层
- 再把第三层做成边界稳定的专题判断层
- 再把第四层做成能解释补漏结果的汇总层
- 最后用埋点文件把整个系统变成可持续优化的回归体系

只有这样，V2 才能真正朝“精准找到所有风险点”的目标收敛。
