# Rule Status Flow

最小状态集合：

- `draft`
- `in_progress`
- `review`
- `active`
- `rejected`
- `deprecated`

最小流转约束：

- `draft -> in_progress | rejected`
- `in_progress -> review | draft | rejected`
- `review -> active | in_progress | rejected | deprecated`
- `active -> review | deprecated`
- `rejected` 和 `deprecated` 为终态

说明：

- `draft`：规则草稿已建，但口径尚未定稿
- `in_progress`：T 正在实现，样本与测试可能仍在补
- `review`：实现完成，等待 M 验收
- `active`：口径通过并可正式纳入成熟链路
- `rejected`：规则判定不成立或本轮不采纳
- `deprecated`：规则已退出当前治理主路径

