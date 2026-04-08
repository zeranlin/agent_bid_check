# V2 Output Governance

该目录承接 V2 的输出治理层骨架，位于：

`compare / rule hits -> output_governance -> assembler / final outputs`

当前第一版只完成最小职责：

1. 将 `ComparisonArtifact` 转换为统一治理输入
2. 为正式风险 / 待补证 / 已排除项生成统一的治理对象
3. 向下游提供单一的 `GovernedResult`

当前边界说明：

- `compare` 负责候选风险识别与初步分层
- `output_governance` 负责风险身份、治理对象和统一结果结构
- `assembler` 负责只消费治理结果装配最终成品输出

后续 `OG2 / OG3` 将继续在此目录内补：

- 风险家族归并
- 三分层裁决器
- 标题单源化
- 输出准入控制
