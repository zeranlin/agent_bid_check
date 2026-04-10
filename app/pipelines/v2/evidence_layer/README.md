# V2 Evidence Layer

该目录承接 V2 的正式证据层骨架，位于：

`structure / evidence_map -> evidence_layer -> topic_review`

`Task-EP1` 仅完成最小职责：

1. 定义统一 `Evidence` 对象
2. 将结构切片与专题证据 bundle 规整为证据层对象
3. 为专题层提供稳定的 `topic_inputs`
4. 保留 `evidence_id / excerpt / location` 的基础 trace

后续 `EP2 / EP3 / EP4` 在此层继续补：

- `source_kind` 全量来源分类
- `business_domain` / `clause_role` 分类补齐
- `hard_evidence` 稳定判定
- 更细粒度的问题级证据归因
