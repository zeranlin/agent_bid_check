# 成熟版 V2 实施任务清单

## 1. 任务拆分原则

本清单用于把《成熟版 V2 架构方案》拆解为可开发、可验收、可排期的具体任务。

拆分原则：

- 先补底层能力，再扩专题，再补汇总，再升级页面
- 每一阶段都应保留可运行状态
- 不破坏当前 V1
- 尽量保持当前 V2 产物兼容
- 每个任务都应有明确输入、输出、验收标准


## 2. 阶段总览

建议分为 4 个阶段：

1. `Phase 1`：结构识别与证据召回层升级
2. `Phase 2`：专题扩容与专题契约落地
3. `Phase 3`：对比汇总层建设
4. `Phase 4`：Web 展示与回归验收建设


## 3. Phase 1：结构识别与证据召回层升级

### 3.1 目标

- 把第二层从“规则切分层”升级为“证据召回层”
- 为第三层专题深审提供更完整、更稳定的证据包
- 保留当前 `document_map.json` 兼容输出

### 3.2 任务列表

#### Task 1：定义结构层数据契约

内容：

- 在 `app/pipelines/v2/schemas.py` 中新增：
  - `SectionCandidate`
  - `ModuleHit`
  - `EvidenceBundle`
  - `TopicCoverage`

输出：

- 新 schema 可被结构层、专题层、汇总层复用

验收：

- 类型定义完整
- 不影响现有 `TopicReviewArtifact`


#### Task 2：重构 `structure.py`

内容：

- 把当前基于规则的粗切分逻辑拆成独立函数：
  - `split_sections()`
  - `score_modules()`
  - `merge_adjacent_sections()`
- 输出标准化 `SectionCandidate[]`

输出：

- 更稳定的章节候选列表

验收：

- `document_map.json` 继续可生成
- 字段兼容旧版，允许新增字段


#### Task 3：新增 `evidence.py`

内容：

- 新增专题证据召回逻辑
- 支持：
  - 按模块召回
  - 按关键词召回
  - 按章节标题召回
  - 按相邻段落补上下文

输出：

- `topic_evidence_bundles`
- `evidence_map.json`

验收：

- 每个专题都能生成证据包
- 同一专题可聚合多个章节片段


#### Task 4：引入结构层 LLM 二次识别

内容：

- 在规则识别后增加可选 LLM 模块识别
- 仅在规则置信度不足时触发

输出：

- `structure_llm_used`
- `module_hits`
- `structure_fallback_used`

验收：

- 第二层最多额外调用 1 次 LLM
- 超时或失败时自动回退到规则模式


#### Task 5：结构层回归样本与指标脚本

内容：

- 增加结构层评估脚本
- 对固定样本集计算：
  - 模块主归属一致率
  - 关键章节召回率

建议文件：

- `scripts/eval_v2_structure.py`

验收：

- 可输出结构层指标
- 能用于后续回归


### 3.3 Phase 1 交付物

- 更新后的 `structure.py`
- 新增 `evidence.py`
- 更新后的 `schemas.py`
- `document_map.json` 兼容版
- `evidence_map.json`
- 结构层评估脚本


## 4. Phase 2：专题扩容与专题契约落地

### 4.1 目标

- 把专题层从当前粗专题扩展为成熟专题体系
- 明确专题边界
- 降低重复命中和交叉冲突

### 4.2 任务列表

#### Task 6：梳理专题 taxonomy

内容：

- 在文档或代码中固化专题边界：
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

- `topic taxonomy`
- 主归属规则

验收：

- 每个专题有清晰职责
- 无明显职责冲突


#### Task 7：扩展提示词文件

内容：

- 新增专题提示词：
  - `topic_performance_staff.py`
  - `topic_samples_demo.py`
  - `topic_acceptance.py`
  - `topic_technical_standard.py`
  - `topic_procedure.py`
  - `topic_policy.py`

验收：

- 每个提示词聚焦单一专题
- 输出结构统一


#### Task 8：重构 `topic_review.py`

内容：

- 支持专题注册表
- 每个专题独立输入 `EvidenceBundle`
- 每个专题输出：
  - `risk_points`
  - `summary`
  - `coverage_note`
  - `missing_evidence`
  - `need_manual_review`

验收：

- 支持默认专题集和精简专题集
- 支持按预算跳过低优先级专题


#### Task 9：新增专题调用预算控制

内容：

- 增加默认模式与加强模式
- 默认模式下：
  - 高优先级专题必跑
  - 低优先级专题可跳过

验收：

- 默认模式总调用数不超过预算
- 专题超时时可降级或跳过


#### Task 10：专题层评估脚本

内容：

- 增加专题层评估脚本
- 评估：
  - 高中风险命中率
  - 技术细节命中率
  - 人工复核比例

建议文件：

- `scripts/eval_v2_topics.py`

验收：

- 支持固定样本集评测


### 4.3 Phase 2 交付物

- 扩展后的专题体系
- 新专题提示词文件
- 新版 `topic_review.py`
- 专题层评估脚本


