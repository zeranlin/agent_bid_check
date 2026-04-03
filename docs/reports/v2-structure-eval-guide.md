# V2 第二层结构评测说明

## 1. 文档定位

本说明用于统一第二层“结构召回与证据聚合”的评测口径，回答三个问题：

- 第二层当前到底测什么
- 第二层变好还是变坏该怎么看
- 第二层改规则后应该跑哪些命令


## 2. 第二层职责

第二层不是直接给最终风险结论，而是负责：

- 把弱结构正文切成稳定 `SectionCandidate`
- 给章节打模块标签与副模块信号
- 为专题层组织 `EvidenceBundle`
- 让第三层尽量少出现“明明文件里有，但证据没送到专题层”的情况

第二层做得好不好，关键看：

- 有没有把关键信息召回出来
- 混合章节有没有被多个专题稳定共享
- 强噪声场景下有没有明显漏掉关键章节


## 3. 当前样本范围

当前结构样本主覆盖族包括：

- `qualification`
- `scoring`
- `contract / acceptance`
- `technical_standard`
- `policy`
- `performance_staff`
- `samples_demo`
- `procedure`

当前样本重点场景包括：

- 标准分章样本
- 混合章节样本
- 表格/附表格式噪声样本
- 无标题/前言式样本
- 目录错乱样本
- 跨页续写样本
- 强噪声样本

当前固定样本文件：

- [data/examples/v2_structure_eval_samples.json](https://github.com/zeranlin/agent_bid_check/blob/main/data/examples/v2_structure_eval_samples.json)
- [data/eval/v2_labels/v2_structure_eval_samples.json](https://github.com/zeranlin/agent_bid_check/blob/main/data/eval/v2_labels/v2_structure_eval_samples.json)


## 4. 关键指标解释

### 4.1 `module_accuracy`

含义：

- 章节主模块识别准确率

关注点：

- 结构切分后，主模块有没有明显判错

典型问题：

- 技术章被判成 procedure
- 商务/验收混排章被整体硬判错


### 4.2 `key_recall`

含义：

- 关键章节召回率

关注点：

- 资格、评分、合同、验收、技术标准等关键章节有没有漏掉

典型问题：

- 评分办法标题变体没被识别
- 附表中的关键章节没被切出来


### 4.3 `coverage_recall_rate`

含义：

- 专题 evidence coverage 命中率

关注点：

- 第二层有没有把第三层真正需要的章节召回进去

典型问题：

- 评分专题只拿到评分章，没拿到资格/附表共享章节
- 技术标准专题没拿到验收抽检章节


### 4.4 `mixed_section_secondary_recall_rate`

含义：

- 混合章节副模块召回率

关注点：

- 一个章节同时属于多个专题时，副模块有没有稳定暴露出来

典型问题：

- “资格 + 评分”只保留了资格
- “商务 + 验收”只保留了商务
- “技术 + 样品 + 评分”只识别到一个主轴


### 4.5 `topic_failure_summary`

含义：

- 哪些专题在结构层 coverage 上最容易出问题

用途：

- 用来决定下一步优先补哪个专题的结构召回


### 4.6 `failure_reason_summary`

含义：

- 当前结构层失败类型分布

常见失败码：

- `missing_titles`
- `primary_order_mismatch`
- `secondary_order_mismatch`
- `shared_topic_unstable`


## 5. 当前推荐门槛

第二层当前建议重点观察：

- `module_accuracy >= 0.90`
- `key_recall >= 0.98`
- `coverage_recall_rate >= 0.97`
- `mixed_section_secondary_recall_rate` 持续提升，不低于当前稳定基线

说明：

- 前三个指标已经更接近“硬门槛”
- 最后一个指标更像持续优化指标，因为混合章节天然更难


## 6. 回跑命令

### 6.1 快速测试

```bash
pytest -q tests/test_v2_structure_eval.py
```

用途：

- 先确认样本文件和评测脚本基本可运行


### 6.2 结构层完整评测

```bash
python scripts/eval_v2_structure.py --dataset-root data/eval --json
```

用途：

- 输出结构层完整 JSON 评测结果


### 6.3 生成可读报告

```bash
python scripts/eval_v2_structure.py --dataset-root data/eval --output-dir .tmp_structure_eval
```

用途：

- 生成 JSON 和 Markdown 报告，方便人工查看


## 7. 评测后的判断顺序

建议按这个顺序看结果：

1. 先看 `key_recall`
2. 再看 `coverage_recall_rate`
3. 再看 `failure_reason_summary`
4. 最后看 `mixed_section_secondary_recall_rate`

原因：

- 如果关键章节没召回，后面指标再漂亮也没意义
- 如果 coverage 没送到第三层，专题层命中率一定受影响
- 副模块召回通常是“更高阶”的优化项


## 8. 调优原则

第二层调优时应遵守：

- 先补样本，再修规则
- 一次只修一类失败原因
- 优先修“固定失败样本”，不做泛化猜测
- 每次改完都回跑结构层评测
- 结构层不能为了追高 `secondary_recall` 大幅牺牲 `module_accuracy`


## 9. 当前阶段结论

截至本轮 `B5 ~ B9` 完成后，第二层结构评测状态可概括为：

- 样本库更厚
- `policy / technical_standard / performance_staff / strong_noise` 覆盖明显增强
- `coverage_recall_rate` 已回到全绿
- 残留的结构层失败已压到 0

下一步若继续优化，重点不再是“大改结构器”，而是：

- 继续补高价值复杂样本
- 用跨层断点样本验证第二层是否真正服务第三层
