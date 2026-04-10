# Candidate Rule Governance Rollout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不污染当前正式规则库的前提下，落地候选规则池、分流台账、快照回滚机制，以及首批纳管任务骨架，支撑后续把外部 150 条审查点安全接入项目治理体系。

**Architecture:** 本次实施分三段推进。第一段建立 `rules/candidates/` 候选池目录和标准化台账模板，先接住外部规则但不进入运行链路。第二段补齐候选批次快照、状态流转与校验测试，确保新增治理资产失败后可回退。第三段产出 `Task-G6 / Task-G7 / Task-G8` 任务单、台账挂载和首批纳管入口，让后续规则接入按统一流程推进。

**Tech Stack:** Markdown, YAML, JSON Schema-compatible rule files, Python pytest, existing rule governance scripts

---

## File Structure

### New files

- `rules/candidates/README.md`
- `rules/candidates/sources/README.md`
- `rules/candidates/imports/README.md`
- `rules/candidates/mappings/README.md`
- `rules/candidates/snapshots/README.md`
- `rules/candidates/imports/candidate_rules_2026-04-07_seed.yaml`
- `rules/candidates/mappings/candidate_rule_mapping_2026-04-07.yaml`
- `rules/candidates/snapshots/SNAP-2026-04-07-bootstrap-001.md`
- `docs/governance/candidate-rule-triage-criteria.md`
- `docs/templates/candidate-rule-mapping-template.md`
- `docs/tasks/Task-G6-candidate-rule-triage-and-ledger.md`
- `docs/tasks/Task-G7-candidate-rule-snapshot-and-rollback.md`
- `docs/tasks/Task-G8-first-batch-candidate-rule-migration.md`
- `tests/test_candidate_rule_governance.py`

### Modified files

- `docs/trackers/v2-remediation-tracker.md`
- `docs/README.md`
- `rules/README.md`
- `rules/tools/README.md`
- `scripts/validate_rule_registry.py`

### Existing references to read while implementing

- `docs/governance/candidate-rule-intake-and-migration-design.md`
- `docs/governance/rule-registry-maintenance-mechanism.md`
- `docs/governance/rule-registry-field-template.md`
- `docs/tasks/Task-G1-governance-foundation.md`
- `docs/tasks/Task-G3-first-batch-rule-migration.md`
- `rules/templates/rule_template.yaml`
- `tests/test_rule_governance.py`

### Verification commands used across tasks

- `pytest -q tests/test_candidate_rule_governance.py`
- `pytest -q tests/test_rule_governance.py tests/test_rule_registry_first_batch.py`
- `python scripts/validate_rule_registry.py`

## Task 1: 建立候选规则池目录与说明文档

**Files:**
- Create: `rules/candidates/README.md`
- Create: `rules/candidates/sources/README.md`
- Create: `rules/candidates/imports/README.md`
- Create: `rules/candidates/mappings/README.md`
- Create: `rules/candidates/snapshots/README.md`
- Modify: `rules/README.md`
- Test: `tests/test_candidate_rule_governance.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path


def test_candidate_rule_directories_and_readmes_exist():
    required_paths = [
        Path("rules/candidates/README.md"),
        Path("rules/candidates/sources/README.md"),
        Path("rules/candidates/imports/README.md"),
        Path("rules/candidates/mappings/README.md"),
        Path("rules/candidates/snapshots/README.md"),
    ]

    missing = [str(path) for path in required_paths if not path.exists()]
    assert not missing, f"missing candidate governance docs: {missing}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest -q tests/test_candidate_rule_governance.py -k directories`
Expected: FAIL with missing `rules/candidates/...` paths.

- [ ] **Step 3: Write minimal implementation**

Create `rules/candidates/README.md` with:

```md
# Candidate Rule Pool

`rules/candidates/` 用于承接外部导入的候选审查点。

这里的内容只用于接入、分流、追踪和回滚，不直接进入正式运行链路。

目录说明：

- `sources/`：来源副本或整理摘录
- `imports/`：标准化导入结果
- `mappings/`：候选规则分流台账
- `snapshots/`：导入、分流、迁移快照
```

Create `rules/candidates/sources/README.md` with:

```md
# Candidate Sources

保存外部候选规则来源副本或摘录。

要求：

- 保留来源名称与时间
- 不直接参与运行
- 用于回溯原始语义
```

Create `rules/candidates/imports/README.md` with:

