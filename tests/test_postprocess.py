from app.review.postprocess import lightly_postprocess_review


def test_postprocess_preserves_existing_risk_title_and_adds_missing_fields() -> None:
    raw = """
# 招标文件合规审查结果

## 风险点1：资格条件可能限制竞争

- 问题定性：高风险
- 原文位置：第1页
- 风险判断：
  - 存在限制竞争风险
"""
    result = lightly_postprocess_review(raw, "sample.docx")
    assert "## 风险点1：资格条件可能限制竞争" in result
    assert "- 审查类型：未发现" in result
    assert "- 原文摘录：未发现" in result
    assert "- 法律/政策依据：" in result
    assert "- 整改建议：" in result


def test_postprocess_leaves_non_template_content_as_is() -> None:
    raw = "这是自由格式结果，没有风险点标题。"
    result = lightly_postprocess_review(raw, "sample.docx")
    assert result == "这是自由格式结果，没有风险点标题。\n"


def test_postprocess_adds_summary_sections_when_missing() -> None:
    raw = """
## 风险点1：评分标准不明确

- 问题定性：中风险
- 审查类型：评分办法
- 原文位置：第2页
- 原文摘录：评分标准描述不够量化
- 风险判断：
  - 评审尺度不统一
- 法律/政策依据：
  - 需人工复核
- 整改建议：
  - 补充量化规则
"""
    result = lightly_postprocess_review(raw, "sample.docx")
    assert "## 综合判断" in result
    assert "## 主要依据汇总" in result
