# 候选导入目录

`rules/candidates/imports/` 保存结构化导入后的候选规则批次文件。

每个导入文件至少包含：

1. `batch_id`
2. `source_name`
3. `source_path` 或 `source_description`
4. `candidate_items`

每条候选条目至少包含：

1. `candidate_id`
2. `source_rule_text`
3. `source_category`
