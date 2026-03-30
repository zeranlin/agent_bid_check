# 招标文件审查工具

仓库地址：

- `GitHub`：`https://github.com/zeranlin/agent_bid_check`

项目已整理为“应用代码、启动脚本、数据目录”三层结构，便于后续继续扩展。

## 目录结构

```text
test_getst/
├── app/
│   ├── review/             # 招标文件解析、提取、LLM 调用、CLI 逻辑
│   └── web/                # Flask 页面、模板、静态资源
├── scripts/
│   ├── run_review.py       # CLI 启动脚本
│   └── run_web.py          # Web 启动脚本
├── data/
│   ├── examples/           # 参考提示词、参考输出、对比样例
│   ├── runs/cli/           # CLI 运行产物
│   └── web_runs/           # Web 配置、上传文件、审查结果
├── bid_review.py           # 兼容旧命令的 CLI 入口
├── web_app.py              # 兼容旧命令的 Web 入口
└── README.md
```

## 分层说明

- `app/review/`
  - `core.py`：提取文本、拼接提示词、请求 LLM、解析响应
  - `cli.py`：命令行参数与执行流程
- `app/web/`
  - `app.py`：Flask 应用
  - `templates/`：页面模板
  - `static/`：样式资源
- `scripts/`
  - 给后续部署、快捷启动、自动化调用留统一入口
- `data/`
  - 运行数据和样例分开存放，避免根目录继续堆文件

## 启动方式

兼容旧命令：

```bash
python3 web_app.py
python3 bid_review.py --help
```

推荐新命令：

```bash
python3 scripts/run_web.py
python3 scripts/run_review.py --help
```

安装依赖：

```bash
python3 -m pip install -r requirements.txt
```

Web 地址：

```text
http://127.0.0.1:5010
```

## CLI 示例

```bash
python3 scripts/run_review.py \
  '/path/to/SZDL2025000495-A.docx' \
  --output data/runs/cli/SZDL2025000495-A_review.md \
  --save-extracted data/runs/cli/SZDL2025000495-A_extracted.txt \
  --save-request-json data/runs/cli/SZDL2025000495-A_request.json \
  --save-raw-response data/runs/cli/SZDL2025000495-A_response.json
```

## 数据目录约定

- `data/examples/`：只放参考资料，不参与运行
- `data/runs/cli/`：命令行执行结果
- `data/web_runs/review_config.json`：页面当前配置
- `data/web_runs/uploads/`：Web 上传文件
- `data/web_runs/results/`：每次审查结果

## 下一步可继续做的增强

- 把 Markdown 渲染器再独立成 `app/web/markdown.py`
- 补更多针对真实招标文件输出的回归样例
- 视需要再补 `pyproject.toml`
