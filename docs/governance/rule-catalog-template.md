# 规则总目录模板

## 1. 目标

本目录用于统一管理项目中已经正式入库的规则，解决以下问题：

1. 当前系统到底有哪些规则
2. 每条规则对应什么标准标题和规则码
3. 每条规则归属哪个专题
4. 每条规则当前状态是什么
5. 每条规则对应哪些任务、样本、测试和真实文件基线

本目录既可作为“规则库模板”，也可直接作为第一版规则总表使用。

## 2. 使用原则

1. 只有通过 M 验收的规则，才能进入本目录
2. 每条规则必须绑定唯一规则编号
3. 每条规则必须绑定标准规则码
4. 每条规则必须绑定至少一条样本或测试映射
5. 每条规则如已进入真实文件回放，应补充真实文件基线映射

## 3. 字段说明

| 字段 | 含义 |
| --- | --- |
| 规则编号 | 规则唯一编号，如 `R-001` |
| 规则名称 | 规则的标准名称 |
| 规则码 | compare / regression 统一规则码 |
| 所属专题 | 如 `policy / scoring / technical_standard / acceptance` |
| 风险标题 | 对外输出的标准风险标题 |
| 审查类型 | 标准审查类型 |
| 当前状态 | `已通过 / 已关闭 / 试运行 / 规划中` |
| 来源任务 | 最初落地该规则的任务单 |
| 样本映射 | 对应样本集或样本文件 |
| 测试映射 | 对应测试文件 |
| 真实文件基线 | 已纳入回放的真实文件 |
| 备注 | 特殊说明 |

## 4. 规则总表

| 规则编号 | 规则名称 | 规则码 | 所属专题 | 风险标题 | 审查类型 | 当前状态 | 来源任务 | 样本映射 | 测试映射 | 真实文件基线 | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R-001 | 拒绝进口 vs 外标引用跨专题一致性识别 | `policy_technical_inconsistency` | `policy + technical_standard` | 技术标准引用与采购政策口径不一致，存在潜在倾向性和理解冲突 | 技术标准引用一致性 / 潜在限制竞争 | 已通过 | R-001 | `data/examples/v2_regression_eval_samples.json` | `tests/test_v2_regression_eval.py` | 已纳入 | 当前为跨专题规则 |
| R-002 | 强制性标准条款未按评审规则加注★ | `star_marker_missing_for_mandatory_standard` | `technical_standard / scoring_rule` | 强制性标准条款未按评审规则标注★，可能导致实质性响应边界不清 | 评审规则一致性 / 实质性条款标识完整性 | 已关闭 | R-002 | `data/examples/v2_regression_eval_samples.json` | `tests/test_v2_regression_eval.py` | 已纳入 | 关注 `GB` 与 `GB/T` 区分 |
| R-003 | 不得将项目验收方案作为评审因素 | `acceptance_plan_in_scoring_forbidden` | `scoring` | 将项目验收方案纳入评审因素，违反评审规则合规性要求 | 评分因素合规性 / 评审规则设置合法性 | 已关闭 | R-003 | `data/examples/v2_regression_eval_samples.json` | `tests/test_v2_regression_eval.py` | 已纳入 | 关注评分项与验收方案挂钩 |
| R-004 | 不得将付款方式作为评审因素 | `payment_terms_in_scoring_forbidden` | `scoring / contract_payment` | 将付款方式纳入评审因素，违反评审规则合规性要求 | 评分因素合规性 / 付款条款禁入评分 | 已关闭 | R-004 | `data/examples/v2_regression_eval_samples.json` | `tests/test_v2_regression_eval.py` | 待补更多真实文件 | 当前真实文件未触发 |
| R-005 | 不得要求提供赠品、回扣或者与采购无关的其他商品、服务 | `gifts_or_unrelated_goods_in_scoring_forbidden` | `scoring` | 将赠送额外商品作为评分条件，违反评审规则合规性要求 | 评分因素合规性 / 不当附加交易条件 | 已关闭 | R-005 | `data/examples/v2_regression_eval_samples.json` | `tests/test_v2_regression_eval.py` | 待补更多真实文件 | 已覆盖隐性办公设备/会议保障变体 |
| R-006 | 不得限定或者指定特定的专利、商标、品牌或者供应商 | `specific_brand_or_supplier_in_scoring_forbidden` | `scoring` | 以制造商特定认证证书作为高分条件，存在限定特定供应商和倾向性评分风险 | 评分因素合规性 / 限定特定供应商或认证体系 | 已关闭 | R-006 | `data/examples/v2_regression_eval_samples.json` | `tests/test_v2_regression_eval.py` | 已纳入 | 已完成真实文件标准标题映射 |
| R-007 | 不得要求中标人承担验收产生的检测费用 | `acceptance_testing_cost_shifted_to_bidder` | `acceptance` | 将验收产生的检测费用计入投标人承担范围，存在需求条款合规风险 | 需求合规性 / 验收检测费用转嫁 | 已关闭 | R-007 | `data/examples/v2_regression_eval_samples.json` | `tests/test_v2_regression_eval.py` | 已纳入 | 已完成真实文件标准标题映射 |

## 5. 新规则登记模板

后续新增规则时，建议先按以下表格填写，再决定是否正式入库：

| 规则编号 | 规则名称 | 规则码 | 所属专题 | 风险标题 | 审查类型 | 当前状态 | 来源任务 | 样本映射 | 测试映射 | 真实文件基线 | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R-XXX | <待补规则名称> | `<待补规则码>` | `<待补专题>` | <待补标准标题> | <待补审查类型> | 待下发 | <任务编号> | <待补> | <待补> | <待补> | <待补说明> |

## 6. 维护建议

建议每次规则通过验收后同步更新以下内容：

1. 本目录中的规则总表
2. 对应任务单状态
3. 总台账状态
4. 样本映射
5. 测试映射
6. 真实文件基线映射

## 7. 推荐配套文档

建议配套使用以下文档：

- [project-management-layering-plan.md](/Users/linzeran/code/2026-zn/test_getst/docs/governance/project-management-layering-plan.md)
- [rule-intake-workflow.md](/Users/linzeran/code/2026-zn/test_getst/docs/governance/rule-intake-workflow.md)
- [task-and-acceptance-templates.md](/Users/linzeran/code/2026-zn/test_getst/docs/governance/task-and-acceptance-templates.md)
