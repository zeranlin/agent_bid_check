# 规则注册表字段模板

## 1. 目的

本模板用于统一规则注册表的字段结构，确保后续新增规则时，所有规则都按同一套格式维护，避免：

- 有的规则只有标题，没有排除条件
- 有的规则有任务单，没有样本
- 有的规则已经生效，但没有测试和验收记录

本模板适用于：

- 新规则接入
- 旧规则补强
- 误报抑制规则
- 待补证复核规则

## 2. 推荐存放位置

建议后续规则文件统一存放在：

- `rules/registry/`

例如：

- `rules/registry/R-001.yaml`
- `rules/registry/R-002.yaml`
- `rules/registry/R-003.yaml`

## 3. 推荐字段模板

以下是一份推荐的 YAML 模板：

```yaml
rule_id: R-001
rule_name: 拒绝进口 vs 外标引用
rule_version: 1
status: draft

owner:
  reviewer: M
  implementer: T

source:
  origin_type: business_rule
  origin_desc: 客户新增规则，识别非进口项目中并列外标引用风险
  created_date: 2026-04-02
  last_updated_date: 2026-04-02

classification:
  category: policy_consistency
  rule_type: risk_detection
  target_level: formal
  severity: medium

summary:
  business_goal: 识别非进口项目中采购政策口径、技术标准口径、验收口径不一致的问题
  reviewer_note: 外标引用本身不当然违规，但在明确拒绝进口场景下需要重点审查

trigger_conditions:
  all_of:
    - 存在“不接受进口产品”或“拒绝进口产品”表述
    - 存在 BS/EN/IEC 等国外标准引用
  any_of:
    - 存在“国外生产部件”
    - 存在“原产地证明”

exclude_conditions:
  any_of:
    - 已明确写明“同等标准可接受”
    - 已明确写明“以国标为准，外标仅作参考”
    - 外标不作为技术要求或验收依据

downgrade_conditions:
  any_of:
    - 仅出现国外标准名，但未与采购要求、验收标准、评分标准形成约束关系

output:
  formal_title: 非进口项目中出现国外标准/国外部件相关表述，存在采购政策口径、技术标准口径、验收口径不一致风险
  pending_title: 外标引用与采购政策口径可能存在不一致，建议人工复核
  excluded_title: 外标引用为参考性表述，不构成正式风险
  formal_description: 文件中的非进口采购口径、国外标准引用及国外部件相关表述并存，可能导致供应商对可投范围和验收依据理解不一致。
  remediation_advice: 明确采用国标或说明同等标准可接受，避免外标约束与拒绝进口口径冲突。

evidence_hints:
  keywords:
    - 不接受进口产品
    - BS EN
    - EN55011
    - 原产地证明
    - 国外生产的部件
  sections:
    - 资格要求
    - 技术参数
    - 验收要求

samples:
  positive:
    - data/examples/rules/R-001/positive-01.json
    - data/examples/rules/R-001/positive-02.json
  negative:
    - data/examples/rules/R-001/negative-01.json
  replay:
    - data/examples/real_cases/SZDL2025000495-A/R-001.json

tests:
  unit:
    - tests/rules/test_R_001.py
  replay:
    - tests/replays/test_real_file_R_001.py
  report:
    - tests/reports/test_report_R_001.py

task_refs:
  remediation_tasks:
    - docs/tasks/R-001.md
  followup_tasks:
    - docs/tasks/W-002.md
  acceptance_records:
    - docs/acceptance/R-001-acceptance.md

activation:
  approved_by: M
  approved_date: null
  effective_scope:
    - mature
    - web
    - report

history:
  - version: 1
    date: 2026-04-02
    change: 初始创建
    author: M
```

## 4. 字段说明

### 4.1 基础字段

#### `rule_id`

规则编号，建议统一采用：

- `R-001`
- `R-002`

#### `rule_name`

规则名称，建议短而清晰，便于：

- 台账引用
- 任务单引用
- 搜索与汇报

#### `rule_version`

