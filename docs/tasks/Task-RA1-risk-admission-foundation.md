# Task-RA1 风险准入层骨架搭建任务单

## 基本信息

- 任务编号：`Task-RA1`
- 任务名称：风险准入层骨架搭建
- 任务类型：`治理架构实施`
- 当前状态：`待下发`
- 下发对象：`T`
- 监督角色：`M`

## 任务背景

当前 V2 已具备风险发现能力，但仍缺少独立的正式风险准入层，导致：

- topic 推断会直接进入正式风险
- 证据边界不清的条目难以统一拦截
- 客户反馈后的误报整改缺少稳定挂点

因此需要先搭建独立的 `risk_admission` 骨架。

## 任务目标

1. 建立 `app/pipelines/v2/risk_admission/` 目录骨架
2. 定义准入层输入输出 schema
3. 明确 `formal_risks / pending_review_items / excluded_risks` 的唯一裁决位置
4. 将现有 compare / governance / assembler 主链路接到准入层

## 具体整改要求

### 1. 搭建模块骨架

至少新增：

- `schemas.py`
- `evidence_classifier.py`
- `source_classifier.py`
- `rules.py`
- `decision_engine.py`
- `pipeline.py`

### 2. 定义输入输出模型

至少要有：

- evidence kind
- source type
- admission decision
- admission reason
- target layer

### 3. 建立唯一三分层裁决入口

要求：

- 最终 `formal_risks / pending_review_items / excluded_risks` 只能由 risk_admission 决定
- 其他层不得绕过 risk_admission 直接写最终分层

### 4. 与现有链路打通

要求：

- compare 结果进入 risk_admission
- assembler 只消费 risk_admission 结果
- Web / report 继续消费最终结构化结果，不直接消费 topic 自由文案

## 必须补的测试

1. risk_admission 基础对象构造测试
2. 三分层唯一出口测试
3. assembler 只能消费 risk_admission 输出测试

## 交付物要求

1. 模块骨架说明
2. 准入层 schema 说明
3. 串联链路说明
4. 新增测试清单

## M 验收标准

### 通过线

- risk_admission 目录骨架完整
- 输入输出模型清晰
- 三分层裁决已形成唯一入口
- 与现有链路已打通

### 不通过情形

- 只是新建目录，没有真正接入主链路
- formal/pending/excluded 仍由多个层同时决定
- assembler 或 Web 仍能绕过 risk_admission
