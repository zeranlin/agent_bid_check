# 真实候选规则来源说明（G9）

- 来源名称：`合规性审查点反馈表分层映射清单`
- 来源时间：`2026-04-07`
- 来源路径：`/Users/linzeran/code/2026-zn/test_target/合规性审查点反馈表分层映射清单.md`
- 导入批次：`CAND-IMPORT-2026-04-07-REAL-001`
- 任务单：`Task-G9`
- 来源说明：基于用户指定的真实来源文件开展首轮候选规则分流，不伪造独立来源副本，只在候选池内保留来源索引与治理产物。

## 真实导入说明

- 原文在“反馈表总体情况”中声明唯一审查点约 `150` 个。
- 本轮从 `RP-* / CCK-* / 建议条件化或删除项` 中按治理视角抽取并去重后，形成 `total_candidates = 154` 条首轮候选治理条目。
- 条目数略高于文内统计，是因为本轮同时保留了 `cross-cutting` 能力项、`待删除/退出全国母版` 项和 `建议条件化` 项，便于后续 `G10+` 继续演进。

## 首轮分流统计

- `formal_rule = 84`
- `conditional_rule = 56`
- `capability_item = 12`
- `drop = 2`

## 对应治理文件

- 导入文件：`rules/candidates/imports/candidate_rules_2026-04-07_real_batch_001.yaml`
- 分流台账：`rules/candidates/mappings/candidate_rule_ledger_2026-04-07_real_batch_001.yaml`
- 统计摘要：`rules/candidates/mappings/candidate_rule_triage_summary_2026-04-07_real_batch_001.yaml`
- 分流快照：`rules/candidates/snapshots/SNAP-2026-04-07-triage-002.md`
