# Task-G14 RC-013 Safety Standardization Modeling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an industry-scoped evidence boundary package for `RC-013` so we can distinguish when `安全生产标准化证书` should fall into formal risk, pending review, or exclusion before deciding whether it should become a formal rule.

**Architecture:** Keep the work inside `rules/candidates/` and governance docs instead of `rules/registry/`. Represent the boundary as structured YAML plus a companion note, validate it with candidate-governance tests, use industry sample replay as the primary proof, and use the diesel real file only as a supporting false-positive check.

**Tech Stack:** YAML, Markdown, pytest, existing candidate-rule governance conventions

---

### Task 1: Add RC-013 governance tests first

**Files:**
- Modify: `tests/test_candidate_rule_governance.py`

- [ ] **Step 1: Write the failing test**

```python
def test_rc013_safety_standardization_model_exists_and_has_required_fields() -> None:
    payload = yaml.safe_load(RC013_MODEL_PATH.read_text(encoding="utf-8"))
    assert payload["candidate_id"] == "RC-013"
    assert payload["required_fields"] == [
        "procurement_object",
        "procurement_scene",
        "requirement_name",
        "requirement_usage",
        "safety_requirement_kind",
        "scene_relevance",
        "evidence_sufficiency",
        "decision_layer",
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest -q tests/test_candidate_rule_governance.py -k 'rc013_safety_standardization'`
Expected: FAIL because the RC-013 model file and constants do not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
RC013_MODEL_PATH = CANDIDATE_ROOT / "mappings" / "rc013_safety_standardization_model_2026-04-08.yaml"
```

- [ ] **Step 4: Run test to verify it fails for the right reason**

Run: `pytest -q tests/test_candidate_rule_governance.py -k 'rc013_safety_standardization'`
Expected: FAIL with missing-file errors, proving the tests are pointed at the new RC-013 package.

- [ ] **Step 5: Commit**

```bash
git add tests/test_candidate_rule_governance.py
git commit -m "补充RC-013行业化治理测试骨架"
```

### Task 2: Create the RC-013 boundary model and sample package

**Files:**
- Create: `rules/candidates/mappings/rc013_safety_standardization_model_2026-04-08.yaml`
- Create: `rules/candidates/imports/rc013_safety_standardization_samples_2026-04-08.yaml`
- Create: `docs/governance/rc013-safety-standardization-model-2026-04-08.md`
- Test: `tests/test_candidate_rule_governance.py`

- [ ] **Step 1: Write the failing test**

```python
def test_rc013_samples_cover_positive_negative_and_boundary_cases() -> None:
    payload = yaml.safe_load(RC013_SAMPLES_PATH.read_text(encoding="utf-8"))
    assert payload["positive_samples"]
    assert payload["negative_samples"]
    assert payload["boundary_samples"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest -q tests/test_candidate_rule_governance.py -k 'rc013_safety_standardization'`
Expected: FAIL because the model and sample files do not exist.

- [ ] **Step 3: Write minimal implementation**

```yaml
candidate_id: RC-013
required_fields:
  - procurement_object
  - procurement_scene
  - requirement_name
  - requirement_usage
  - safety_requirement_kind
  - scene_relevance
  - evidence_sufficiency
  - decision_layer
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest -q tests/test_candidate_rule_governance.py -k 'rc013_safety_standardization and not replay'`
Expected: PASS for model and sample structure tests.

- [ ] **Step 5: Commit**

```bash
git add rules/candidates/mappings/rc013_safety_standardization_model_2026-04-08.yaml rules/candidates/imports/rc013_safety_standardization_samples_2026-04-08.yaml docs/governance/rc013-safety-standardization-model-2026-04-08.md tests/test_candidate_rule_governance.py
git commit -m "补充RC-013行业化边界模型与样本"
```

### Task 3: Add industry replay and real file check summary

**Files:**
- Create: `rules/candidates/mappings/rc013_safety_standardization_replay_summary_2026-04-08.yaml`
- Modify: `docs/governance/rc013-safety-standardization-model-2026-04-08.md`
- Test: `tests/test_candidate_rule_governance.py`

- [ ] **Step 1: Write the failing test**

```python
def test_rc013_replay_summary_distinguishes_industry_replay_and_real_file_check() -> None:
    payload = yaml.safe_load(RC013_REPLAY_PATH.read_text(encoding="utf-8"))
    assert payload["industry_replay"]
    assert payload["real_file_check"]
    assert payload["upgrade_recommendation"]["candidate_id"] == "RC-013"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest -q tests/test_candidate_rule_governance.py -k 'rc013_safety_standardization_replay'`
Expected: FAIL because the replay summary file does not exist.

- [ ] **Step 3: Write minimal implementation**

```yaml
candidate_id: RC-013
industry_replay:
  summary: 主回放以行业化样例为主
real_file_check:
  summary: 当前柴油真实文件仅作误报辅助核查
upgrade_recommendation:
  candidate_id: RC-013
  recommend_formal_rule: false
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest -q tests/test_candidate_rule_governance.py -k 'rc013_safety_standardization'`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add rules/candidates/mappings/rc013_safety_standardization_replay_summary_2026-04-08.yaml docs/governance/rc013-safety-standardization-model-2026-04-08.md tests/test_candidate_rule_governance.py
git commit -m "补充RC-013样例回放与升级建议"
```
