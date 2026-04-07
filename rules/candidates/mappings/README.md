# 候选分流台账目录

`rules/candidates/mappings/` 保存候选规则分流台账。

候选规则分流台账核心字段：

- `candidate_id`
- `source_name`
- `source_rule_text`
- `source_category`
- `decision`
- `decision_reason`
- `target_rule_id`
- `target_layer`
- `profile_dependency`
- `negative_conditions`
- `samples_status`
- `tests_status`
- `task_id`
- `status`
- `snapshot_id`

字段口径说明：

- `decision`：仅允许 `formal_rule / conditional_rule / capability_item / drop`
- `target_layer`：记录建议落层，如 `formal_risks / pending_review_items / excluded_risks / capability`
- `profile_dependency`：记录是否依赖品类、地区、采购画像等前置条件
- `negative_conditions`：记录负样本、排除条件或不触发边界
- `samples_status`：`missing / seeded / ready`
- `tests_status`：`missing / seeded / ready`
- `status`：`new / triaged / in_progress / accepted / rejected / migrated`
