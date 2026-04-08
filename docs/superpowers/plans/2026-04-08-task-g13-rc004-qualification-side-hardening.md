# Task-G13 RC-004 Qualification-Side Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a qualification-side governance package for `RC-004` so we can separate gate-side personnel certificate risks from scoring-side logic and make one explicit ownership recommendation.

**Architecture:** Keep this work in the candidate-governance layer only. Represent the qualification-side boundary as structured YAML plus companion governance notes, validate it with targeted tests, and avoid touching `rules/registry/` or the runtime compare chain.

**Tech Stack:** YAML, Markdown, pytest, existing candidate governance conventions

---

### Task 1: Add qualification-side governance tests first

**Files:**
- Modify: `tests/test_candidate_rule_governance.py`

- [ ] **Step 1: Write the failing test**

```python
def test_rc004_qualification_side_model_exists_and_is_scoped_to_gate_only() -> None:
    payload = yaml.safe_load(RC004_QUAL_MODEL_PATH.read_text(encoding="utf-8"))
    assert payload["candidate_id"] == "RC-004"
    assert payload["scope"]["included"] == [
        "特定企业人员证书作为资格条件",
        "特定企业人员证书作为合格供应商条件",
        "特定企业人员证书作为资格审查通过门槛",
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest -q tests/test_candidate_rule_governance.py -k 'rc004_qualification_side'`
Expected: FAIL because the RC-004 qualification-side package does not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
RC004_QUAL_MODEL_PATH = CANDIDATE_ROOT / "mappings" / "rc004_qualification_side_model_2026-04-08.yaml"
```

- [ ] **Step 4: Run test to verify it fails for the right reason**

Run: `pytest -q tests/test_candidate_rule_governance.py -k 'rc004_qualification_side'`
Expected: FAIL with missing-file errors, proving the tests are pointed at the new package.

- [ ] **Step 5: Commit**

```bash
git add tests/test_candidate_rule_governance.py
git commit -m "补充RC-004资格条件侧治理测试骨架"
```

### Task 2: Create the RC-004 qualification-side model and samples

**Files:**
- Create: `rules/candidates/mappings/rc004_qualification_side_model_2026-04-08.yaml`
- Create: `rules/candidates/imports/rc004_qualification_side_samples_2026-04-08.yaml`
- Create: `docs/governance/rc004-qualification-side-model-2026-04-08.md`
- Test: `tests/test_candidate_rule_governance.py`

- [ ] **Step 1: Write the failing test**

```python
def test_rc004_qualification_side_samples_cover_positive_negative_and_boundary_cases() -> None:
    payload = yaml.safe_load(RC004_QUAL_SAMPLES_PATH.read_text(encoding="utf-8"))
    assert payload["positive_samples"]
    assert payload["negative_samples"]
    assert payload["boundary_samples"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest -q tests/test_candidate_rule_governance.py -k 'rc004_qualification_side'`
Expected: FAIL because the model and sample files do not exist.

- [ ] **Step 3: Write minimal implementation**

```yaml
candidate_id: RC-004
required_fields:
  - qualification_context
  - certificate_name
  - certificate_holder
  - gate_usage
  - necessity_level
  - qualification_side_match
  - evidence_sufficiency
  - decision_layer
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest -q tests/test_candidate_rule_governance.py -k 'rc004_qualification_side and not summary'`
Expected: PASS for model/sample structure tests.

- [ ] **Step 5: Commit**

```bash
git add rules/candidates/mappings/rc004_qualification_side_model_2026-04-08.yaml rules/candidates/imports/rc004_qualification_side_samples_2026-04-08.yaml docs/governance/rc004-qualification-side-model-2026-04-08.md tests/test_candidate_rule_governance.py
git commit -m "补充RC-004资格条件侧边界模型与样本"
```

### Task 3: Add the explicit ownership recommendation package

**Files:**
- Create: `rules/candidates/mappings/rc004_qualification_side_summary_2026-04-08.yaml`
- Modify: `docs/governance/rc004-qualification-side-model-2026-04-08.md`
- Test: `tests/test_candidate_rule_governance.py`

- [ ] **Step 1: Write the failing test**

```python
def test_rc004_qualification_side_summary_has_single_explicit_ownership_conclusion() -> None:
    payload = yaml.safe_load(RC004_QUAL_SUMMARY_PATH.read_text(encoding="utf-8"))
    assert payload["ownership_recommendation"]["route"] == "propose_new_rule"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest -q tests/test_candidate_rule_governance.py -k 'rc004_qualification_side_summary'`
Expected: FAIL because the summary file does not exist.

- [ ] **Step 3: Write minimal implementation**

```yaml
candidate_id: RC-004
ownership_recommendation:
  route: propose_new_rule
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest -q tests/test_candidate_rule_governance.py -k 'rc004_qualification_side'`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add rules/candidates/mappings/rc004_qualification_side_summary_2026-04-08.yaml docs/governance/rc004-qualification-side-model-2026-04-08.md tests/test_candidate_rule_governance.py
git commit -m "明确RC-004资格条件侧归属建议"
```
