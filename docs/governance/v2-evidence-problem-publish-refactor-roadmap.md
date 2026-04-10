# V2 证据层 / 问题层 / 发布层重构任务路线图

## 1. 目标

本路线图用于承接：

- [v2-evidence-problem-publish-refactor-design.md](https://github.com/zeranlin/agent_bid_check/blob/main/docs/governance/v2-evidence-problem-publish-refactor-design.md)

目标是把本轮重构拆成可执行、可验收、可回放的任务序列，后续由 M 按顺序下发给 T。

## 2. 重构主线

本轮任务分为 4 条主线：

1. `A 线：证据层`
2. `B 线：问题层`
3. `C 线：发布层`
4. `D 线：回放与治理`

## 3. 推荐执行顺序

必须按以下顺序推进：

1. 先做 `A 线`
2. 再做 `B 线`
3. 再做 `C 线`
4. 最后做 `D 线`

原因：

1. 证据对象不稳，后面问题层和发布层都会带偏
2. 问题对象不单源，准入和发布都无法真正稳定
3. 发布层必须等前面两层对象模型稳定后再做单源发布
4. replay 和治理门禁必须基于新对象模型固化

## 4. 任务总表

| 顺序 | 任务编号 | 任务名称 | 主线 | 优先级 | 目标 |
| --- | --- | --- | --- | --- | --- |
| 1 | `Task-EP1` | 证据层骨架搭建 | A | P0 | 建立 evidence pipeline、schema、trace 骨架 |
| 2 | `Task-EP2` | 证据来源分类补齐 | A | P0 | 建立 `source_kind` 分类体系 |
| 3 | `Task-EP3` | 证据业务分类补齐 | A | P0 | 建立 `business_domain` 分类体系 |
| 4 | `Task-EP4` | 条款角色与硬证据判定补齐 | A | P0 | 建立 `clause_role / evidence_strength / hard_evidence` |
| 5 | `Task-PB1` | 问题层骨架搭建 | B | P0 | 建立 `problem_id`、问题对象与问题层 pipeline |
| 6 | `Task-PB2` | 同簇候选归并与主副吸收 | B | P0 | 解决重复报、主副风险拆碎 |
| 7 | `Task-PB3` | 跨专题问题归并与跨层冲突收口 | B | P0 | 解决同一问题跨专题、跨层并存 |
| 8 | `Task-PB4` | 跨专题一致性冲突识别补强 | B | P1 | 支撑“拒绝进口 vs 外标引用”等跨问题矛盾 |
| 9 | `Task-PU1` | 发布层 final snapshot 单源化 | C | P0 | 统一 Web / Markdown / history / API 出口 |
| 10 | `Task-PU2` | 发布追溯链与 run_id 索引补齐 | C | P1 | 能从展示结果反查问题、证据、规则 |
| 11 | `Task-GR1` | 真实文件 replay 基线重建 | D | P0 | 建立柴油/福建/福州关键回放基线 |
| 12 | `Task-GR2` | 分层问题登记与任务归因机制 | D | P1 | 让误报/漏报先归因到具体层级 |
| 13 | `Task-GR3` | 重构后总体验收与关单收口 | D | P0 | 汇总真实文件、台账、文档、门禁结果 |

## 5. 每个任务的职责边界

### 5.1 A 线：证据层

#### `Task-EP1` 证据层骨架搭建

目标：

1. 建立 `app/pipelines/v2/evidence_layer/` 或等价模块
2. 定义 evidence schema
3. 让解析输出先进入证据层，再进入专题

不在本任务范围：

1. 复杂业务分类
2. 问题归并
3. 发布层改造

#### `Task-EP2` 证据来源分类补齐

目标：

补齐以下 `source_kind`：

1. `body_clause`
2. `template_clause`
3. `placeholder_clause`
4. `contract_template`
5. `attachment_clause`
6. `reminder_clause`
7. `form_clause`
8. `sample_clause`

优先解决：

1. 模板误报
2. 合同格式误报
3. 留白误报
4. 提醒项误升 formal

#### `Task-EP3` 证据业务分类补齐

目标：

补齐以下 `business_domain`：

1. `qualification`
2. `scoring`
3. `technical`
4. `technical_standard`
5. `commercial`
6. `acceptance`
7. `policy`
8. `procedure`
9. `sample`
10. `performance_staff`

优先解决：

1. 资格 / 评分混淆
2. 技术 / 商务混淆
3. 验收 / 样品 / 评分混挂

#### `Task-EP4` 条款角色与硬证据判定补齐

目标：

补齐：

1. `clause_role`
2. `evidence_strength`
3. `hard_evidence`

优先解决：

1. 哪些证据可进入 formal 候选
2. 哪些只能进入 pending
3. 哪些默认排除

### 5.2 B 线：问题层

#### `Task-PB1` 问题层骨架搭建

目标：

1. 建立问题对象模型
2. 定义 `problem_id`
3. 让候选先进入问题层，再进入准入层

#### `Task-PB2` 同簇候选归并与主副吸收

目标：

1. 解决近义标题重复报
2. 解决主风险和附属说明拆碎
3. 统一标准标题

优先验证：

1. 商务失衡问题簇
2. 样品问题簇
3. 技术参数过细问题簇

#### `Task-PB3` 跨专题问题归并与跨层冲突收口

目标：

1. 解决同一问题在多个专题重复出现
2. 解决同一问题在 `formal / pending / excluded` 中跨层并存

#### `Task-PB4` 跨专题一致性冲突识别补强

目标：

重点支持：

1. `不得进口 vs 外标引用`
2. 需求与评审规则、技术与政策之间的互相矛盾

### 5.3 C 线：发布层

#### `Task-PU1` 发布层 final snapshot 单源化

目标：

1. Web / Markdown / history / API 只消费统一 `final snapshot`
2. 不再允许旧 summary、自由文案、旁路结果进入成品输出

#### `Task-PU2` 发布追溯链与 run_id 索引补齐

目标：

1. 支持从一条展示结果追到：
   - `run_id`
   - `problem_id`
   - `evidence_id`
   - `rule_id`
2. 加快运维排查和客户反馈复现

### 5.4 D 线：回放与治理

#### `Task-GR1` 真实文件 replay 基线重建

目标：

至少纳入：

1. 柴油文件
2. 福建物业文件
3. 福州一中宿舍家具文件

为每份文件维护：

1. 已知应报项
2. 已知不应报项
3. 已知待补证项

#### `Task-GR2` 分层问题登记与任务归因机制

目标：

让每个反馈先归类到：

1. 证据层
2. 问题层
3. 准入层
4. 发布层
5. 规则层

禁止默认全部落成“补规则”。

#### `Task-GR3` 重构后总体验收与关单收口

目标：

1. 汇总所有任务验收结果
2. 汇总真实文件 replay 结果
3. 汇总台账、文档、门禁结果
4. 作为本轮重构总关单入口

## 6. 任务优先级说明

### P0

必须先做，且不过线不能进入下一批：

1. `Task-EP1`
2. `Task-EP2`
3. `Task-EP3`
4. `Task-EP4`
5. `Task-PB1`
6. `Task-PB2`
7. `Task-PB3`
8. `Task-PU1`
9. `Task-GR1`
10. `Task-GR3`

### P1

在主链稳定后跟进：

1. `Task-PB4`
2. `Task-PU2`
3. `Task-GR2`

## 7. 建议下发顺序

后续建议由 M 按以下顺序下发给 T：

1. `Task-EP1`
2. `Task-EP2`
3. `Task-EP3`
4. `Task-EP4`
5. `Task-PB1`
6. `Task-PB2`
7. `Task-PB3`
8. `Task-PB4`
9. `Task-PU1`
10. `Task-PU2`
11. `Task-GR1`
12. `Task-GR2`
13. `Task-GR3`

## 8. 每阶段的验收门槛

### A 线验收门槛

1. 来源分类稳定
2. 业务分类稳定
3. 条款角色稳定
4. 模板/留白/提醒项误报明显下降

### B 线验收门槛

1. 同一问题能形成稳定 `problem_id`
2. 同簇重复报明显下降
3. 跨层并存问题明显下降

### C 线验收门槛

1. Web / Markdown / history / API 单源一致
2. 能从展示结果直接回到问题和证据

### D 线验收门槛

1. 关键真实文件 replay 稳定不过线不能关单
2. 任务单、台账、治理文档同步完成

## 9. 结论

本轮重构的正确顺序不是：

`先加规则 -> 再看结果`

而是：

`先稳证据 -> 再稳问题 -> 再稳发布 -> 最后固化 replay 与治理`

后续 M 应严格按本路线图顺序下发给 T，避免再次出现：

1. 前面对象模型还没稳，后面先补展示
2. 证据层没稳，就先补问题归并
3. 发布层没单源，就先做 Web 修补

只有这样，这轮重构才能真正收口。
