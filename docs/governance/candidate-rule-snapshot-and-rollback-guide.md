# 候选规则快照与回滚说明

## 1. 适用范围

本文档用于说明候选规则池在 `Task-G7` 之后的快照命名、批次追踪和最小回滚口径。

适用目录：

- `rules/candidates/imports/`
- `rules/candidates/mappings/`
- `rules/candidates/snapshots/`
- `rules/registry/`

## 2. 快照命名规则

统一使用 `SNAP-YYYY-MM-DD-<action>-XXX`。

动作类型限定为：

- 导入批次：`SNAP-YYYY-MM-DD-import-XXX`
- 分流批次：`SNAP-YYYY-MM-DD-triage-XXX`
- 迁移批次：`SNAP-YYYY-MM-DD-migrate-XXX`

说明：

1. `YYYY-MM-DD` 为日期。
2. `<action>` 为动作类型。
3. `XXX` 为三位递增批次号。

## 3. 回滚场景

### 3.1 候选池分流判断错误

回滚对象至少包括：

- `rules/candidates/mappings/` 对应分流台账
- `rules/candidates/snapshots/` 对应分流快照
- 必要时回写 `rules/candidates/imports/` 对应导入批次说明

处理原则：

1. 保留原始导入条目。
2. 回退分流判断和快照记录。
3. 不直接影响 `rules/registry/` 正式规则库。

### 3.2 某批纳管引入误报

回滚对象至少包括：

- 相关迁移批次快照
- `rules/registry/` 中该批纳管涉及的正式规则文件
- 对应样本、测试和任务单记录

处理原则：

1. 先按迁移批次定位问题范围。
2. 优先回退该批纳管范围，而不是全局回退。
3. 保留候选池条目，等待补强后重新迁移。

### 3.3 已入正式规则但后续发现问题

回滚对象至少包括：

- `rules/registry/` 中对应规则
- 对应快照、任务单、样本和测试记录

处理原则：

1. 若问题可补强，转入补强任务单并保留追踪关系。
2. 若问题影响当前稳定性，可先暂停启用或降级处理。
3. 所有动作都要回写到快照和台账记录中。

## 4. 工具校验闭环

当前最小校验命令：

```bash
python scripts/validate_rule_registry.py --candidate-root rules/candidates
```

该命令当前检查：

1. 候选池根目录是否存在
2. `sources / imports / mappings / snapshots` 子目录及其 `README.md` 是否存在
3. 候选池骨架是否完整

本轮只做最小骨架校验，不做深度候选规则内容校验。