```md
# Candidate Imports

保存某次导入后的结构化候选清单。

要求：

- 以批次命名
- 不直接代表正式规则
- 与快照和分流台账可追踪关联
```

Create `rules/candidates/mappings/README.md` with:

```md
# Candidate Mappings

保存候选规则分流台账。

核心用途：

- 记录候选编号
- 记录分流结论
- 记录任务单、样本、测试和迁移状态
```

Create `rules/candidates/snapshots/README.md` with:

```md
# Candidate Snapshots

保存候选规则治理过程中的批次快照。

每个快照至少应包含：

- 批次编号
- 输入来源
- 分流范围
- 任务单范围
- 状态摘要
```

Update `rules/README.md` by adding one bullet:

```md
- `candidates/`：候选规则池，承接外部规则导入、分流、快照与回滚
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest -q tests/test_candidate_rule_governance.py -k directories`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add rules/candidates rules/README.md tests/test_candidate_rule_governance.py
git commit -m "搭建候选规则池目录骨架"
```

## Task 2: 落地候选规则导入样板与分流台账模板

**Files:**
- Create: `rules/candidates/imports/candidate_rules_2026-04-07_seed.yaml`
- Create: `rules/candidates/mappings/candidate_rule_mapping_2026-04-07.yaml`
- Create: `docs/templates/candidate-rule-mapping-template.md`
- Create: `docs/governance/candidate-rule-triage-criteria.md`
- Modify: `docs/README.md`
- Test: `tests/test_candidate_rule_governance.py`

- [ ] **Step 1: Write the failing test**

```python
import yaml
from pathlib import Path


def test_candidate_seed_import_and_mapping_have_required_fields():
    import_path = Path("rules/candidates/imports/candidate_rules_2026-04-07_seed.yaml")
    mapping_path = Path("rules/candidates/mappings/candidate_rule_mapping_2026-04-07.yaml")

    imports_data = yaml.safe_load(import_path.read_text(encoding="utf-8"))
    mapping_data = yaml.safe_load(mapping_path.read_text(encoding="utf-8"))

    assert "batch_id" in imports_data
    assert "candidates" in imports_data and imports_data["candidates"]
    assert "snapshot_id" in mapping_data
    assert "items" in mapping_data and mapping_data["items"]

    first_item = mapping_data["items"][0]
    for key in [
        "candidate_id",
        "source_name",
        "source_rule_text",
        "decision",
        "status",
    ]:
        assert key in first_item
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest -q tests/test_candidate_rule_governance.py -k seed_import`
Expected: FAIL because candidate import and mapping files do not exist.

- [ ] **Step 3: Write minimal implementation**

Create `rules/candidates/imports/candidate_rules_2026-04-07_seed.yaml` with:

```yaml
batch_id: IMPORT-2026-04-07-001
source_name: 合规性审查点反馈表分层映射清单
source_path: test_target/合规性审查点反馈表分层映射清单.md
candidates:
  - candidate_id: CR-001
    source_rule_text: 不得将项目验收方案作为评审因素
    source_category: 评审因素
  - candidate_id: CR-002
    source_rule_text: 不得将付款方式作为评审因素
    source_category: 评审因素
  - candidate_id: CR-003
    source_rule_text: 不得要求提供赠品、回扣或者与采购无关的其他商品、服务
    source_category: 评分合规
```

Create `rules/candidates/mappings/candidate_rule_mapping_2026-04-07.yaml` with:

```yaml
snapshot_id: SNAP-2026-04-07-bootstrap-001
source_batch_id: IMPORT-2026-04-07-001
items:
  - candidate_id: CR-001
    source_name: 合规性审查点反馈表分层映射清单
    source_rule_text: 不得将项目验收方案作为评审因素
    source_category: 评审因素
    decision: formal_rule
    decision_reason: 已有稳定业务口径，且现有 R-003 可承接
    target_rule_id: R-003
    target_layer: 正式风险
    profile_dependency: false
    negative_conditions: 已定义
    samples_status: 已验证
    tests_status: 已通过
    task_id: R-003
    status: migrated
    snapshot_id: SNAP-2026-04-07-bootstrap-001
  - candidate_id: CR-002
    source_name: 合规性审查点反馈表分层映射清单
    source_rule_text: 不得将付款方式作为评审因素
    source_category: 评审因素
    decision: formal_rule
    decision_reason: 已有稳定业务口径，且现有 R-004 可承接
    target_rule_id: R-004
    target_layer: 正式风险
    profile_dependency: false
    negative_conditions: 已定义
    samples_status: 已验证
    tests_status: 已通过
    task_id: R-004
    status: migrated
    snapshot_id: SNAP-2026-04-07-bootstrap-001
