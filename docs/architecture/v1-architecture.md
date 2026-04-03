# V1 审查架构说明

## 定位

V1 是当前稳定运行的招标文件审查主流程，目标是：

- 支持上传 `.docx/.txt/.md`
- 调用单次 LLM 审查
- 对模型输出做固定格式归一化
- 在 Web 页面展示统一报告
- 保留原始输出、请求体、响应体和提取文本

V1 当前不承载三层架构实验，也不承载多阶段专题深审。

## V1 主链路

1. Web 接收文件上传
2. 后台任务提取正文
3. 调用 LLM 做全文直审
4. 对原始 Markdown 做标准化整理
5. 解析固定报告结构
6. 页面按风险等级和审查类型展示结果

## 关键目录

### 公共底座

- `app/common/file_extract.py`
  - 文件提取入口
- `app/common/llm_client.py`
  - LLM 调用入口
- `app/common/markdown_utils.py`
  - Markdown 标准化与解析公共方法
- `app/common/artifacts.py`
  - 审查产物结构
- `app/common/schemas.py`
  - 报告结构 Schema

### V1 Pipeline

- `app/pipelines/v1/service.py`
  - V1 审查编排
- `app/pipelines/v1/prompts.py`
  - V1 提示词入口
- `app/pipelines/v1/assembler.py`
  - V1 请求体与审查产物保存

### 兼容层

- `app/review/core.py`
  - 文本提取
  - LLM 调用
  - 流式输出支持
- `app/review/normalize.py`
  - 审查结果标准化
- `app/review/parser.py`
  - Markdown 报告解析
- `app/review/schema.py`
  - 兼容导出 Schema
- `app/review/service.py`
  - 兼容导出 V1 pipeline 能力

### Web

- `app/web/app.py`
  - V1 Web 应用入口
  - 审查任务状态管理
  - 历史结果读取与展示
- `app/web/templates/review.html`
  - V1 主页面
- `app/web/static/styles.css`
  - V1 页面样式

### 启动脚本

- `scripts/run_web.py`
  - V1 Web 入口
- `scripts/run_review.py`
  - CLI 入口

## V1 数据目录

- `data/uploads/v1/`
  - 上传文件
- `data/jobs/v1/`
  - 任务状态
- `data/results/v1/`
  - 审查结果与中间产物
- `data/config/review_v1.json`
  - V1 配置文件

## 主要产物

每次 V1 运行通常会生成：

- `review.md`
- `review_raw.md`
- `request.json`
- `response.json`
- `extracted.txt`
- `meta.json`

## 当前边界

V1 目前采用“全文直审 + 结果标准化”的单阶段模式。

这意味着：

- 优点是链路简单、稳定、覆盖完整
- 缺点是专题深审能力有限，结构化导航和多阶段复核能力不足

后续 V2 的三层架构实验应与 V1 隔离推进，不直接改动 V1 主链路。

另外，V1 仍兼容读取历史上的旧目录 `data/web_runs/results/`，用于保留既有审查记录。
