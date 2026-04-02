# 客户反馈闭环记录

本目录用于统一沉淀客户反馈闭环资产，避免漏报/误报问题只停留在聊天记录里。

目录约定：

- `templates/customer_feedback_template.yaml`
  - 统一反馈记录模板。
- `records/*.yaml`
  - 单条客户反馈记录。
- `records/G-004-feedback-matrix.md`
  - 当前闭环演练矩阵。

每条反馈至少记录以下字段：

- `feedback_id`
- `file_name`
- `feedback_type`
- `source_location`
- `customer_feedback`
- `m_initial_analysis`
- `root_cause_layer`
- `task_type`
- `linked_task`
- `fix_summary`
- `regression_result`
