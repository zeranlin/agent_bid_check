from app.review.normalize import normalize_review_markdown
from app.review.parser import parse_review_markdown


def test_parse_review_markdown_handles_standard_risk_sections() -> None:
    raw = """
# 招标文件合规审查结果

审查对象：`sample.docx`

说明：
- 本审查基于你提供的招标文件文本进行。

## 风险点1：资格条件不合理

- 问题定性：高风险
- 审查类型：资格条件
- 原文位置：第1页
- 原文摘录：要求供应商成立满五年
- 风险判断：
  - 限制新设供应商参与
- 法律/政策依据：
  - 《政府采购法》第二十二条
- 整改建议：
  - 删除成立年限要求
"""
    report = parse_review_markdown(raw)
    assert report.subject == "sample.docx"
    assert len(report.risk_points) == 1
    assert report.risk_points[0].title == "资格条件不合理"
    assert report.risk_points[0].severity == "高风险"
    assert report.risk_points[0].risk_judgment == ["限制新设供应商参与"]


def test_normalize_review_markdown_fills_missing_fields_without_rewriting_title() -> None:
    raw = """
## 风险点1：评分标准不明确

- 问题定性：中风险
- 原文位置：第2页
- 风险判断：
  - 评分口径不清
"""
    result = normalize_review_markdown(raw, "sample.docx")
    assert "## 风险点1：评分标准不明确" in result
    assert "- 审查类型：未发现" in result
    assert "- 原文摘录：未发现" in result
    assert "- 法律/政策依据：" in result
    assert "- 整改建议：" in result


def test_normalize_review_markdown_supports_alt_headings_and_generates_summary() -> None:
    raw = """
### 1. 技术参数存在品牌倾向

- 问题定性：高风险
- 审查类型：技术参数
- 原文位置：第3页
- 原文摘录：要求同品牌配套
- 风险判断：
  - 可能指向特定供应商
- 法律/政策依据：
  - 需人工复核
- 整改建议：
  - 改为兼容性要求
"""
    result = normalize_review_markdown(raw, "sample.docx")
    assert "## 风险点1：技术参数存在品牌倾向" in result
    assert "## 综合判断" in result
    assert "## 主要依据汇总" in result
    assert "  - 技术参数存在品牌倾向" in result


def test_normalize_review_markdown_supports_table_style_risk_blocks() -> None:
    raw = """
## 二、详细风险点清单

### 1. 资格条件设置不当（高风险）

| 项目 | 内容 |
| :--- | :--- |
| **问题标题** | 设置与项目履约无直接关联的特定行业认证及企业性质限制 |
| **问题定性** | **高风险** |
| **审查类型** | 资格条件/限制竞争 |
| **原文位置** | 第一章 招标公告 |
| **原文摘录** | "投标人须具备保安服务认证证书" |
| **风险判断** | 1. 与项目无直接关联。<br>2. 可能限制竞争。 |
| **法律/政策依据** | 《中华人民共和国政府采购法》第二十二条。 |
| **整改建议** | 1. 删除该资格条件。<br>2. 调整为评分项。 |
"""
    result = normalize_review_markdown(raw, "sample.docx")
    assert "## 风险点1：资格条件设置不当" in result
    assert "- 问题定性：高风险" in result
    assert "- 审查类型：资格条件/限制竞争" in result
    assert "- 原文位置：第一章 招标公告" in result
    assert "  - 1. 与项目无直接关联。" in result
    assert "  - 2. 可能限制竞争。" in result


def test_parse_review_markdown_ignores_overview_and_advice_sections() -> None:
    raw = """
## 一、审查综述

经审查发现多个问题。

## 二、详细风险点清单

### 1. 资格条件设置不当（高风险）

| 项目 | 内容 |
| :--- | :--- |
| **问题定性** | **高风险** |
| **审查类型** | 资格条件 |
| **原文位置** | 第一章 |
| **原文摘录** | 不合理资格要求 |
| **风险判断** | 存在限制竞争。 |
| **法律/政策依据** | 《政府采购法》第二十二条。 |
| **整改建议** | 删除该条款。 |

## 三、综合整改建议

1. 建议整体修订招标文件。
"""
    report = parse_review_markdown(raw)
    assert len(report.risk_points) == 1
    assert report.risk_points[0].title == "资格条件设置不当"


def test_normalize_filters_heading_and_separator_noise_in_list_fields() -> None:
    raw = """
## 风险点1：违约金比例过高

- 问题定性：中风险
- 审查类型：商务条款/公平性
- 原文位置：第三章
- 原文摘录：违约金 20%
- 风险判断：
  - 比例偏高
- 法律/政策依据：
  - 《中华人民共和国民法典》
- 整改建议：
  - 调整违约金比例
  - --
  - ## 五、其他问题
"""
    result = normalize_review_markdown(raw, "sample.docx")
    assert "## 五、其他问题" not in result
    assert "\n  - --" not in result