```

Create `docs/templates/candidate-rule-mapping-template.md` with a Markdown table containing these columns:

```md
# 候选规则分流台账模板

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| candidate_id | 是 | 候选编号，格式 `CR-xxx` |
| source_name | 是 | 来源文档名称 |
| source_rule_text | 是 | 原始审查点文本 |
| source_category | 是 | 来源专题或家族 |
| decision | 是 | `formal_rule / conditional_rule / capability_item / drop` |
| decision_reason | 是 | 分流原因 |
| target_rule_id | 否 | 若纳管，对应 `R-xxx` |
| target_layer | 否 | 建议落层 |
| profile_dependency | 是 | 是否依赖画像前置 |
| negative_conditions | 是 | 是否已有排除条件 |
| samples_status | 是 | 样本状态 |
| tests_status | 是 | 测试状态 |
| task_id | 否 | 关联任务单 |
| status | 是 | `new / triaged / in_progress / accepted / rejected / migrated` |
| snapshot_id | 是 | 所属快照批次 |
```

Create `docs/governance/candidate-rule-triage-criteria.md` with sections:

```md
# 候选规则分流标准

## 1. 分流结论

- `formal_rule`
- `conditional_rule`
- `capability_item`
- `drop`

## 2. 判定口径

进入 `formal_rule` 至少满足：

1. 触发条件可稳定定义
2. 排除条件可稳定定义
3. 可形成统一风险文案
4. 可形成统一整改文案
5. 可设计正负样本和回归测试

## 3. 常见排除场景

1. 模板残留项
2. 品类强依赖但当前未建立 profile 判断
3. 仅靠单句规则无法稳定识别的能力项
```

Update `docs/README.md` by adding one governance entry:

```md
- 候选规则治理方案：`docs/governance/candidate-rule-intake-and-migration-design.md`
- 候选规则分流标准：`docs/governance/candidate-rule-triage-criteria.md`
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest -q tests/test_candidate_rule_governance.py -k seed_import`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add rules/candidates/imports rules/candidates/mappings docs/templates/candidate-rule-mapping-template.md docs/governance/candidate-rule-triage-criteria.md docs/README.md tests/test_candidate_rule_governance.py
git commit -m "补充候选规则导入样板和分流模板"
```

## Task 3: 建立快照与回滚说明，并扩展治理校验

**Files:**
- Create: `rules/candidates/snapshots/SNAP-2026-04-07-bootstrap-001.md`
- Modify: `scripts/validate_rule_registry.py`
- Modify: `rules/tools/README.md`
- Test: `tests/test_candidate_rule_governance.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path


def test_candidate_snapshot_contains_required_sections():
    snapshot = Path("rules/candidates/snapshots/SNAP-2026-04-07-bootstrap-001.md")
    text = snapshot.read_text(encoding="utf-8")

    for phrase in [
        "快照编号",
        "输入来源",
        "分流范围",
        "任务单范围",
        "状态摘要",
        "回滚说明",
    ]:
        assert phrase in text
```

Add one validator smoke test:

```python
import subprocess


def test_validate_rule_registry_supports_candidate_mode():
    result = subprocess.run(
        ["python", "scripts/validate_rule_registry.py", "--candidate-root", "rules/candidates"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "candidate" in result.stdout.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest -q tests/test_candidate_rule_governance.py -k "snapshot or candidate_mode"`
Expected: FAIL because snapshot file and candidate mode validation do not exist.

- [ ] **Step 3: Write minimal implementation**

Create `rules/candidates/snapshots/SNAP-2026-04-07-bootstrap-001.md` with:

```md
# SNAP-2026-04-07-bootstrap-001

## 快照编号

- `SNAP-2026-04-07-bootstrap-001`

## 输入来源

- `IMPORT-2026-04-07-001`
- `合规性审查点反馈表分层映射清单`

## 分流范围

- `CR-001`
- `CR-002`
- `CR-003`

## 任务单范围

- `Task-G6`
- `Task-G7`
- `Task-G8`

## 状态摘要

- 候选池目录已建立
- 首批 seed import 已落盘
- 首批 mapping 样板已落盘

## 回滚说明

若首批候选台账结构或批次命名不合理，回退本快照对应文件：

- `rules/candidates/imports/candidate_rules_2026-04-07_seed.yaml`
- `rules/candidates/mappings/candidate_rule_mapping_2026-04-07.yaml`
- `rules/candidates/snapshots/SNAP-2026-04-07-bootstrap-001.md`
```

