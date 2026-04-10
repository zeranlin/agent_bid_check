# 候选快照目录

`rules/candidates/snapshots/` 保存候选规则导入、分流和迁移前后的批次快照。

快照命名规则统一使用：

- 导入批次：`SNAP-YYYY-MM-DD-import-XXX`
- 分流批次：`SNAP-YYYY-MM-DD-triage-XXX`
- 迁移批次：`SNAP-YYYY-MM-DD-migrate-XXX`

命名约束：

1. `YYYY-MM-DD` 必填，用于标记批次日期。
2. 动作类型只允许 `import / triage / migrate`。
3. `XXX` 为三位递增序号，例如 `001 / 002 / 003`。

快照至少应记录：

1. `snapshot_id`
2. 批次范围
3. 导入文件
4. 分流台账
5. 当前结论摘要

本目录用于后续 `Task-G7` 快照回滚能力建设。
