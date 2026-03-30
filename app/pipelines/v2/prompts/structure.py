STRUCTURE_LAYER_NOTE = """\
V2 结构增强层采用“弱结构切分 + 模块概率识别”：
- 先按标题、枚举、关键词切分候选章节
- 再为章节分配可能模块
- 后续专题深审只召回最相关的章节和片段
"""


STRUCTURE_LLM_SYSTEM_PROMPT = """\
你是政府采购招标文件结构识别助手。
你的任务不是做合规判断，而是只判断每个章节片段更可能属于哪个模块。
你必须只输出 JSON，不要输出 Markdown，不要解释。
"""


STRUCTURE_LLM_USER_PROMPT = """\
请对下面这些“规则模式下置信度不足”的章节片段进行模块复判。

可选模块只有：
- qualification
- scoring
- contract
- acceptance
- technical
- procedure
- policy

请返回 JSON，对每个 index 给出：
- module：你判断的主模块
- confidence：0 到 1 之间的小数
- reason：一句简短原因
- keywords：你依据的 1-4 个关键词

输出格式：
{
  "sections": [
    {
      "index": 1,
      "module": "technical",
      "confidence": 0.78,
      "reason": "章节主要描述技术标准和检测要求。",
      "keywords": ["标准", "检测", "参数"]
    }
  ]
}
"""
