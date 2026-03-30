from __future__ import annotations

import json
import subprocess
import textwrap
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Callable


DOCX_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


DEFAULT_SYSTEM_PROMPT = (
    "你是政府采购招标文件合规审查人，专门审查招标文件是否存在限制竞争、"
    "不合理条件、评分因素不相关、技术参数倾向性、商务条款失衡等问题。"
    "你必须严格按用户给定的 Markdown 模板输出，不得擅自改写一级、二级标题名称，"
    "不得新增前言、结论口号、总结性宣传语。"
)


DEFAULT_USER_PROMPT = textwrap.dedent(
    """\
    请基于我提供的招标文件内容，输出一份结构稳定、字段固定的 Markdown 审查结果。

    审查要求：
    1. 逐项审查，不要遗漏
    2. 重点审查资格条件、评分办法、技术参数、商务条款、验收条款、业绩与证书要求
    3. 每个问题必须给出以下固定字段，且字段名不得改动：
    - 问题标题
    - 问题定性（高风险/中风险/低风险）
    - 审查类型
    - 原文位置
    - 原文摘录
    - 风险判断
    - 法律/政策依据
    - 整改建议

    审查原则：
    - 判断“是否与采购标的和合同履约直接相关”
    - 判断“是否可能限制或排斥潜在供应商”
    - 判断“是否存在指向特定供应商或特定产品的倾向”
    - 判断“评分标准是否明确、量化、可操作”
    - 判断“商务条款是否公平合理”

    注意：
    - 不能只给笼统意见，必须引用原文
    - 不能凭空捏造依据
    - 如依据不完全确定，应明确写“需人工复核”
    - 同类问题可合并，但不能省略关键原文
    - 输出必须严格使用下面的 Markdown 模板骨架
    - 一级标题、二级标题、字段顺序必须保持一致
    - 每个风险点都必须使用“## 风险点N：标题”格式，N 从 1 开始递增
    - 如果某一部分没有内容，也保留该章节标题，并写“未发现”
    - 不要输出表格
    - 不要把内容写成“审查报告”“审查综述”“详细风险点清单”等其他结构

    严格使用以下模板：

    # 招标文件合规审查结果

    审查对象：`<填写项目或文件名称>`

    说明：
    - 本审查基于你提供的招标文件文本进行。
    - 对于存在事实基础不足、需要采购人补充论证材料才能最终定性的事项，明确标注“需人工复核”。
    - 下述“风险判断”系合规审查意见，不等同于行政机关最终认定。

    ---

    ## 风险点1：<问题标题>

    - 问题定性：<高风险/中风险/低风险>
    - 审查类型：<类型>
    - 原文位置：<位置>
    - 原文摘录：<摘录>
    - 风险判断：
      - <分点说明>
    - 法律/政策依据：
      - <分点列出>
    - 整改建议：
      - <分点列出>

    ## 风险点2：<问题标题>

    - 问题定性：<高风险/中风险/低风险>
    - 审查类型：<类型>
    - 原文位置：<位置>
    - 原文摘录：<摘录>
    - 风险判断：
      - <分点说明>
    - 法律/政策依据：
      - <分点列出>
    - 整改建议：
      - <分点列出>

    按以上格式继续，直到风险点列完。

    ---

    ## 综合判断

    - 高风险问题：
      - <列出>
    - 中风险问题：
      - <列出>
    - 需人工复核事项：
      - <列出；如没有写未发现>

    ## 主要依据汇总

    - <法律政策1>
    - <法律政策2>
    - <法律政策3>

    以下是招标文件正文，请基于正文输出完整审查结果：
    """
)


def maybe_disable_qwen_thinking(prompt: str, model: str) -> str:
    lower_model = model.lower()
    if "qwen" in lower_model and not prompt.lstrip().startswith("/no_think"):
        return "/no_think\n" + prompt
    return prompt


def run_textutil(docx_path: Path) -> str | None:
    try:
        proc = subprocess.run(
            ["textutil", "-convert", "txt", "-stdout", str(docx_path)],
            capture_output=True,
            check=True,
        )
        return proc.stdout.decode("utf-8", errors="replace")
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None


