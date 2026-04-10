# V2 Risk Admission

该目录承接 V2 的正式风险准入层骨架，位于：

`compare / output_governance -> risk_admission -> assembler / final outputs`

当前 RA1 版本只完成最小职责：

1. 承接 `output_governance` 输出，形成独立的准入层输入输出对象
2. 为 `formal_risks / pending_review_items / excluded_risks` 提供唯一最终出口
3. 向 assembler 提供单一的 `AdmissionResult`

后续 `RA2 / RA3` 将在此层继续补：

- evidence kind 判定
- 模板与边界证据硬门禁
- 提醒项与证据不足项降级
- 真实文件回放门禁
