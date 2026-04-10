# Task-G12 RC-003 Industry Evidence Modeling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an industry-scoped evidence boundary package for `RC-003` so we can distinguish formal risk, pending review, and exclusion before deciding whether it should become `R-013`.

**Architecture:** Keep the work inside `rules/candidates/` and governance docs instead of `rules/registry/`. Represent the model as structured YAML plus a companion note, validate it with tests, and produce one targeted diesel real-file replay plus one industry sample replay to measure false-positive risk.

**Tech Stack:** YAML, Markdown, pytest, existing V2 replay pipeline, candidate-rule governance conventions

---

### Task 1: Create the RC-003 modeling package

**Files:**
- Create: `rules/candidates/mappings/rc003_industry_evidence_model_2026-04-08.yaml`
- Create: `docs/governance/rc003-industry-evidence-model-2026-04-08.md`
- Modify: `rules/candidates/mappings/README.md`
- Test: `tests/test_candidate_rule_governance.py`

- [ ] **Step 1: Write the failing test**

```python
def test_rc003_evidence_model_exists_and_has_required_fields() -> None:
    payload = yaml.safe_load(RC003_MODEL_PATH.read_text(encoding="utf-8"))
    assert payload["candidate_id"] == "RC-003"
    assert payload["required_fields"] == [
        "procurement_object",
        "procurement_scene",
        "qualification_name",
        "qualification_usage",
        "demand_relevance",
        "industry_match_level",
        "evidence_sufficiency",
        "decision_layer",
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest -q tests/test_candidate_rule_governance.py -k rc003_evidence_model_exists`
Expected: FAIL because the RC-003 model file and constant do not exist yet.

- [ ] **Step 3: Write minimal implementation**

