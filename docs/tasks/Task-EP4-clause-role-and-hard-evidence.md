# Task-EP4 条款角色与硬证据判定补齐任务单

## 基本信息

- 任务编号：`Task-EP4`
- 任务名称：条款角色与硬证据判定补齐
- 任务类型：`治理架构实施 / 重构任务`
- 当前状态：`待下发`
- 下发对象：`T`
- 监督角色：`M`

## 任务背景

`Task-EP3` 完成后，系统应已具备：

1. 证据来源分类
2. 证据业务分类

但仅有来源和业务归属仍然不够。

系统还必须继续回答：

1. 这条证据在业务里扮演什么角色
2. 这条证据强不强
3. 这条证据是否有资格支撑正式风险

否则即使证据已经被归到正确业务域，系统仍然会继续出现：

1. 资格门槛和评分因素混在一起使用
2. 一般说明、材料要求、提醒事项被误当成 formal 支撑证据
3. 模板条款、附件材料、辅助条款仍可能被抬成正式风险

因此，`Task-EP4` 的目标，是在统一 Evidence 对象上补齐：

1. `clause_role`
2. `evidence_strength`
3. `hard_evidence`

并与后续准入层形成可消费的稳定接口。

## 任务目标

1. 补齐 Evidence 的条款角色分类
2. 补齐证据强弱判定
3. 补齐 `hard_evidence` 基础规则
4. 让后续准入层能够更稳定拦截弱证据与非正式支撑证据

## 本任务范围

本任务负责：

1. `clause_role` 分类体系
2. `evidence_strength` 判定
3. `hard_evidence` 判定
4. 与后续准入层的最小联动
5. 真实文件 replay 验证

本任务不负责：

1. 问题层归并
2. 发布层改造
3. 规则注册表扩展

## 具体整改要求

### 1. 建立 `clause_role` 分类枚举

至少支持以下角色：

| clause_role | 含义 |
| --- | --- |
| `gate` | 准入门槛 |
| `scoring_factor` | 评分因素 |
| `technical_requirement` | 技术要求 |
| `acceptance_basis` | 验收依据 |
| `commercial_obligation` | 商务义务 |
| `supporting_material` | 证明材料要求 |
| `reminder` | 提醒 / 待补证提示 |

如实现时需要保留 `unknown` 兜底值，可以保留，但不得替代上述主要角色。

### 2. 建立 `evidence_strength` 判定

至少应支持：

| evidence_strength | 含义 |
| --- | --- |
| `weak` | 弱证据 |
| `medium` | 中等证据 |
| `strong` | 强证据 |

判定应综合考虑：

1. 是否为正文硬条款
2. 是否有完整上下文
3. 是否有明确约束动作
4. 是否只是提醒、模板或格式说明

### 3. 建立 `hard_evidence` 判定

要求：

1. `hard_evidence` 不能只等于“正文 + 长文本”
2. 必须结合：
   - `source_kind`
   - `business_domain`
   - `clause_role`
   - `evidence_strength`
3. 至少形成第一版可解释规则

### 4. 优先覆盖的高价值角色场景

本任务必须优先稳定以下场景：

1. 资格门槛
2. 评分因素
3. 技术标准要求
4. 验收依据
5. 商务义务
6. 证明材料要求
7. 提醒项

### 5. 与准入层的最小联动

本任务必须证明：

1. `clause_role`、`evidence_strength`、`hard_evidence` 已能供后续准入层消费
2. 至少能解释“为什么某条证据可/不可支撑 formal”
3. 不允许后续 `risk_admission` 仍只能粗暴地以正文/非正文判断

### 6. trace 留痕要求

至少保留：

1. `clause_role`
2. `evidence_strength`
3. `hard_evidence`
4. 判定原因
5. 命中规则或命中信号

## 必须补的测试

至少补以下测试：

1. `gate` 分类测试
2. `scoring_factor` 分类测试
3. `technical_requirement` 分类测试
4. `acceptance_basis` 分类测试
5. `commercial_obligation` 分类测试
6. `supporting_material` 分类测试
7. `reminder` 分类测试
8. `weak / medium / strong` 判定测试
9. `hard_evidence=true/false` 判定测试
10. 可被准入层消费测试

## 真实文件验证要求

至少用 2 份关键真实文件验证：

1. 柴油文件
2. 福建物业或福州一中

至少验证以下场景：

1. 正文硬门槛
2. 评分项
3. 技术标准
4. 验收依据
5. 商务义务
6. 材料要求
7. 提醒项降级

## 交付物要求

至少交付：

1. `clause_role` 枚举或等价定义
2. `evidence_strength` 判定说明
3. `hard_evidence` 判定说明
4. 新增测试清单
5. 真实文件 replay 结果说明
6. 典型正负边界案例说明

## M 验收标准

### 通过线

满足以下条件可判通过：

1. `clause_role` 体系完整
2. `evidence_strength` 已形成稳定第一版规则
3. `hard_evidence` 已形成可解释判定
4. 关键角色场景有专项测试
5. 至少 2 份真实文件 replay 已验证
6. 后续准入层已能消费这些结果
7. 未打坏当前正式风险输出

### 不通过情形

出现以下任一情况，本任务不能通过：

1. 只有字段，没有真正分类逻辑
2. `hard_evidence` 仍然等同于“正文长文本”
3. 只有样本测试，没有真实文件 replay
4. 条款角色和证据强弱无法解释判定依据
5. 本任务引入正式风险回退

## 后续衔接

本任务通过后，下一张任务单按顺序进入：

1. `Task-PB1` 问题层骨架搭建

只有证据来源、业务归类、条款角色、硬证据四件事都稳定后，问题层重构才真正有稳定输入对象可用。
