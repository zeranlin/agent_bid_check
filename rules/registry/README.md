# Rule Registry

`rules/registry/` 存放运行主源注册表文件。

- 根目录下的 `R-xxx.yaml` 为正式规则注册表
- `governance-formal/` 下的 `GOV-*.yaml` 为治理型主源条目，不等同于正式 `R-xxx` 规则
- 一条条目对应一个 YAML 文件
- 文件命名优先使用条目编号，如 `R-001.yaml`、`GOV-sample_gate.yaml`
- `_example_rule.yaml` 用于演示最小完整写法
