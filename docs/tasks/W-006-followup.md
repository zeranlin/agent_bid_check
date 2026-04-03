# W-006 未通过补强整改单

## 基本信息

- 关联任务：`W-006`
- 整改类型：`未通过后补强`
- 当前状态：`已通过`
- 下发对象：`T`
- 监督角色：`M`

## 未通过结论

`W-006` 本轮验收结论为：`未通过`

本轮不是主清单没有收敛，而是：

1. 正式风险 / 待补证 / 已剔除误报三层在 `comparison` 中已基本分开
2. 但最终交付给业务看的 `review.md` 末尾“综合判断 / 需人工复核事项”仍在回吐旧口径
3. 导致已降级、已剔除的内容在最终成品页重新出现，破坏了本轮分层治理结果

也就是说，这次问题已经不在 compare 聚合本身，而在最终报告装配层。

## 直接证据

### 1. 主清单已经收敛，但总结区仍回流旧内容

当前真实文件结果目录：

- [20260402-133514-w006-default-entry-rerun](https://github.com/zeranlin/agent_bid_check/blob/main/data/results/v2/20260402-133514-w006-default-entry-rerun)

正式风险主清单已经收敛为 10 条，见：

- [review.md](https://github.com/zeranlin/agent_bid_check/blob/main/data/results/v2/20260402-133514-w006-default-entry-rerun/review.md#L14)

但在同一份最终报告末尾，又重新出现以下旧口径：

- 合同模板区旧结论回流，见 [review.md](https://github.com/zeranlin/agent_bid_check/blob/main/data/results/v2/20260402-133514-w006-default-entry-rerun/review.md#L345)
- 澄清截止时间未填、文件容量限制等程序类旧口径回流，见 [review.md](https://github.com/zeranlin/agent_bid_check/blob/main/data/results/v2/20260402-133514-w006-default-entry-rerun/review.md#L346)
- 所属行业未明确、政策导向章节缺失等政策类旧口径回流，见 [review.md](https://github.com/zeranlin/agent_bid_check/blob/main/data/results/v2/20260402-133514-w006-default-entry-rerun/review.md#L347)
- 人员社保豁免、三体系高分值、证据缺失等复核项被再次写成泛化结论，见 [review.md](https://github.com/zeranlin/agent_bid_check/blob/main/data/results/v2/20260402-133514-w006-default-entry-rerun/review.md#L343)

### 2. 当前测试只测 compare 分层，没有测最终成品页

当前 `W-006` 测试主要断言：

- 正式风险列表中不再包含哪些标题
- `pending_review_items` 中应包含哪些标题
- `excluded_risks` 中应包含哪些标题

见：

- [tests/test_w002_real_file.py](https://github.com/zeranlin/agent_bid_check/blob/main/tests/test_w002_real_file.py#L325)

问题在于：

- 这只证明 compare 输出分层正确
- 不能证明最终 `review.md` 的“综合判断 / 需人工复核事项”没有重新拼回旧结论

因此本次属于：

- compare 层基本过线
- report assembler / final markdown renderer 层未过线

## 本次补强目标

1. 让最终 `review.md` 与 compare 分层结果完全一致
2. 禁止 `excluded_risks` 中的条目再次出现在“综合判断 / 需人工复核事项”
3. 禁止旧专题自由摘要绕过分层结果，重新拼回成品页
4. 补一条面向最终报告成品页的自动化测试

## 具体整改要求

### 1. 修复最终报告装配层

重点检查：

- 最终 `review.md` 的“综合判断”如何生成
- “需人工复核事项”是否直接拼接 topic summary / raw summary / baseline summary
- 是否存在未经过 `comparison.metadata.pending_review_items / excluded_risks / clusters` 过滤的自由文本注入

必须满足：

- 正式风险总结，只能基于正式风险主清单生成
- 待补证复核总结，只能基于 `pending_review_items` 生成
- 已剔除误报不得出现在最终成品页结论区
- 不允许旧专题原始总结绕过分层规则直接落入最终报告

### 2. 清理本轮明确禁止回流的内容

以下内容不得再出现在最终 `review.md` 的结论区、综合判断区、需人工复核事项中：

- 合同模板留白导致的付款/履约/验收时限类旧结论
- `澄清截止时间未填写具体日期`
- `采购标的所属行业未明确`
- `人员社保证明要求存在特殊豁免`
- `电子投标文件容量限制可能增加投标负担`

注意：

- 它们可以存在于内部 trace、raw topic 输出、comparison signatures 中
- 但不能再出现在最终业务交付报告里

### 3. 待补证复核区也要受控

以下条目可以保留在待补证复核区：

- `三体系认证设置高分值，需评估与项目履约的关联性`
- `业绩评分内容与采购标的履约能力关联度存疑`
- `项目负责人学历、职称及相关经验被纳入评分因素，需进一步论证其与项目履约能力的直接关联性`
- `具体资格条款缺失，无法判断是否存在排斥性要求`
- `关键人员配置及业绩要求证据缺失，需人工复核`
- `政策导向章节内容缺失，无法确认节能环保等政策落实情况`
- `缺失检测报告及认证要求的具体规定`

但要求：

- 只能以“复核项”形式出现
- 不得在“综合判断”里再写成泛化高风险或正式结论

### 4. 补齐最终成品页测试

必须新增一条或多条测试，直接断言最终 `review.md` 或最终 report markdown：

- 不再包含已剔除误报的总结性表述
- 不再包含 `excluded_risks` 的旧结论回流
- “综合判断”只覆盖正式风险
- “待补证复核项”只覆盖 pending 项

不接受只测 compare、不测最终 markdown 的方案。

## 必须补的测试

### 1. 最终报告回流阻断测试

固定文件：

- `test_target/zf/埋点测试案例和结果/[SZDL2025000495-A]柴油发电机组及相关配套机电设备采购及安装项目.docx`

断言最终 `review.md` 不再出现以下表述或同义回流：

- 付款条款关键数据缺失、履约保证金退还期限未明确、验收期限留白
- 澄清截止时间未填写具体日期
- 采购标的所属行业未明确
- 人员社保证明特殊豁免
- 电子投标文件容量限制可能增加投标负担

### 2. 最终报告分层一致性测试

断言：

- 最终正式风险区仅对应 `comparison.clusters`
- 最终待补证复核区仅对应 `comparison.metadata.pending_review_items`
- `comparison.metadata.excluded_risks` 中条目不再进入最终业务报告结论区

### 3. 旧摘要绕过拦截测试

若 topic summary / baseline summary 中含有已剔除条目，断言：

- 最终报告不会直接原样拼接这些旧摘要
- 渲染阶段会按最终分层结果重写或过滤

## 交付物要求

T 提交时必须附：

1. 改了哪些最终报告装配文件
2. 最终报告装配逻辑是如何改的
3. 新增了哪些针对最终 markdown 的测试
4. 新的真实文件结果目录
5. 一份“整改前后最终 review.md 结论区对照表”

## M 验收标准

### 通过线

- 最终 `review.md` 不再回流已剔除误报
- “综合判断 / 需人工复核事项”与 compare 分层结果一致
- 已降级条目只出现在待补证复核区，不再被写成正式结论
- 自动化测试直接覆盖最终业务报告，而不只是 compare 数据结构

### 不通过情形

- 主清单虽然正确，但最终报告末尾仍回流旧口径
- `excluded_risks` 内容仍出现在最终结论区
- 只改测试数据，不改最终渲染逻辑
- 只证明 compare 正确，不证明最终业务报告正确
