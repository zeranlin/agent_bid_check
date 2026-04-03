# Docs 总入口

## 1. 目录目标

`docs/` 用于统一承载项目中的长期知识、治理规范、任务单、台账、复核记录、阶段汇报和历史归档。

当前治理原则：

1. 顶层只保留少量入口性文档，避免继续横向堆积
2. 新文档优先按职责进入二级目录
3. 先补结构与索引，再分批迁移老文档并修复链接

## 2. 目标目录结构

```text
docs/
├── README.md
├── architecture/
├── governance/
├── trackers/
├── tasks/
├── reviews/
├── reports/
├── templates/
└── archive/
```

各目录职责：

- [architecture/README.md](https://github.com/zeranlin/agent_bid_check/blob/main/docs/architecture/README.md)
  - 放系统架构、处理链路、分层设计、接口/产物关系说明
  - 以长期有效的“系统如何工作”为主
- [governance/README.md](https://github.com/zeranlin/agent_bid_check/blob/main/docs/governance/README.md)
  - 放规则治理、接入机制、角色协作、目录治理、规范类文档
  - 以“系统如何持续演进”为主
- [trackers/README.md](https://github.com/zeranlin/agent_bid_check/blob/main/docs/trackers/README.md)
  - 放总台账、长期 backlog、路线图、阶段推进看板
  - 以持续更新的任务状态文档为主
- [tasks/](https://github.com/zeranlin/agent_bid_check/blob/main/docs/tasks)
  - 放正式任务单、整改单、补强单、治理实施单
  - 一任务一文档
- [reviews/README.md](https://github.com/zeranlin/agent_bid_check/blob/main/docs/reviews/README.md)
  - 放真实文件复核记录、逐条审查笔记、人工对账说明
  - 以单文件、单批次复核材料为主
- [reports/README.md](https://github.com/zeranlin/agent_bid_check/blob/main/docs/reports/README.md)
  - 放面向汇报、阶段总结、评测说明、处理架构汇报版
  - 以“给人看结果”为主
- [templates/README.md](https://github.com/zeranlin/agent_bid_check/blob/main/docs/templates/README.md)
  - 放文档模板、表格模板、统一输出模板
- [archive/README.md](https://github.com/zeranlin/agent_bid_check/blob/main/docs/archive/README.md)
  - 放历史失效方案、已弃用旧版本、完成迁移后的旧路径保留说明

## 3. 常用文档入口

日常优先看：

- 总台账： [v2-remediation-tracker.md](https://github.com/zeranlin/agent_bid_check/blob/main/docs/trackers/v2-remediation-tracker.md)
- 任务单目录： [tasks/](https://github.com/zeranlin/agent_bid_check/blob/main/docs/tasks)
- 规则治理入口： [governance/README.md](https://github.com/zeranlin/agent_bid_check/blob/main/docs/governance/README.md)
- 文档治理方案： [docs-directory-governance-plan.md](https://github.com/zeranlin/agent_bid_check/blob/main/docs/governance/docs-directory-governance-plan.md)
- 现状分类映射： [docs-inventory-mapping.md](https://github.com/zeranlin/agent_bid_check/blob/main/docs/governance/docs-inventory-mapping.md)
- 迁移执行清单： [docs-migration-checklist.md](https://github.com/zeranlin/agent_bid_check/blob/main/docs/governance/docs-migration-checklist.md)

## 4. 不同角色先看什么

- `M`
  - 先看总台账、任务单、规则治理目录、复核记录
- `T`
  - 先看任务单、架构文档、规则治理文档、回归和汇报说明
- `Q`
  - 先看总台账、评测/回归相关文档、复核记录、任务单
- 新加入成员
  - 先看本 README，再看 `governance/README.md` 与 `tasks/`

## 5. 新文档接入规则

1. 新架构/分层设计文档放 `docs/architecture/`
2. 新规则治理、目录治理、角色协作规范放 `docs/governance/`
3. 新总台账、路线图、长期 backlog 放 `docs/trackers/`
4. 新任务单统一放 `docs/tasks/`
5. 新真实文件复核、人工审查笔记放 `docs/reviews/`
6. 新阶段汇报、面向领导/运营的说明放 `docs/reports/`
7. 新模板放 `docs/templates/`
8. 已失效方案和历史版本放 `docs/archive/`

## 6. 当前迁移状态

当前目录治理已经进入“方案落地 + 首批迁移完成”状态：

1. `DOC-001` 已完成目录治理方案、目录骨架、总入口和分类映射
2. `DOC-002` 已完成首批主要存量文档的物理迁移与关键链接修复
3. `docs/` 顶层已明显收敛，主要存量文档已按职责进入二级目录

当前仍可继续推进的收尾工作：

1. 历史归档文档整理到 `docs/archive/`
2. 模板类文档进一步迁入 `docs/templates/`
3. 小范围残余链接、说明文案和验收回写持续收口

后续迁移与收尾批次继续按 [docs-migration-checklist.md](https://github.com/zeranlin/agent_bid_check/blob/main/docs/governance/docs-migration-checklist.md) 执行。