规则版本号，便于后续规则迭代。

#### `status`

建议值：

- `draft`
- `in_progress`
- `review`
- `active`
- `rejected`
- `deprecated`

## 4.2 责任字段

### `owner.reviewer`

规则口径负责人，通常是 `M`。

### `owner.implementer`

规则实现负责人，通常是 `T`。

## 4.3 来源字段

### `source.origin_type`

建议值：

- `business_rule`
- `real_case_issue`
- `false_positive_fix`
- `law_update`

### `source.origin_desc`

记录规则来源说明，便于后续追溯。

## 4.4 分类字段

### `classification.category`

建议按业务语义分类，例如：

- `policy_consistency`
- `scoring_compliance`
- `technical_bias`
- `contract_boundary`
- `procedure_compliance`

### `classification.rule_type`

建议值：

- `risk_detection`
- `false_positive_suppression`
- `pending_review_rule`

### `classification.target_level`

建议值：

- `formal`
- `pending`
- `excluded`

### `classification.severity`

建议值：

- `high`
- `medium`
- `low`
- `manual_review`

## 4.5 规则逻辑字段

### `trigger_conditions`

定义触发该规则必须满足的条件。

建议支持：

- `all_of`
- `any_of`

### `exclude_conditions`

定义不应触发的条件，是误报治理的关键字段。

### `downgrade_conditions`

定义命中后应降级到待补证复核或提示层的条件。

## 4.6 输出字段

### `output.formal_title`

正式风险标题。

### `output.pending_title`

待补证复核标题。

### `output.excluded_title`

被剔除或降级时的说明标题。

### `output.formal_description`

标准风险说明文案。

### `output.remediation_advice`

标准整改建议。

## 4.7 证据字段

### `evidence_hints.keywords`

推荐的关键词提示，用于后续：

- 召回
- 调试
- 人工排查

### `evidence_hints.sections`

建议优先关注的章节或模块。

## 4.8 样本与测试字段

### `samples`

建议至少分为：

- `positive`
- `negative`
- `replay`

### `tests`

建议至少分为：

- `unit`
- `replay`
- `report`

这样能同时覆盖：

- 规则识别
- 真实文件回放
- 最终报告输出

## 4.9 任务关联字段

### `task_refs.remediation_tasks`

记录主整改任务单。

### `task_refs.followup_tasks`

记录补强任务单。

### `task_refs.acceptance_records`

记录验收单或验收记录。

## 4.10 生效字段

### `activation.approved_by`

谁批准该规则生效。

### `activation.approved_date`

规则正式生效日期。

### `activation.effective_scope`

在哪些输出链路中生效，例如：

- `mature`
- `web`
- `report`

## 4.11 历史字段

### `history`

用于记录规则变更历史，建议至少记录：

- 版本
- 日期
- 改动说明
- 修改人

## 5. 最小必填字段

如果先做 MVP，建议先要求每条规则至少具备以下必填字段：

```yaml
rule_id:
rule_name:
status:
classification:
  category:
  target_level:
trigger_conditions:
exclude_conditions:
output:
  formal_title:
  remediation_advice:
samples:
task_refs:
tests:
```

只要这几个字段不完整，就不允许规则进入 `active`。

## 6. 推荐维护原则

### 原则 1：先保证结构完整，再追求表达精细

宁可先把字段填齐，也不要继续靠聊天记录散落维护。

### 原则 2：规则标题和输出标题分开

`rule_name` 用于治理和维护，  
`formal_title` 用于业务输出。

### 原则 3：必须有负样本

没有负样本的规则，后续极容易变成误报源。

### 原则 4：必须绑定任务单

没有任务单的规则，不应直接入库生效。

### 原则 5：必须能追溯谁批准

任何正式启用的规则，都应记录：

- 谁批准
- 何时批准
- 生效在哪些链路

## 7. 一句话建议

后续规则注册表可以先按这份 YAML 模板落地，先把“字段齐全、结构统一、可追溯”做起来，再逐步做自动生成和自动校验。
