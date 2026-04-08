# Task-G15 RC-014 Certificate Tenure Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a candidate-governance strengthening package for `RC-014` that anchors it under `R-006` as the `certificate_tenure_as_hidden_business_age` sub-boundary.

**Architecture:** Keep the work in governance artifacts instead of runtime rule code. Represent the hidden-tenure logic as structured YAML, pair it with positive/negative/boundary samples and a strengthening recommendation package, and validate the whole package with focused pytest checks.

**Tech Stack:** YAML, Markdown, pytest, existing candidate-rule governance conventions

---

### Task 1: Add RC-014 governance tests first

**Files:**
- Modify: `tests/test_candidate_rule_governance.py`

- [ ] **Step 1: Write the failing test**

```python
def test_rc014_hidden_tenure_model_exists_and_targets_r006_sub_boundary() -> None:
    payload = yaml.safe_load(RC014_MODEL_PATH.read_text(encoding="utf-8"))
    assert payload["candidate_id"] == "RC-014"
    assert payload["ownership"]["target_rule_id"] == "R-006"
    assert payload["ownership"]["sub_boundary"] == "certificate_tenure_as_hidden_business_age"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest -q tests/test_candidate_rule_governance.py -k 'rc014_hidden_tenure'`
Expected: FAIL because the RC-014 governance package does not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
RC014_MODEL_PATH = CANDIDATE_ROOT / "mappings" / "rc014_hidden_tenure_model_2026-04-08.yaml"
```

- [ ] **Step 4: Run test to verify it fails for the right reason**

Run: `pytest -q tests/test_candidate_rule_governance.py -k 'rc014_hidden_tenure'`
Expected: FAIL with missing-file errors, proving the tests are pointed at the new package.

- [ ] **Step 5: Commit**

```bash
git add tests/test_candidate_rule_governance.py
git commit -m "补充RC-014隐性年限门槛测试骨架"
```

### Task 2: Create the RC-014 boundary model and sample package

**Files:**
- Create: `rules/candidates/mappings/rc014_hidden_tenure_model_2026-04-08.yaml`
- Create: `rules/candidates/imports/rc014_hidden_tenure_samples_2026-04-08.yaml`
- Create: `docs/governance/rc014-hidden-tenure-model-2026-04-08.md`
- Test: `tests/test_candidate_rule_governance.py`

- [ ] **Step 1: Write the failing test**

```python
def test_rc014_hidden_tenure_samples_cover_positive_negative_and_boundary_cases() -> None:
    payload = yaml.safe_load(RC014_SAMPLES_PATH.read_text(encoding="utf-8"))
    assert payload["positive_samples"]
    assert payload["negative_samples"]
    assert payload["boundary_samples"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest -q tests/test_candidate_rule_governance.py -k 'rc014_hidden_tenure'`
Expected: FAIL because the model and sample files do not exist.

- [ ] **Step 3: Write minimal implementation**

```yaml
candidate_id: RC-014
ownership:
  target_rule_id: R-006
  sub_boundary: certificate_tenure_as_hidden_business_age
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest -q tests/test_candidate_rule_governance.py -k 'rc014_hidden_tenure and not strengthening'`
Expected: PASS for model/sample structure tests.

- [ ] **Step 5: Commit**

```bash
git add rules/candidates/mappings/rc014_hidden_tenure_model_2026-04-08.yaml rules/candidates/imports/rc014_hidden_tenure_samples_2026-04-08.yaml docs/governance/rc014-hidden-tenure-model-2026-04-08.md tests/test_candidate_rule_governance.py
git commit -m "补充RC-014隐性年限边界模型与样本"
```

### Task 3: Add the strengthening recommendation package

**Files:**
- Create: `rules/candidates/mappings/rc014_hidden_tenure_strengthening_package_2026-04-08.yaml`
- Modify: `docs/governance/rc014-hidden-tenure-model-2026-04-08.md`
- Test: `tests/test_candidate_rule_governance.py`

- [ ] **Step 1: Write the failing test**

```python
def test_rc014_strengthening_package_writes_final_conclusion_to_r006_only() -> None:
    payload = yaml.safe_load(RC014_PACKAGE_PATH.read_text(encoding="utf-8"))
    assert payload["final_conclusion"]["target_rule_id"] == "R-006"
    assert payload["final_conclusion"]["recommend_new_rule"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest -q tests/test_candidate_rule_governance.py -k 'rc014_strengthening_package'`
Expected: FAIL because the strengthening package file does not exist.

- [ ] **Step 3: Write minimal implementation**

```yaml
candidate_id: RC-014
final_conclusion:
  target_rule_id: R-006
  recommend_new_rule: false
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest -q tests/test_candidate_rule_governance.py -k 'rc014_hidden_tenure or rc014_strengthening_package'`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add rules/candidates/mappings/rc014_hidden_tenure_strengthening_package_2026-04-08.yaml docs/governance/rc014-hidden-tenure-model-2026-04-08.md tests/test_candidate_rule_governance.py
git commit -m "明确RC-014补强归属与子边界"
```
