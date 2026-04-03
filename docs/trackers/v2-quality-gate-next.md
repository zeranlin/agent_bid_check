# V2 下一阶段质量门建议

## 1. 文档定位

这份文档用于整理 V2 当前已经稳定达到的评测结果，并据此给出下一阶段建议门槛。

目标不是“把门槛调到刚好能过”，而是形成一套后续可持续使用的质量门：

- 第一层看结构识别与证据召回是否稳
- 第二层看专题与细节风险是否稳
- 第三层看汇总去重与覆盖分析是否稳
- 联动层看跨层主回归是否稳
- 断点样本看失败定位是否清晰


## 2. 当前稳定结果快照

基于 2026-03-31 当前仓库执行结果：

- 结构层：`python scripts/eval_v2_structure.py --dataset-root data/eval --json`
- 专题层：`python scripts/eval_v2_topics.py --dataset-root data/eval --json`
- 汇总层：`python scripts/eval_v2_compare.py --dataset-root data/eval --json`
- 主回归：`python scripts/eval_v2_all.py --dataset-root data/eval --json`
- 细节批次：`python scripts/eval_v2_detail_batch.py --json`

当前稳定指标如下：

| 层级 | 指标 | 当前值 |
| --- | --- | --- |
| 第一层 | `module_accuracy` | `0.9307` |
| 第一层 | `key_recall` | `1.0000` |
| 第一层 | `coverage_recall_rate` | `1.0000` |
| 第一层 | `negative_pass_rate` | `1.0000` |
| 第一层 | `mixed_section_secondary_recall_rate` | `0.8916` |
| 第二层 | `high_medium_hit_rate` | `1.0000` |
| 第二层 | `topic_hit_rate` | `1.0000` |
| 第二层 | `false_positive_rate` | `0.0000` |
| 第二层 | `manual_review_expected_rate` | `1.0000` |
| 第三层 | `accuracy` | `1.0000` |
| 联动主回归 | `structure_hit_rate` | `0.8000` |
| 联动主回归 | `topic_coverage_hit_rate` | `0.8000` |
| 联动主回归 | `risk_hit_rate` | `0.8000` |
| 联动主回归 | `miss_rate` | `0.2000` |
| 细节批次 | `topic_hit_rate` | `1.0000` |
| 细节批次 | `false_positive_rate` | `0.0000` |
| 细节批次 | `manual_review_expected_rate` | `1.0000` |

说明：

- 结构层当前最接近边界的指标仍是 `mixed_section_secondary_recall_rate=0.8916`
- 主回归层当前是“贴线通过”，四个指标都刚好卡在门槛边缘
- 专题层、汇总层、细节批次目前表现更宽裕，但样本仍需继续扩充


## 3. 下一阶段门禁建议

### 3.1 第一层硬门禁

建议继续采用“稳态门槛”：

- `module_accuracy >= 0.90`
- `key_recall >= 0.98`
- `coverage_recall_rate >= 0.98`
- `negative_pass_rate >= 0.98`
- `mixed_section_secondary_recall_rate >= 0.88`

原因：

- 当前结构层已经明显高于旧门槛
- 但 `secondary recall` 仍是第一层最脆弱指标，不宜一次拉太高
- 下一阶段先把第一层门槛抬到“有压力但不会频繁误杀”的水平更合理


### 3.2 第二层硬门禁

建议下一阶段专题层门槛：

- `high_medium_hit_rate >= 0.98`
- `topic_hit_rate >= 0.98`
- `false_positive_rate = 0`
- `manual_review_expected_rate >= 0.95`

补充观察项：

- `failure_reason_summary` 继续保留为趋势项，不单独卡死
- 若 `cross_topic_shared_but_single_topic_hit`、`topic_triggered_but_partial_miss` 明显升高，应触发人工复核


### 3.3 第三层硬门禁

建议维持：

- `accuracy >= 0.95`

补充观察项：

- `topic_only_count`
- `baseline_only_count`
- `coverage_gap_count`
- `conflict_count`

原因：

- 第三层当前样本规模仍偏小，先不建议把门槛继续抬高
- 先通过扩样提升监督厚度，再决定是否把 `accuracy` 拉到 `0.98`


### 3.4 联动主回归硬门禁

建议把“主回归硬门禁”和“断点诊断门禁”拆开：

主回归硬门禁继续使用：

- `structure_hit_rate >= 0.80`
- `topic_coverage_hit_rate >= 0.80`
- `risk_hit_rate >= 0.80`
- `miss_rate <= 0.20`

说明：

- 主回归目前只是刚过线，不能再抬
- 下一阶段优先目标不是先抬主回归门槛，而是先把贴线项拉出安全裕量


### 3.5 断点诊断门禁

新增建议：

- 断点样本集单独执行，不并入主回归硬门禁
- 目标不是“全部通过”，而是“失败归因必须正确”

建议检查项：

- `coverage_gap_after_section_recall` 应归因到 `coverage/structure`
- `topic_miss_after_recall` 应归因到 `topic`
- `manual_review_boundary_after_recall` 应归因到 `topic`
- Markdown 失败报告必须展示：
  - 当前失败点
  - 已召回章节
  - 应命中专题
  - 应命中风险

推荐命令：

```bash
python scripts/eval_v2_regression.py --samples data/examples/v2_regression_breakpoint_samples.json --text
```


### 3.6 细节风险专项门禁

新增建议把 `detail batch` 作为第二层快速回归门：

- 标准类细节风险批次
- 评分类细节风险批次
- 资格类细节风险批次
- 付款类细节风险批次

建议门槛：

- 每个批次 `topic_hit_rate >= 0.95`
- 每个批次 `false_positive_rate = 0`
- 每个批次 `manual_review_expected_rate >= 0.95`
- 任何批次 `missing_sample_ids` 必须为 `[]`

推荐命令：

```bash
python scripts/eval_v2_detail_batch.py --json
```


## 4. 推荐执行顺序

每次涉及结构规则、专题 prompt、专题后处理、compare 合并逻辑改动后，建议按下面顺序执行：

1. `pytest -q tests/test_v2_structure_eval.py tests/test_v2_topics_eval.py tests/test_v2_compare_eval.py tests/test_v2_regression_eval.py tests/test_v2_detail_batch.py`
2. `python scripts/eval_v2_detail_batch.py --json`
3. `python scripts/eval_v2_regression.py --samples data/examples/v2_regression_breakpoint_samples.json --text`
4. `python scripts/eval_v2_all.py --dataset-root data/eval --json`

解释：

- 第 2 步先回答“这次改动有没有让细节风险变坏”
- 第 3 步再回答“如果坏了，断在第几层”
- 第 4 步最后确认是否还能通过整体质量门


## 5. 使用建议

后续建议把 V2 质量门分成三类：

- `发布门`
  - 看 `eval_v2_all.py`
- `专题调优门`
  - 看 `eval_v2_detail_batch.py`
- `问题定位门`
  - 看 `v2_regression_breakpoint_samples.json`

这样可以避免再出现下面两类误判：

- 为了补诊断样本，把主回归门禁拉红
- 只看总通过率，却不知道问题断在结构层还是专题层


## 6. 当前结论

当前 V2 已具备下一阶段门禁基础，但建议采用“双轨制”：

- 主回归集负责“是否通过”
- 断点样本集负责“失败归因”

如果继续推进下一轮结构层和专题层细化优化，优先顺序建议为：

1. 扩结构层强噪声与跨章节共享样本
2. 扩专题层细节负样本与灰区样本
3. 扩第三层 compare 样本规模
4. 在主回归指标脱离贴线状态后，再考虑提高主回归门槛
