# docs/ 迁移执行清单

## 1. 迁移策略

本清单用于把 `docs/` 迁移拆成可执行批次，避免一次性搬家造成链接大量失效。

## 2. 第一阶段：只补结构和索引

本阶段目标：

- 建立目标目录结构
- 建立 `docs/README.md`
- 建立治理方案、映射表和迁移清单
- 不大规模移动现有文档

本阶段完成标准：

- 新文档已有明确落位规则
- 老文档已有分类映射
- 后续迁移已有批次顺序

## 3. 第二阶段：按批次迁移老文档

当前状态：

- 批次 A、B、C 已在 `DOC-002` 中完成
- 批次 D 仍待后续任务处理

### 批次 A：台账与 backlog

目标：

- 将顶层 tracker / backlog 类文档迁入 `docs/trackers/`

建议文件：

- `v2-remediation-tracker.md`
- `v2-mature-implementation-backlog.md`
- `v2-risk-recall-backlog.md`
- `v2-structure-topic-hardening-backlog.md`
- `v2-regression-hardening-backlog.md`
- `v2-p0-implementation-plan.md`
- `v2-quality-gate-next.md`

风险：

- 被任务单和治理文档广泛引用，迁移后需批量修链接

### 批次 B：复核记录与角色文档

目标：

- 将 review / governance 类顶层文档迁入对应目录

建议文件：

- `szdl2025000495a-review-notes-2026-04-01.md` -> `docs/reviews/`
- `project-roles-and-issue-closure-v1.md` -> `docs/governance/`
- `project-testing-role-and-collaboration-v1.md` -> `docs/governance/`

### 批次 C：架构与汇报文档

目标：

- 将 architecture / report 类顶层文档迁入对应目录

建议文件：

- `v1-architecture.md` -> `docs/architecture/`
- `v2-mature-architecture-plan.md` -> `docs/architecture/`
- `v2-risk-recall-system-plan.md` -> `docs/architecture/`
- `v2-processing-architecture-report.md` -> `docs/reports/`
- `v2-structure-eval-guide.md` -> `docs/reports/`
- `v2-topic-eval-guide.md` -> `docs/reports/`

### 批次 D：模板与归档

目标：

- 将模板类文档迁入 `docs/templates/`
- 将失效或已替代文档迁入 `docs/archive/`

建议文件：

- `docs/governance/rule-registry-field-template.md`
- `docs/governance/task-and-acceptance-templates.md`

## 4. 链接修复策略

每批迁移都执行：

1. 先移动文档
2. 再全仓检索旧路径引用
3. 修复 `docs/` 内部交叉链接
4. 修复任务单、台账、规则注册表中的绝对路径引用
5. 最后跑一次 `rg` 检查残留旧路径

## 5. 建议执行顺序

1. 批次 A
2. 批次 B
3. 批次 C
4. 批次 D

原因：

- 先把台账和 backlog 收敛，最能改善日常查找效率
- 再整理 review / governance，降低角色协作混乱
- 最后迁 architecture / reports，减少大范围链接波动

## 6. 本轮已实施项

本轮已完成：

1. 建立目标目录骨架
2. 建立 `docs/README.md`
3. 建立治理方案文档
4. 建立现状映射表
5. 建立迁移执行清单
6. 完成 tracker / review / governance / architecture / reports 范围内的主要存量文档物理迁移
7. 修复 `docs/` 内部和关键任务单中的主要旧路径引用

本轮未实施：

1. `docs/governance/` 中模板类文档迁入 `docs/templates/`
2. 其他未纳入 `DOC-002` 范围的顶层文档整理
