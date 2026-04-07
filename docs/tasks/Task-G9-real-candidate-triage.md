# Task-G9 真实候选规则首轮分流任务单

## 基本信息

- 任务编号：`Task-G9`
- 任务名称：150条真实候选规则首轮分流
- 任务类型：`治理架构实施`
- 当前状态：`已通过`
- 下发对象：`T`
- 监督角色：`M`

## 任务背景

`G6 / G7 / G8` 已建立候选池、快照回滚和首批样板纳管机制，但项目仍停留在 seed 样板阶段，尚未接住真实约 150 条外部候选审查点。

本任务要求将用户指定的真实来源文件正式接入候选池，并完成首轮真实分流。

## 真实来源

- 来源文件：`/Users/linzeran/code/2026-zn/test_target/合规性审查点反馈表分层映射清单.md`
- 来源说明：用户指定作为“真实 150 条候选规则来源”的首轮接入文件

## 交付结果

### 已完成产物

- 来源索引：`rules/candidates/sources/external-review-points-real-2026-04-07.md`
- 导入批次：`rules/candidates/imports/candidate_rules_2026-04-07_real_batch_001.yaml`
- 分流台账：`rules/candidates/mappings/candidate_rule_ledger_2026-04-07_real_batch_001.yaml`
- 统计摘要：`rules/candidates/mappings/candidate_rule_triage_summary_2026-04-07_real_batch_001.yaml`
- 快照文件：`rules/candidates/snapshots/SNAP-2026-04-07-triage-002.md`

### 首轮统计

- `total_candidates = 154`
- `formal_rule = 84`
- `conditional_rule = 56`
- `capability_item = 12`
- `drop = 2`

### 已吸收条目标注

- `RC-037` -> `R-005`
- `RC-047` -> `R-006`
- `RC-073` -> `R-004`
- `RC-074` -> `R-003`
- `RC-107` -> `R-002`
- `RC-110` -> `R-001`
- `RC-127` -> `R-007`

## M 验收结论

- 验收结论：`已通过`
- 验收评分：`93 / 100`

### 通过依据

1. 真实来源文件已正式接入候选池
2. 已建立真实导入批次、分流台账、统计摘要和快照
3. 已对一批现有规则吸收关系做清晰标注
4. 已输出第一批优先纳管候选清单和能力项 backlog
5. 对应测试与候选池最小校验已通过

### 收尾项

1. 后续继续把 `first_priority_candidates` 往下拆成正式纳管任务
2. 与 `Task-G10` 衔接，避免真实分流结果悬空
