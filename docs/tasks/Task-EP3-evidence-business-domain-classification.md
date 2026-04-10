# Task-EP3 证据业务分类补齐任务单

## 基本信息

- 任务编号：`Task-EP3`
- 任务名称：证据业务分类补齐
- 任务类型：`治理架构实施 / 重构任务`
- 当前状态：`待下发`
- 下发对象：`T`
- 监督角色：`M`

## 任务背景

`Task-EP1` 已完成证据层骨架，`Task-EP2` 已完成来源分类。

但如果证据对象还不能稳定回答：

`这段证据在业务上到底属于哪一类`

则系统仍会继续出现以下问题：

1. 资格条件和评分规则混淆
2. 技术参数、技术标准、验收标准、商务义务混挂
3. 样品条款、验收条款、评分条款之间边界漂移
4. 后续问题层难以稳定归并

因此，`Task-EP3` 的核心目标，是在统一 Evidence 对象上补齐 `business_domain`。

本任务只处理“业务归属”，不处理“条款在业务里的角色”与“是否可支撑 formal”，那属于 `Task-EP4`。

## 任务目标

1. 在 Evidence 对象上补齐 `business_domain` 分类能力
2. 让关键业务域之间的证据边界稳定
3. 为问题层提供可归并、可聚类、可解释的证据业务标签
4. 用真实文件验证业务归类的稳定性

## 本任务范围

本任务负责：

1. `business_domain` 分类体系
2. `business_domain` 分类规则或分类器
3. 证据 trace 中的业务归类留痕
4. 真实文件 replay 验证

本任务不负责：

1. `clause_role` 分类
2. `evidence_strength` 判定
3. `hard_evidence` 判定
4. 问题层归并
5. 发布层改造

## 具体整改要求

### 1. 建立 `business_domain` 分类枚举

至少支持以下业务域：

| business_domain | 含义 |
| --- | --- |
| `qualification` | 资格条件 |
| `scoring` | 评分规则 |
| `technical` | 技术参数 |
| `technical_standard` | 技术标准引用 |
| `commercial` | 商务条款 |
| `acceptance` | 验收条款 |
| `policy` | 政策条款 |
| `procedure` | 流程条款 |
| `sample` | 样品要求 |
| `performance_staff` | 业绩 / 人员 / 证书 |

如实现时需要保留 `unknown` 兜底值，可以保留，但不得替代上述主要分类。

### 2. 优先补齐的高价值业务边界

本任务必须优先稳定以下边界：

1. `qualification` vs `scoring`
2. `technical` vs `technical_standard`
3. `commercial` vs `acceptance`
4. `sample` vs `acceptance`
5. `performance_staff` vs `qualification` / `scoring`

### 3. trace 留痕要求

业务分类必须在 trace 中能看到至少以下信息：

1. 最终 `business_domain`
2. 分类命中规则
3. 判定原因
4. 关键上下文信号

### 4. 与后续问题层的承接要求

要求：

1. 后续问题层应能够基于 `business_domain` 做聚类和归并
2. 不允许业务分类结果只停留在日志里
3. Evidence 对象和 topic sections 至少要有可消费字段

### 5. 与现有专题层的最小兼容要求

本任务不要求重写整个专题体系，但至少要做到：

1. `business_domain` 结果可以供 topic_review / compare / 后续问题层消费
2. 不引入现有正式风险明显回退

## 必须补的测试

至少补以下测试：

1. `qualification` 分类测试
2. `scoring` 分类测试
3. `technical` 分类测试
4. `technical_standard` 分类测试
5. `commercial` 分类测试
6. `acceptance` 分类测试
7. `sample` 分类测试
8. `performance_staff` 分类测试
9. 业务分类进入主链路测试

## 真实文件验证要求

至少选 2 份关键真实文件做 replay：

1. 柴油文件
2. 福建物业或福州一中

必须至少验证以下真实业务场景：

1. 资格条件条款
2. 评分规则条款
3. 技术标准条款
4. 商务/验收条款
5. 样品条款

## 交付物要求

至少交付：

1. `business_domain` 枚举或等价定义
2. 业务分类器说明
3. 新增测试清单
4. 真实文件 replay 结果说明
5. 关键边界样例说明

## M 验收标准

### 通过线

满足以下条件可判通过：

1. `business_domain` 分类体系完整
2. 高价值业务边界已有专项测试
3. 业务分类已真实进入主链路
4. 真实文件 replay 已覆盖关键业务场景
5. 关键边界归类有可解释 trace
6. 未打坏当前正式风险稳定性

### 不通过情形

出现以下任一情况，本任务不能通过：

1. 只补了枚举，未进入主链路
2. 资格 / 评分等核心边界仍大量混淆
3. 只有样本，没有真实文件 replay
4. 业务分类无法解释判定原因
5. 引入正式风险回退

## 后续衔接

本任务通过后，下一张任务单按顺序进入：

1. `Task-EP4` 条款角色与硬证据判定补齐

只有业务分类稳定后，条款角色和硬证据判定才不会继续建立在混乱的业务归类上。
