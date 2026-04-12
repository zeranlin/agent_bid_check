# V2 真实文件回放矩阵使用说明

## 目的

`docs/trackers/v2-real-replay-matrix.yaml` 是 AXG2 后的真实文件回放验收主源。

它用于：
- 统一维护真实文件的 `document_domain`
- 统一维护 `should_report / should_not_report / should_pending`
- 统一输出 domain 漂移、formal/pending/internal 差异

结果目录仅作为产物，不作为断言主源。

## 运维/运营使用

批量运行：

```bash
python scripts/run_real_replay_matrix.py
```

单文件运行：

```bash
python scripts/run_real_replay_matrix.py --document-id DOC-FUZHOU-DORM-BASELINE
```

运行后重点看：
- `replay_summary.json`
- `replay_assertions.json`
- `final_snapshot.json`
- `final_review.md`

## 差异定位

`replay_summary.json` 至少包含：
- `missing_should_report`
- `unexpected_reported`
- `missing_should_pending`
- `unexpected_pending`
- `mismatched_layers`
- `document_domain`
- `domain_policy_id`
- `budget_policy_id`
- `domain_drift`
- `diff_summary`

其中：
- `domain_drift=true` 表示分域结果与矩阵主源不一致
- `unexpected_reported_titles` 表示误报 formal
- `missing_should_pending_titles` 表示待补证层回退

## 新真实文件接入规范

新增真实文件时，统一追加到 `docs/trackers/v2-real-replay-matrix.yaml`。

每份文件至少补齐：
- `document_id`
- `document_name`
- `file_path`
- `document_domain`
- `topic_mode`
- `seed_result_dir`
- `result_dir`
- `notes`
- `baseline_assertions.should_report`
- `baseline_assertions.should_not_report`
- `baseline_assertions.should_pending`

接入原则：
- `document_domain` 必须先和当前 AX 分类结果对齐
- 断言优先使用稳定标题和 `family_key`
- 不允许把 run 目录内容反向当作主源配置
