# Governance 文档索引

## 1. 目录定位

`docs/governance/` 用于统一管理项目中的“规则治理机制”文档。

它不直接描述某个具体业务功能，而是描述：

- 新规则如何进入系统
- M / T 如何协作
- 任务单如何生成
- 验收如何执行
- 规则如何正式入库

一句话理解：

`这里管理的是“系统如何持续变强”，不是“系统给客户展示什么功能”。`

## 2. 文档清单

### 2.1 项目管理分层方案

- 文件： [project-management-layering-plan.md](/Users/linzeran/code/2026-zn/test_getst/docs/governance/project-management-layering-plan.md)
- 作用：
  - 定义项目的顶层分层
  - 区分业务功能、规则治理、质量回归、汇报体系
  - 说明后续新增业务功能时，如何与规则治理机制区分

### 2.2 规则接入流程图

- 文件： [rule-intake-workflow.md](/Users/linzeran/code/2026-zn/test_getst/docs/governance/rule-intake-workflow.md)
- 作用：
  - 描述“客户提出新规则”后，如何进入项目治理流程
  - 明确从规则登记、任务编号、开发、验收到规则入库的完整流程
  - 明确 M / T / 客户的职责边界

### 2.3 任务单 / 验收单模板规范

- 文件： [task-and-acceptance-templates.md](/Users/linzeran/code/2026-zn/test_getst/docs/governance/task-and-acceptance-templates.md)
- 作用：
  - 统一任务单模板
  - 统一 T 回传格式
  - 统一 M 验收模板
  - 统一台账状态更新与关单规范

### 2.4 规则总目录模板

- 文件： [rule-catalog-template.md](/Users/linzeran/code/2026-zn/test_getst/docs/governance/rule-catalog-template.md)
- 作用：
  - 统一管理项目中已正式入库的规则
  - 建立规则编号、规则码、专题、样本、测试、真实文件基线之间的映射
  - 当前已内置 `R-001 ~ R-007` 的第一版目录示例

## 3. 推荐阅读顺序

建议按以下顺序阅读：

1. 先看 [project-management-layering-plan.md](/Users/linzeran/code/2026-zn/test_getst/docs/governance/project-management-layering-plan.md)
   - 先理解项目的整体管理分层
2. 再看 [rule-intake-workflow.md](/Users/linzeran/code/2026-zn/test_getst/docs/governance/rule-intake-workflow.md)
   - 理解新规则如何进入治理流程
3. 再看 [task-and-acceptance-templates.md](/Users/linzeran/code/2026-zn/test_getst/docs/governance/task-and-acceptance-templates.md)
   - 理解任务单怎么下发、怎么验收
4. 最后看 [rule-catalog-template.md](/Users/linzeran/code/2026-zn/test_getst/docs/governance/rule-catalog-template.md)
   - 理解规则最终如何正式入库

## 4. 使用建议

后续建议按以下方式使用本目录：

1. 新客户规则提出时
   - 先参考规则接入流程图
2. M 生成任务单时
   - 直接套用任务单模板
3. T 回传后
   - M 按验收模板执行验收
4. 规则通过后
   - 同步更新规则总目录

## 5. 当前适用范围

当前本目录主要服务于：

- 政府采购招标文件风险识别项目
- `R-001 ~ R-007` 等标准规则治理
- `W-002 / W-003` 等真实文件与展示链路治理

后续如果项目新增新的业务域或新的规则体系，本目录可以继续扩展，不需要推翻重建。