```yaml
candidate_id: RC-003
model_version: 1
required_fields:
  - procurement_object
  - procurement_scene
  - qualification_name
  - qualification_usage
  - demand_relevance
  - industry_match_level
  - evidence_sufficiency
  - decision_layer
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest -q tests/test_candidate_rule_governance.py -k rc003_evidence_model_exists`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add rules/candidates/mappings/rc003_industry_evidence_model_2026-04-08.yaml docs/governance/rc003-industry-evidence-model-2026-04-08.md rules/candidates/mappings/README.md tests/test_candidate_rule_governance.py
git commit -m "补充RC-003行业化证据字段模型"
```

### Task 2: Add industry judgment logic and three-layer rules

**Files:**
- Modify: `rules/candidates/mappings/rc003_industry_evidence_model_2026-04-08.yaml`
- Modify: `docs/governance/rc003-industry-evidence-model-2026-04-08.md`
- Test: `tests/test_candidate_rule_governance.py`

- [ ] **Step 1: Write the failing test**

```python
def test_rc003_industry_logic_defines_three_decision_layers() -> None:
    payload = yaml.safe_load(RC003_MODEL_PATH.read_text(encoding="utf-8"))
    assert payload["decision_layers"] == ["formal_risk", "pending_review", "exclude"]
    assert "柴油发电机组" in payload["industry_scope"]
    assert "机电安装" in payload["industry_scope"]
    assert "配套设备采购" in payload["industry_scope"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest -q tests/test_candidate_rule_governance.py -k rc003_industry_logic_defines_three_decision_layers`
Expected: FAIL because the fields are missing.

- [ ] **Step 3: Write minimal implementation**

```yaml
industry_scope:
  - 柴油发电机组
  - 机电安装
  - 配套设备采购
decision_layers:
  - formal_risk
  - pending_review
  - exclude
decision_rules:
  formal_risk:
    - procurement_object_and_scene_clear
    - qualification_is_obviously_cross_industry
    - evidence_is_sufficient
  pending_review:
    - relevance_is_weak_but_not_dead
    - industry_special_basis_may_exist
  exclude:
    - qualification_has_reasonable_delivery_relation
    - unfamiliar_name_alone_is_not_enough
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest -q tests/test_candidate_rule_governance.py -k rc003_industry_logic_defines_three_decision_layers`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add rules/candidates/mappings/rc003_industry_evidence_model_2026-04-08.yaml docs/governance/rc003-industry-evidence-model-2026-04-08.md tests/test_candidate_rule_governance.py
git commit -m "补充RC-003行业化判定与三层落位规则"
```

### Task 3: Add positive, negative, and boundary sample sets

**Files:**
- Modify: `rules/candidates/mappings/rc003_industry_evidence_model_2026-04-08.yaml`
- Create: `rules/candidates/imports/rc003_industry_samples_2026-04-08.yaml`
- Test: `tests/test_candidate_rule_governance.py`

- [ ] **Step 1: Write the failing test**

```python
def test_rc003_samples_cover_positive_negative_and_boundary_cases() -> None:
    payload = yaml.safe_load(RC003_SAMPLES_PATH.read_text(encoding="utf-8"))
    assert payload["positive_samples"]
    assert payload["negative_samples"]
    assert payload["boundary_samples"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest -q tests/test_candidate_rule_governance.py -k rc003_samples_cover_positive_negative_and_boundary_cases`
Expected: FAIL because the sample file does not exist yet.

- [ ] **Step 3: Write minimal implementation**

```yaml
batch_id: RC003-SAMPLES-2026-04-08-001
candidate_id: RC-003
positive_samples:
  - sample_id: RC003-P-001
    procurement_object: 柴油发电机组
    qualification_name: 农作物种子生产经营许可证
boundary_samples:
  - sample_id: RC003-B-001
    procurement_object: 柴油发电机组及配套安装
    qualification_name: 安全生产标准化证书
negative_samples:
  - sample_id: RC003-N-001
    procurement_object: 机电设备安装
    qualification_name: 建筑机电安装工程专业承包资质
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest -q tests/test_candidate_rule_governance.py -k rc003_samples_cover_positive_negative_and_boundary_cases`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add rules/candidates/imports/rc003_industry_samples_2026-04-08.yaml rules/candidates/mappings/rc003_industry_evidence_model_2026-04-08.yaml tests/test_candidate_rule_governance.py
git commit -m "补充RC-003正负边界样本集"
```

### Task 4: Add replay summary and upgrade recommendation

**Files:**
- Create: `rules/candidates/mappings/rc003_industry_replay_summary_2026-04-08.yaml`
- Modify: `docs/governance/rc003-industry-evidence-model-2026-04-08.md`
- Modify: `docs/trackers/v2-remediation-tracker.md`
- Test: `tests/test_candidate_rule_governance.py`

- [ ] **Step 1: Write the failing test**

```python
def test_rc003_replay_summary_and_upgrade_recommendation_are_present() -> None:
    payload = yaml.safe_load(RC003_REPLAY_PATH.read_text(encoding="utf-8"))
    assert payload["real_replay"]
    assert payload["industry_replay"]
    assert payload["upgrade_recommendation"]["candidate_id"] == "RC-003"
    assert payload["upgrade_recommendation"]["recommend_r013"] in {True, False}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest -q tests/test_candidate_rule_governance.py -k rc003_replay_summary_and_upgrade_recommendation_are_present`
Expected: FAIL because the replay summary file does not exist.

- [ ] **Step 3: Write minimal implementation**

```yaml
candidate_id: RC-003
real_replay:
  file: /Users/linzeran/code/2026-zn/test_target/zf/埋点测试案例和结果/[SZDL2025000495-A-0330]柴油发电机组及相关配套机电设备采购及安装项目.docx
  summary: 未发现足以支持“资质与需求错配”正式风险的证据
industry_replay:
  summary: 行业样本可区分 formal / pending / exclude
upgrade_recommendation:
  candidate_id: RC-003
  recommend_r013: false
  blocker: 行业覆盖仍过窄，边界样本仍需扩充
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest -q tests/test_candidate_rule_governance.py -k rc003_replay_summary_and_upgrade_recommendation_are_present`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add rules/candidates/mappings/rc003_industry_replay_summary_2026-04-08.yaml docs/governance/rc003-industry-evidence-model-2026-04-08.md docs/trackers/v2-remediation-tracker.md tests/test_candidate_rule_governance.py
git commit -m "补充RC-003回放结论与R-013升级建议"
```

### Task 5: Run the full governance verification set

**Files:**
- Test: `tests/test_candidate_rule_governance.py`

- [ ] **Step 1: Run focused RC-003 tests**

Run: `pytest -q tests/test_candidate_rule_governance.py -k 'rc003 or candidate_rule_governance'`
Expected: PASS

- [ ] **Step 2: Run the full candidate governance test file**

Run: `pytest -q tests/test_candidate_rule_governance.py`
Expected: PASS

- [ ] **Step 3: Re-read the task checklist**

Confirm the final response includes:

```text
1. 证据字段模型说明
2. 行业化判定逻辑说明
3. 三层落位规则说明
4. 正样本、负样本、边界样本清单
5. 真实回放或行业回放结果
6. 是否建议升级 R-013 的结论说明
7. 改动文件清单
```

- [ ] **Step 4: Commit**

```bash
git add tests/test_candidate_rule_governance.py rules/candidates/mappings/rc003_industry_evidence_model_2026-04-08.yaml rules/candidates/imports/rc003_industry_samples_2026-04-08.yaml rules/candidates/mappings/rc003_industry_replay_summary_2026-04-08.yaml docs/governance/rc003-industry-evidence-model-2026-04-08.md docs/trackers/v2-remediation-tracker.md
git commit -m "完成Task-G12 RC-003行业化证据边界建模"
```
