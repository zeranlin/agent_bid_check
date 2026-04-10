# Rule Tools

当前第一版治理工具：

- `python scripts/validate_rule_registry.py`
- `python scripts/validate_rule_registry.py --candidate-root rules/candidates`

用途：

- 校验规则 YAML 是否具备最小必填字段
- 校验是否缺少 `trigger_conditions`
- 校验是否缺少 `exclude_conditions`
- 校验是否缺少 `output.formal_title`
- 校验是否缺少样本、测试、任务单引用
- 校验候选规则池骨架是否完整

候选池最小校验命令：

```bash
python scripts/validate_rule_registry.py --candidate-root rules/candidates
```
