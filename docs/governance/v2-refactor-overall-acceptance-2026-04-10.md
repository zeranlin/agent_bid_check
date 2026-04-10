# V2 重构总体验收与收口报告

日期：`2026-04-10`

适用范围：

- `Task-EP1` ~ `Task-EP4`
- `Task-PB1` ~ `Task-PB4`
- `Task-PU1`
- `Task-GR1`
- `Task-GR2`

---

## 总体结论

结论：建议本轮整体收口，并进入下一阶段。

判断依据：

- 主链已完成 `证据层 -> 问题层 -> 准入层 -> 发布层` 串通。
- `conflict problem` 已能走完整链路，并在 `final_snapshot` 中保留结构化冲突字段。
- `final_snapshot` 已成为成品事实主源，Web / Markdown / history / API 已收口到同一来源。
- `GR1` 三份关键真实文件 replay 基线已全绿。
- `GR2` 已建立反馈分层归因和整改建议机制，后续新增反馈不再默认落到 `rule_layer`。

是否建议进入下一阶段：建议进入。

当前最大剩余风险：

- 本轮主链已稳定，但下一阶段若继续扩规则或扩反馈样本，仍需严守 `GR1` replay 基线与 `GR2` 分层归因门禁，避免新问题再次绕开单源链路回流。

---

## 本轮范围

### A 线：证据层

- `Task-EP1`：证据层骨架搭建
- `Task-EP2`：证据来源分类补齐
- `Task-EP3`：证据业务分类补齐
- `Task-EP4`：条款角色与硬证据判定补齐

### B 线：问题层

- `Task-PB1`：问题层骨架搭建
- `Task-PB2`：同簇候选归并与主副吸收
- `Task-PB3`：跨专题问题归并与跨层冲突收口
- `Task-PB4`：跨专题一致性冲突识别补强

### C 线：发布层

- `Task-PU1`：发布层 `final snapshot` 单源化

### D 线：治理与回放

- `Task-GR1`：真实文件 replay 基线重建
- `Task-GR2`：分层问题登记与任务归因机制

---

## 架构闭环状态

### 证据层

- 已建立统一 `Evidence` 对象。
- 已接入 `source_kind / business_domain / clause_role / evidence_strength / hard_evidence`。
- 候选风险可回溯到 `evidence_id / excerpt / location`。

### 问题层

- 已建立统一 `Problem` 对象。
- 已完成同簇归并、主副吸收、跨专题归并和 conflict problem 建模。
- admission 已改为消费问题对象，不再直接消费松散 candidate。

### 准入层

- `risk_admission` 仍是唯一最终三分层出口。
- 问题层冲突输入已在 admission 前完成统一收口。

### 发布层

- `final_snapshot` 已成为唯一成品事实源。
- `final_output.json` 已降级为 `final_snapshot` 派生物。
- 冲突问题在成品侧保留 `left_side / right_side / conflict_reason / conflict_evidence_links`。

### replay / 反馈治理

- `GR1` 已形成三份关键真实文件 replay 基线。
- `GR2` 已形成“反馈 -> 分层归因 -> 整改建议”的统一机制。

---

## 真实文件回放结果摘要

基线主配置：

- [docs/trackers/v2-real-replay-baselines.yaml](/Users/linzeran/code/2026-zn/test_getst/docs/trackers/v2-real-replay-baselines.yaml)

### 柴油

- replay 目录：[data/results/v2/gr1-diesel-baseline](/Users/linzeran/code/2026-zn/test_getst/data/results/v2/gr1-diesel-baseline)
- 结果：通过
- 摘要：`formal 7 / pending 19 / excluded 3`
- 基线要点：
  - 应报：进口一致性相关主风险、认证评分主风险、检测费用主风险
  - 不应报：模板留白、程序边界项
  - 待补证：检测/认证要求缺失、评分量化口径不足

### 福建物业

- replay 目录：[data/results/v2/gr1-fujian-baseline](/Users/linzeran/code/2026-zn/test_getst/data/results/v2/gr1-fujian-baseline)
- 结果：通过
- 摘要：`formal 0 / pending 20 / excluded 1`
- 基线要点：
  - 应报：品牌倾向评分、实验服清洗服务品牌指定风险
  - 不应报：依赖后续合同确定的模板型验收误报
  - 待补证：验收流程笼统、中小企业评审细节待确认