Update `scripts/validate_rule_registry.py` so it accepts:

```python
parser.add_argument(
    "--candidate-root",
    default=None,
    help="Optional candidate rule root to validate candidate governance scaffolding.",
)
```

And add minimal logic:

```python
if args.candidate_root:
    candidate_root = Path(args.candidate_root)
    required = [
        candidate_root / "README.md",
        candidate_root / "imports",
        candidate_root / "mappings",
        candidate_root / "snapshots",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise SystemExit(f"candidate validation failed: missing {missing}")
    print("candidate governance validation passed")
```

Update `rules/tools/README.md` by adding:

```md
- `python scripts/validate_rule_registry.py --candidate-root rules/candidates`

新增用途：

- 校验候选规则池目录是否完整
- 校验候选导入、映射、快照目录是否存在
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest -q tests/test_candidate_rule_governance.py -k "snapshot or candidate_mode"`
Expected: PASS

Run: `python scripts/validate_rule_registry.py --candidate-root rules/candidates`
Expected: print `candidate governance validation passed`

- [ ] **Step 5: Commit**

```bash
git add rules/candidates/snapshots/SNAP-2026-04-07-bootstrap-001.md scripts/validate_rule_registry.py rules/tools/README.md tests/test_candidate_rule_governance.py
git commit -m "补充候选规则快照与基础校验"
```

## Task 4: 下发 G6 / G7 / G8 任务单并挂接总台账

**Files:**
- Create: `docs/tasks/Task-G6-candidate-rule-triage-and-ledger.md`
- Create: `docs/tasks/Task-G7-candidate-rule-snapshot-and-rollback.md`
- Create: `docs/tasks/Task-G8-first-batch-candidate-rule-migration.md`
- Modify: `docs/trackers/v2-remediation-tracker.md`
- Test: `tests/test_candidate_rule_governance.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path


def test_candidate_governance_tasks_exist_and_are_linked_in_tracker():
    task_paths = [
        Path("docs/tasks/Task-G6-candidate-rule-triage-and-ledger.md"),
        Path("docs/tasks/Task-G7-candidate-rule-snapshot-and-rollback.md"),
        Path("docs/tasks/Task-G8-first-batch-candidate-rule-migration.md"),
    ]
    missing = [str(path) for path in task_paths if not path.exists()]
    assert not missing, f"missing governance tasks: {missing}"

    tracker_text = Path("docs/trackers/v2-remediation-tracker.md").read_text(encoding="utf-8")
    for task_id in ["G-006", "G-007", "G-008"]:
        assert task_id in tracker_text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest -q tests/test_candidate_rule_governance.py -k linked_in_tracker`
Expected: FAIL because G6/G7/G8 task files and tracker entries do not exist.

- [ ] **Step 3: Write minimal implementation**

Create `docs/tasks/Task-G6-candidate-rule-triage-and-ledger.md` with these sections:

```md
# Task-G6 候选规则分流与纳管台账搭建任务单

## 基本信息

- 任务编号：`Task-G6`
- 任务名称：候选规则分流与纳管台账搭建
- 任务类型：`治理架构实施`
- 当前状态：`待执行`
- 下发对象：`T`
- 监督角色：`M`

## 任务目标

1. 建立候选规则分流台账
2. 完成首轮候选规则分类
3. 形成正式规则、条件型规则、能力项、删除项四类分流结果
```

Create `docs/tasks/Task-G7-candidate-rule-snapshot-and-rollback.md` with:

```md
# Task-G7 候选规则快照与回滚机制任务单

## 基本信息

- 任务编号：`Task-G7`
- 任务名称：候选规则快照与回滚机制
- 任务类型：`治理架构实施`
- 当前状态：`待执行`
- 下发对象：`T`
- 监督角色：`M`

## 任务目标

1. 建立候选规则批次快照模板
2. 建立迁移失败快速回滚说明
3. 打通候选池与校验工具的最小闭环
```

