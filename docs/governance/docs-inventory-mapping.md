# docs/ 现状文档分类映射表

## 1. 说明

本表用于回答：当前 `docs/` 里有哪些主要文档、它们分别是做什么的、未来应该放到哪里。

说明：

- 本轮只做映射，不大规模迁移
- “建议归属目录”表示目标位置，不代表本轮已移动

## 2. 重点文档映射

| 当前路径 | 文档用途 | 建议归属目录 | 是否建议改名 | 是否建议归档 |
| --- | --- | --- | --- | --- |
| `docs/trackers/v2-remediation-tracker.md` | V2 整改总台账 | `docs/trackers/` | 建议后续改为 `v2-remediation-tracker.md` 原名保留 | 否 |
| `docs/trackers/v2-mature-implementation-backlog.md` | 成熟版实施任务清单 | `docs/trackers/` | 可保留原名 | 否 |
| `docs/trackers/v2-risk-recall-backlog.md` | 风险召回 backlog | `docs/trackers/` | 可保留原名 | 否 |
| `docs/trackers/v2-structure-topic-hardening-backlog.md` | 二三层补强 backlog | `docs/trackers/` | 可保留原名 | 否 |
| `docs/trackers/v2-regression-hardening-backlog.md` | 回归补强 backlog | `docs/trackers/` | 可保留原名 | 否 |
| `docs/reports/v2-processing-architecture-report.md` | V2 处理架构汇报版 | `docs/reports/` | 可保留原名 | 否 |
| `docs/reviews/szdl2025000495a-review-notes-2026-04-01.md` | 真实文件逐条复核记录 | `docs/reviews/` | 建议保留文件名 | 否 |
| `docs/governance/project-roles-and-issue-closure-v1.md` | 项目角色与闭环机制 | `docs/governance/` | 建议后续改为 `project-roles-and-issue-closure.md` | 暂不归档 |
| `docs/governance/project-testing-role-and-collaboration-v1.md` | 测试角色协作机制 | `docs/governance/` | 建议后续改为 `project-testing-role-and-collaboration.md` | 暂不归档 |
| `docs/architecture/v1-architecture.md` | V1 架构说明 | `docs/architecture/` | 可保留原名 | 暂不归档 |
| `docs/v2-annotation-mapping-spec.md` | 埋点/标注映射规范 | `docs/governance/` | 建议后续改为 `v2-annotation-mapping-spec.md` | 否 |
| `docs/architecture/v2-mature-architecture-plan.md` | 成熟架构方案 | `docs/architecture/` | 可保留原名 | 否 |
| `docs/trackers/v2-p0-implementation-plan.md` | P0 实施计划 | `docs/trackers/` | 建议后续改为 `v2-p0-implementation-roadmap.md` | 暂不归档 |
| `docs/trackers/v2-quality-gate-next.md` | 质量门后续计划 | `docs/trackers/` | 建议后续改为 `v2-quality-gate-roadmap.md` | 否 |
| `docs/architecture/v2-risk-recall-system-plan.md` | 风险召回系统方案 | `docs/architecture/` | 可保留原名 | 否 |
| `docs/reports/v2-structure-eval-guide.md` | 结构评测说明 | `docs/reports/` | 建议后续改为 `v2-structure-eval-report-guide.md` | 否 |
| `docs/reports/v2-topic-eval-guide.md` | 专题评测说明 | `docs/reports/` | 建议后续改为 `v2-topic-eval-report-guide.md` | 否 |

## 3. `docs/governance/*` 建议映射

| 当前路径 | 文档用途 | 建议归属目录 | 是否需要改名 | 是否建议归档 |
| --- | --- | --- | --- | --- |
| `docs/governance/README.md` | 治理文档入口 | `docs/governance/` | 否 | 否 |
| `docs/governance/bid-review-processing-architecture.md` | 招标审查处理架构说明 | `docs/architecture/` | 建议后续迁移时改到 `architecture/` | 否 |
| `docs/governance/project-management-layering-plan.md` | 项目管理分层方案 | `docs/governance/` | 否 | 否 |
| `docs/governance/rule-catalog-template.md` | 规则总目录/规则索引 | `docs/governance/` | 否 | 否 |
| `docs/governance/rule-intake-mvp-execution-checklist.md` | 规则接入执行清单 | `docs/governance/` | 否 | 否 |
| `docs/governance/rule-intake-mvp-spec.md` | 规则接入 MVP 方案 | `docs/governance/` | 否 | 否 |
| `docs/governance/rule-intake-workflow.md` | 规则接入流程 | `docs/governance/` | 否 | 否 |
| `docs/governance/rule-registry-field-template.md` | 注册表字段模板 | `docs/templates/` | 建议迁移到 `templates/` | 否 |
| `docs/governance/rule-registry-maintenance-mechanism.md` | 注册表维护机制 | `docs/governance/` | 否 | 否 |
| `docs/governance/task-and-acceptance-templates.md` | 任务/验收模板规范 | `docs/templates/` | 建议迁移到 `templates/` | 否 |
| `docs/governance/v2-rule-and-review-architecture-adjustment.md` | 规则与审查架构调整说明 | `docs/governance/` | 否 | 暂不归档 |
| `docs/governance/v2-rule-governance-implementation-checklist.md` | 规则治理实施清单 | `docs/governance/` | 否 | 否 |

## 4. `docs/tasks/*` 建议映射

`docs/tasks/` 当前职责基本正确，建议继续保留在原目录，不做迁移。

分组建议：

| 文件组 | 用途 | 建议动作 |
| --- | --- | --- |
| `R-*` | 规则整改单 | 保持在 `docs/tasks/` |
| `W-*` | Web / 运行链路整改单 | 保持在 `docs/tasks/` |
| `G-*` / `Task-G*` | 治理架构实施单 | 保持在 `docs/tasks/` |
| `DOC-*` | 文档治理任务单 | 保持在 `docs/tasks/` |
| `Task-G5-FB-*` | 反馈运行单 | 保持在 `docs/tasks/`，后续如增多可再拆子目录 |

## 5. 已完成迁移的重点文档

本轮已完成迁移：

1. `docs/v2-remediation-tracker.md` -> `docs/trackers/v2-remediation-tracker.md`
2. 顶层各类 backlog -> `docs/trackers/`
3. `docs/szdl2025000495a-review-notes-2026-04-01.md` -> `docs/reviews/szdl2025000495a-review-notes-2026-04-01.md`
4. 顶层角色协作文档 -> `docs/governance/`
5. 顶层 architecture / reports 文档 -> `docs/architecture/` 与 `docs/reports/`

后续仍建议迁移：

1. `docs/governance/` 中偏模板的文档 -> `docs/templates/`

## 6. 暂不迁移的文档

本轮建议暂不移动：

1. `docs/tasks/*`
2. 已被大量绝对路径引用的重点文档
3. 正在被并行任务持续修改的文档