- 备注：
  - 当前链路下福建物业已整体收紧到 pending 主导，但应报项仍稳定留在结果池，不构成 replay 回退。

### 福州一中

- replay 目录：[data/results/v2/gr1-fuzhou-baseline](/Users/linzeran/code/2026-zn/test_getst/data/results/v2/gr1-fuzhou-baseline)
- 结果：通过
- 摘要：`formal 8 / pending 16 / excluded 3`
- 基线要点：
  - 应报：样品门槛、厂家验收标准、采购人单方变更权过大且结算不明
  - 不应报：无犯罪证明误标题、开标签字默认认可、模板留白验收条款
  - 待补证：缺乏预付款、远程解密时限及后果条款

---

## 台账与任务状态对照

台账主源：

- [docs/trackers/v2-remediation-tracker.md](/Users/linzeran/code/2026-zn/test_getst/docs/trackers/v2-remediation-tracker.md)

本轮任务状态：

- `Task-EP1` ~ `Task-EP4`：已通过
- `Task-PB1` ~ `Task-PB4`：已通过
- `Task-PU1`：已通过
- `Task-GR1`：已通过
- `Task-GR2`：已通过

对账结论：

- 本轮范围内任务已全部进入总台账。
- 当前未发现“任务已通过但关键产物缺失”的状态漂移。
- 当前未发现 roadmap / tracker / replay 主配置之间的显著不一致。

---

## 文档与治理主源对照

关键文档：

- [docs/governance/v2-evidence-problem-publish-refactor-roadmap.md](/Users/linzeran/code/2026-zn/test_getst/docs/governance/v2-evidence-problem-publish-refactor-roadmap.md)
- [docs/trackers/v2-real-replay-baselines.yaml](/Users/linzeran/code/2026-zn/test_getst/docs/trackers/v2-real-replay-baselines.yaml)
- [docs/trackers/v2-real-replay-issue-ledger.yaml](/Users/linzeran/code/2026-zn/test_getst/docs/trackers/v2-real-replay-issue-ledger.yaml)
- [docs/trackers/v2-feedback-attribution-ledger.yaml](/Users/linzeran/code/2026-zn/test_getst/docs/trackers/v2-feedback-attribution-ledger.yaml)

一致性结论：

- roadmap 负责说明本轮任务编排与顺序；
- replay baseline 负责真实文件回归底座；
- issue ledger 负责真实回放问题闭环；
- feedback attribution ledger 负责新增反馈分层归因；
- 当前四者与实现边界一致，可作为本轮收口后的持续治理主源。

---

## 已完成项与未完成项

### 本轮已完成项

- 证据层对象与分类体系
- 问题层对象、归并、吸收、conflict 建模
- 准入层唯一裁决链路承接
- 发布层 `final_snapshot` 单源化
- 三份关键真实文件 replay 基线
- 反馈分层归因与任务建议机制

### 本轮未完成项

- 本轮未纳入“下一阶段扩规则、扩样本、扩反馈自动化”的实现工作
- 未纳入 Web 视觉层重构
- 未纳入更广泛的发布运营工具链建设

这些不构成当前收口阻塞，属于下一阶段 backlog。

---

## 下一阶段 Backlog

### P0

- 扩新能力时强制接入 `GR1` 三文件 replay 基线门禁
- 将新反馈持续纳入 `GR2` 归因账本，避免再次默认落 `rule_layer`
- 持续守住 `final_snapshot` 单源，不允许新旁路回流

### P1

- 扩展更多真实文件进入 replay 基线
- 提升 `GR2` 自动归因覆盖率与证据丰富度
- 针对下一批高价值真实问题，按层分发专题整改任务

### P2

- 更强的治理报表自动化
- 更细粒度的任务 / replay / 反馈联动面板
- 非核心展示体验优化

---

## 建议关单

建议按本轮总体验收结论，正式视为可整体收口的任务：

- `Task-EP1`
- `Task-EP2`
- `Task-EP3`
- `Task-EP4`
- `Task-PB1`
- `Task-PB2`
- `Task-PB3`
- `Task-PB4`
- `Task-PU1`
- `Task-GR1`
- `Task-GR2`

建议动作：

- 以上任务保持“已通过”状态，并以本报告作为总体验收收口依据；
- 后续新工作进入下一阶段 backlog，不再将本轮主链任务视为开放整改项。
