# V2 第三层专题评测说明

## 1. 文档定位

本说明用于统一第三层“专题深审与细节风险抽取”的评测口径，回答四个问题：

- 第三层当前评测什么
- 第三层哪些专题已经有固定样本
- 第三层变好还是变坏该怎么看
- 第三层改 prompt 或后处理后应该回跑什么


## 2. 第三层职责

第三层不负责重新切文档，而是基于第二层送来的 `EvidenceBundle` 做专题深审，主要负责：

- 从已召回证据中抽出真实风险点
- 区分明确风险与需人工复核事项
- 对细节型风险给出更稳定的专题判断
- 在模型漏抽时，用轻量后处理补回一部分明确风险

第三层做得好不好，关键看：

- 章节已召回时，风险有没有真正抽出来
- 对细节型风险有没有稳定命中
- 是否把明确风险错误降成了人工复核
- 轻量兜底是否带来误报


## 3. 当前专题覆盖

当前固定样本已重点覆盖：

- `qualification`
- `scoring`
- `technical_standard`
- `contract_payment`

当前重点细节风险包括：

- 标准名称与编号不一致
- 引用已废止标准
- 本地服务机构要求
- 人员/业绩条件被抬成资格门槛
- 评分档次缺少量化口径
- 主观分值裁量空间过大
- 评分依据与采购标的关联性不足
- 评分口径前后不一致
- 付款与财政资金到位挂钩
- 付款安排以验收裁量为前置条件
- 付款节点明显偏后

当前固定样本文件：

- [data/examples/v2_topic_eval_samples.json](/Users/linzeran/code/2026-zn/test_getst/data/examples/v2_topic_eval_samples.json)
- [data/eval/v2_labels/v2_topic_eval_samples.json](/Users/linzeran/code/2026-zn/test_getst/data/eval/v2_labels/v2_topic_eval_samples.json)


## 4. 关键指标解释

### 4.1 `topic_hit_rate`

含义：

- 当前目标专题的风险命中率

关注点：

- 给定专题后，应命中的风险标题有没有真正命中


### 4.2 `high_medium_hit_rate`

含义：

- 所有高风险/中风险目标的总体命中率

关注点：

- 关键风险是否稳定抽出


### 4.3 `technical_hit_rate`

含义：

- 技术标准相关风险命中率

关注点：

- 技术标准类细节问题是否稳定识别


### 4.4 `false_positive_rate`

含义：

- 负样本误报率

关注点：

- 轻量兜底规则是否变成误报源


### 4.5 `manual_review_expected_rate`

含义：

- 预期需要人工复核的样本，是否真的被标成了人工复核

关注点：

- 是否错误把“本应保守处理”的情况直接定成明确风险


### 4.6 `failure_reason_summary`

含义：

- 当前第三层失败原因分布

当前重点原因码包括：

- `missing_evidence`
- `degraded_to_manual_review`
- `risk_degraded_to_manual_review`
- `risk_not_extracted`
- `evidence_enough_but_risk_missed`
- `topic_triggered_but_partial_miss`
- `cross_topic_shared_but_single_topic_hit`


## 5. 当前失败原因码解释

### 5.1 `missing_evidence`

说明：

- 当前证据不足，无法稳定抽出明确风险

典型场景：

- 评分附表缺失
- 合同付款比例缺失
- 标准适用范围缺少上下文


### 5.2 `degraded_to_manual_review`

说明：

- 当前专题结果整体降级为人工复核


### 5.3 `risk_degraded_to_manual_review`

说明：

- 已经看到了可疑风险，但因关键证据缺口，仍被保守降级为人工复核


### 5.4 `risk_not_extracted`

说明：

- 模型初始输出没有完整抽出风险，后处理补回了风险


### 5.5 `evidence_enough_but_risk_missed`

说明：

- 证据基本已经足够，但模型初始完全没抽出风险


### 5.6 `topic_triggered_but_partial_miss`

说明：

- 模型已经抽出部分风险，但仍漏掉同专题下其他风险


### 5.7 `cross_topic_shared_but_single_topic_hit`

说明：

- 同一证据片段同时承载多个专题信号，但模型只命中了其中一部分


## 6. 当前推荐门槛

第三层当前建议重点观察：

- `topic_hit_rate >= 0.95`
- `high_medium_hit_rate >= 0.95`
- `technical_hit_rate >= 0.95`
- `false_positive_rate = 0`
- `manual_review_expected_rate = 1.0`

说明：

- 第三层最大的风险不是“跑不出来”，而是“命中不稳”或“误报升高”
- 因此专题层调优必须同时看命中率和误报率


## 7. 回跑命令

### 7.1 快速测试

```bash
pytest -q tests/test_v2_topics_eval.py
```

用途：

- 确认专题样本、评测脚本基本正常


### 7.2 专题层完整评测

```bash
python scripts/eval_v2_topics.py --dataset-root data/eval --json
```

用途：

- 输出专题层完整 JSON 结果


### 7.3 生成可读报告

```bash
python scripts/eval_v2_topics.py --dataset-root data/eval --output-dir .tmp_topics_eval
```

用途：

- 生成 JSON 和 Markdown 报告，方便人工阅读


### 7.4 第三层关键回归测试

```bash
pytest -q tests/test_v2_topics_eval.py tests/test_v2_pipeline.py -k 'scoring_postprocess or qualification_postprocess or contract_postprocess or topic_failure_reasons or tightens_manual_review'
```

用途：

- 验证轻量兜底和 failure reason 是否稳定


## 8. 评测后的判断顺序

建议按这个顺序看结果：

1. 先看 `topic_hit_rate`
2. 再看 `false_positive_rate`
3. 再看 `manual_review_expected_rate`
4. 最后看 `failure_reason_summary`

原因：

- 命中率先说明“能不能找到”
- 误报率说明“会不会乱报”
- 人工复核命中率说明“会不会乱定性”
- failure reason 说明“下一步该改哪里”


## 9. 调优原则

第三层调优时应遵守：

- 先补样本，再补后处理
- 轻量兜底只补强规则性明确的问题
- 一条兜底规则必须有对应样本支撑
- 不允许为了追高命中率明显拉高误报率
- 不能把大量不确定问题一律改成明确风险


## 10. 当前阶段结论

截至本轮 `C5 ~ C10` 完成后，第三层可概括为：

- 样本库更厚
- 资格、评分、技术标准、付款专题的细节风险覆盖明显增强
- “章节已召回但风险未抽出”已形成更细 failure reason 分型
- 轻量兜底规则已开始覆盖评分相关性、评分口径矛盾等细节问题

下一步若继续优化，重点不是盲目加规则，而是：

- 继续补跨专题共享证据样本
- 继续补“需人工复核”与“明确风险”边界样本
- 用跨层断点样本验证第二层与第三层的衔接质量