def extract_docx_via_xml(docx_path: Path) -> str:
    with zipfile.ZipFile(docx_path) as zf:
        xml_bytes = zf.read("word/document.xml")

    root = ET.fromstring(xml_bytes)
    body = root.find("w:body", DOCX_NS)
    if body is None:
        return ""

    lines: list[str] = []

    def text_from_paragraph(p: ET.Element) -> str:
        parts: list[str] = []
        for node in p.iter():
            tag = node.tag.rsplit("}", 1)[-1]
            if tag == "t" and node.text:
                parts.append(node.text)
            elif tag == "tab":
                parts.append("\t")
            elif tag in {"br", "cr"}:
                parts.append("\n")
        return "".join(parts).strip()

    for child in body:
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            text = text_from_paragraph(child)
            lines.append(text if text else "")
        elif tag == "tbl":
            for tr in child.findall("w:tr", DOCX_NS):
                cells: list[str] = []
                for tc in tr.findall("w:tc", DOCX_NS):
                    cell_lines = []
                    for p in tc.findall("w:p", DOCX_NS):
                        t = text_from_paragraph(p)
                        if t:
                            cell_lines.append(t)
                    cells.append(" ".join(cell_lines).strip())
                row = "\t".join(cells).strip()
                if row:
                    lines.append(row)
            lines.append("")

    return "\n".join(lines)


def extract_text(input_path: Path) -> str:
    suffix = input_path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return input_path.read_text(encoding="utf-8")
    if suffix == ".docx":
        text = run_textutil(input_path)
        if text:
            return text
        return extract_docx_via_xml(input_path)
    raise ValueError(f"Unsupported input type: {suffix}")


def call_chat_completion(
    base_url: str,
    model: str,
    api_key: str | None,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_tokens: int,
    timeout: int,
) -> dict:
    url = base_url.rstrip("/") + "/chat/completions"
    body = {
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    if "qwen" in model.lower():
        body["chat_template_kwargs"] = {"enable_thinking": False}
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    return json.loads(raw)


def extract_stream_text(delta: object) -> str:
    if isinstance(delta, str):
        return delta
    if isinstance(delta, list):
        parts: list[str] = []
        for item in delta:
            if isinstance(item, dict) and item.get("type") == "text" and item.get("text"):
                parts.append(str(item["text"]))
            elif isinstance(item, str):
                parts.append(item)
        return "".join(parts)
    return ""


def call_chat_completion_stream(
    base_url: str,
    model: str,
    api_key: str | None,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_tokens: int,
    timeout: int,
    on_text: Callable[[str], None] | None = None,
) -> dict:
    url = base_url.rstrip("/") + "/chat/completions"
    body = {
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    if "qwen" in model.lower():
        body["chat_template_kwargs"] = {"enable_thinking": False}
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")

    collected: list[str] = []
    last_payload: dict = {}
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            for raw_line in resp:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line or not line.startswith("data:"):
                    continue
                payload_text = line[5:].strip()
                if payload_text == "[DONE]":
                    break
                payload = json.loads(payload_text)
                last_payload = payload
                choices = payload.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta", {})
                text_chunk = extract_stream_text(delta.get("content"))
                if text_chunk:
                    collected.append(text_chunk)
                    if on_text:
                        on_text(text_chunk)
    except urllib.error.HTTPError:
        raise

    content = "".join(collected).strip()
    if content:
        return {
            "choices": [{"message": {"content": content}}],
            "stream_collected": True,
            "last_chunk": last_payload,
        }
    return last_payload or {"choices": [{"message": {"content": ""}}]}


def build_prompt(document_text: str, prompt_prefix: str) -> str:
    return f"{prompt_prefix.strip()}\n\n{document_text.strip()}\n"


def save_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def extract_response_text(response: dict) -> str | None:
    try:
        message = response["choices"][0]["message"]
    except Exception:
        return None

    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text" and item.get("text"):
                parts.append(str(item["text"]))
            elif isinstance(item, str):
                parts.append(item)
        text = "".join(parts).strip()
        if text:
            return text
    return None