## 5. Phase 3：对比汇总层建设

### 5.1 目标

- 把第四层从“结果拼接”升级成“分析型汇总”
- 补齐风险聚类、冲突识别、漏项分析能力

### 5.2 任务列表

#### Task 11：定义汇总层数据契约

内容：

- 在 `schemas.py` 中新增：
  - `ComparisonArtifact`
  - `MergedRiskCluster`
  - `RiskSignature`

验收：

- 汇总层可独立消费基线层和专题层输出


#### Task 12：新增 `compare.py`

内容：

- 实现风险签名生成
- 实现重复风险聚类
- 实现严重级别冲突裁决
- 实现来源聚合

验收：

- 同一风险可跨专题聚类
- 冲突项有明确标记


#### Task 13：补漏与覆盖分析

内容：

- 识别：
  - 某专题未召回关键证据
  - 某专题证据不足却给出结论
  - 基线与专题差异过大

输出：

- `coverage_summary`
- `missing_topic_coverage`
- `manual_review_items`

验收：

- `comparison.json` 可生成


#### Task 14：重构 `assembler.py`

内容：

- 让最终报告基于 `MergedRiskCluster` 生成
- 统一风险点编号
- 为每个风险点保留多个原文位置与来源信息

验收：

- 最终报告不再只是基线 + 专题简单拼接


#### Task 15：汇总层评估脚本

内容：

- 评估：
  - 聚类准确率
  - 冲突识别正确率
  - 最终风险点去重效果

建议文件：

- `scripts/eval_v2_compare.py`


### 5.3 Phase 3 交付物

- 新增 `compare.py`
- 更新 `assembler.py`
- 新增 `comparison.json`
- 汇总层评估脚本


## 6. Phase 4：Web 展示与回归验收建设

### 6.1 目标

- 让成熟版 V2 不只是后端能力升级，还能在页面上被看清楚、被复核
- 建立固定回归样本集与评估脚本

### 6.2 任务列表

#### Task 16：升级 V2 页面专题视图

内容：

- 增加专题覆盖度展示
- 增加风险来源标签
- 增加“需人工复核原因”展示

验收：

- 页面可展示专题覆盖说明


#### Task 17：增加差异视图

内容：

- 若存在 `comparison.json`：
  - 展示基线发现
  - 展示专题补充发现
  - 展示冲突项

验收：

- 旧结果无 `comparison.json` 时页面不报错


#### Task 18：历史结果兼容迁移

内容：

- 确保旧 `document_map.json`
- 旧 `topic_reviews/*.json`
- 旧 `v2_overview.json`

仍可被当前页面读取

验收：

- 旧运行目录可回放
- 新旧下载接口兼容


#### Task 19：建立固定样本集

内容：

- 新建标准样本目录
- 建立人工标注文件
- 固化回归入口

建议目录：

- `data/eval/v2_samples/`
- `data/eval/v2_labels/`

验收：

- 评估脚本可对固定样本集运行


#### Task 20：总评估脚本与验收报告

内容：

- 聚合结构层、专题层、汇总层指标
- 输出单次评估报告

建议文件：

- `scripts/eval_v2_all.py`

验收：

- 可产出一份总的评估结果


### 6.3 Phase 4 交付物

- 升级后的 V2 页面
- 固定回归样本集
- 评估脚本集合
- 验收报告模板


## 7. 优先级建议

### P0

- Task 1
- Task 2
- Task 3
- Task 6
- Task 8
- Task 11
- Task 12
- Task 14

### P1

- Task 4
- Task 7
- Task 9
- Task 13
- Task 16
- Task 17
- Task 18

### P2

- Task 5
- Task 10
- Task 15
- Task 19
- Task 20


## 8. 建议实施顺序

推荐按以下顺序推进：

1. 先做结构层 schema 与 `evidence.py`
2. 再重构 `structure.py`
3. 再扩展 `topic_review.py`
4. 再做 `compare.py`
5. 再改 `assembler.py`
6. 最后补页面与评估脚本


## 9. 每阶段完成定义

### Phase 1 完成定义

- `document_map.json` 兼容输出
- 专题 evidence bundle 可生成
- 第二层失败时有稳定降级路径

### Phase 2 完成定义

- 重点专题完成扩容
- 专题边界规则落地
- 默认预算模式可运行

### Phase 3 完成定义

- `comparison.json` 可生成
- 最终报告基于聚类结果输出
- 冲突和漏项可识别

### Phase 4 完成定义

- 页面支持成熟版 V2 的关键结果展示
- 样本集与评估脚本齐备
- 可形成阶段性验收结论


## 10. 结论

这份任务清单的目标，是把成熟版 V2 从“架构想法”落成“可排期、可开发、可验收”的工程执行项。

后续若进入真正开发阶段，建议先以 `Phase 1 + Phase 2` 为主，先把结构识别与专题深审打稳，再进入 `Phase 3` 的对比汇总层建设。
