# V2 真实回放根因闭环说明

## 1. 目标

本说明用于固定真实文件问题的最小闭环：

1. 真实文件反馈进入问题级台账
2. 每个问题落到明确问题类型与根因层级
3. 每个问题绑定整改任务编号
4. 每次回放结果只保留结果与索引，不承担主账本职责
5. M 可基于结构化产物直接完成验收与回写

## 2. 单源位置

问题级闭环单源固定为：

- `docs/trackers/v2-real-replay-issue-ledger.yaml`

结果层只保留：

- `data/results/v2/<run_id>/`
- `data/results/v2/<run_id>/replay_closure_index.json`

其中 `replay_closure_index.json` 只做索引，不做治理主账本。

## 3. 问题分类

每个问题至少归类为以下之一：

- `误报`
- `漏报`
- `错层`
- `重复`
- `风险文案偏差`
- `规则归属错误`
- `证据映射错误`

## 4. 根因层级

每个问题必须填写唯一主根因层：

- `compare`
- `output_governance`
- `risk_admission`
- `assembler_web`

允许再补充：

- `rule`
- `model`
- `evidence`

这类补充标签通过 `root_cause_tags` 表达。

## 5. 验收基线

M 验收时，至少检查以下字段：

1. 当前风险标题
2. 当前层级
3. M复核结论
4. 目标动作
5. 根因层级
6. 对应规则编号
7. 对应任务单编号
8. 验收状态
9. 验证通过回放

## 6. 任务单 / 台账 / 回放目录关联

关联规则固定如下：

1. 问题级主源在 `docs/trackers/v2-real-replay-issue-ledger.yaml`
2. 总台账 `docs/trackers/v2-remediation-tracker.md` 负责管理任务状态
3. 每个问题通过 `task_ids` 关联整改任务
4. 每个问题通过 `replay_run_ids` 和 `replay_result_dirs` 关联真实回放
5. 每次回放通过 `replay_closure_index.json` 反向指向问题 ID 与任务 ID

## 7. 维护方式

### T 如何引用

- 收到真实文件反馈后，先新增或更新问题项
- 回写 `problem_type / root_cause_layer / task_ids / replay_run_ids`
- 完成整改回放后，更新 `acceptance_status / acceptance_result`

### M 如何验收

- 先看问题台账中的问题项是否已补齐字段
- 再看对应 `task_ids` 是否与总台账状态一致
- 最后核对 `replay_result_dirs` 与 `replay_closure_index.json`

### 后续新问题如何接入

1. 新增 `issue_id`
2. 归类 `problem_type`
3. 标注 `root_cause_layer`
4. 绑定 `task_ids`
5. 回放完成后补 `replay_run_ids`
6. M 验收通过后回写 `acceptance_status`

## 8. 当前样例

当前已形成最小闭环样例：

- 福州一中宿舍家具文件
- 柴油发电机组文件

对应问题与 run_id 见：

- `docs/trackers/v2-real-replay-issue-ledger.yaml`
- `data/results/v2/20260409-ar2-fuzhou/replay_closure_index.json`
- `data/results/v2/20260409-w011-diesel/replay_closure_index.json`