Create `docs/tasks/Task-G8-first-batch-candidate-rule-migration.md` with:

```md
# Task-G8 首批高价值候选规则纳管任务单

## 基本信息

- 任务编号：`Task-G8`
- 任务名称：首批高价值候选规则纳管
- 任务类型：`治理架构实施`
- 当前状态：`待执行`
- 下发对象：`T`
- 监督角色：`M`

## 任务目标

1. 从候选池挑选首批高价值条目
2. 转化为正式规则纳管任务
3. 补齐样本、测试、任务单映射
```

Update `docs/trackers/v2-remediation-tracker.md` by inserting three rows near the governance section:

```md
| G-006 | 150条候选规则分流与纳管台账搭建 | 治理架构实施 | 待执行 | 候选池接入、首轮分流与台账落盘 |
| G-007 | 候选规则快照与回滚机制 | 治理架构实施 | 待执行 | 建立候选批次快照、回滚说明与最小校验闭环 |
| G-008 | 首批高价值候选规则纳管 | 治理架构实施 | 待执行 | 从候选池筛选首批高价值条目并生成正式纳管入口 |
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest -q tests/test_candidate_rule_governance.py -k linked_in_tracker`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add docs/tasks/Task-G6-candidate-rule-triage-and-ledger.md docs/tasks/Task-G7-candidate-rule-snapshot-and-rollback.md docs/tasks/Task-G8-first-batch-candidate-rule-migration.md docs/trackers/v2-remediation-tracker.md tests/test_candidate_rule_governance.py
git commit -m "新增候选规则治理任务单和台账入口"
```

## Task 5: 做一轮治理自检并收口文档入口

**Files:**
- Modify: `tests/test_candidate_rule_governance.py`
- Modify: `docs/README.md`
- Modify: `rules/README.md`
- Modify: `rules/tools/README.md`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path


def test_candidate_governance_docs_are_cross_referenced():
    docs_readme = Path("docs/README.md").read_text(encoding="utf-8")
    rules_readme = Path("rules/README.md").read_text(encoding="utf-8")
    tools_readme = Path("rules/tools/README.md").read_text(encoding="utf-8")

    assert "candidate-rule-intake-and-migration-design.md" in docs_readme
    assert "candidate-rule-triage-criteria.md" in docs_readme
    assert "candidates/" in rules_readme
    assert "--candidate-root rules/candidates" in tools_readme
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest -q tests/test_candidate_rule_governance.py -k cross_referenced`
Expected: FAIL until README and tool docs are all updated.

- [ ] **Step 3: Write minimal implementation**

Ensure the following lines exist exactly once:

In `docs/README.md`:

```md
- 候选规则治理方案：`docs/governance/candidate-rule-intake-and-migration-design.md`
- 候选规则分流标准：`docs/governance/candidate-rule-triage-criteria.md`
```

In `rules/README.md`:

```md
- `candidates/`：候选规则池，承接外部规则导入、分流、快照与回滚
```

In `rules/tools/README.md`:

```md
- `python scripts/validate_rule_registry.py --candidate-root rules/candidates`
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest -q tests/test_candidate_rule_governance.py -k cross_referenced`
Expected: PASS

Run: `pytest -q tests/test_candidate_rule_governance.py tests/test_rule_governance.py tests/test_rule_registry_first_batch.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add docs/README.md rules/README.md rules/tools/README.md tests/test_candidate_rule_governance.py
git commit -m "收口候选规则治理入口和自检"
```

## Spec Coverage Check

This plan covers the approved spec as follows:

- 候选层 / 注册层 / 运行层边界：Task 1, Task 2
- 候选目录骨架：Task 1
- 候选分流台账：Task 2
- 快照与回滚：Task 3
- M / T 任务承接入口：Task 4
- 文档入口与治理一致性：Task 5

No spec section is intentionally deferred in this rollout. Full automation is not implemented here; it is intentionally postponed per the approved spec and only the minimal candidate validation hook is included.

## Self-Review

- Placeholder scan complete: no `TODO`, `TBD`, or undefined file paths remain.
- Type consistency checked: `candidate_id`, `snapshot_id`, `decision`, `status`, `task_id`, and `--candidate-root` naming are used consistently across all tasks.
- Scope check complete: the plan is limited to governance scaffolding and does not expand into actual large-scale rule migration or runtime behavior changes.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-07-candidate-rule-governance-rollout.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
