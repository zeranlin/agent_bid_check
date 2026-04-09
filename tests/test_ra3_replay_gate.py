from __future__ import annotations

import json
from pathlib import Path

from app.common.parser import parse_review_markdown
from app.web.v2_app import create_app, load_result_by_run_id


FUJIAN_RA3_RUN = Path("data/results/v2/20260409-ra3f-fujian-091728/final_output.json")
DIESEL_RA3_RUN = Path("data/results/v2/20260409-ra3f-diesel-091728/final_output.json")
FUJIAN_W011_RUN = Path("data/results/v2/20260409-w011-fujian/final_output.json")
DIESEL_W011_RUN = Path("data/results/v2/20260409-w011-diesel/final_output.json")


def _load_output(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _find_layer(data: dict, title: str) -> str | None:
    for layer in ("formal_risks", "pending_review_items", "excluded_risks"):
        if any(item.get("title") == title for item in data.get(layer, [])):
            return layer
    return None


def test_ra3_fujian_replay_blocks_template_and_downgrades_reminders() -> None:
    data = _load_output(FUJIAN_RA3_RUN)

    assert _find_layer(data, "验收标准模糊且依赖后续合同确定，存在需求条款合规风险") == "excluded_risks"
    assert _find_layer(data, "评分标准中设置特定品牌倾向性条款") == "formal_risks"
    formal_titles = {item.get("title") for item in data.get("formal_risks", [])}
    assert "验收流程与考核机制表述笼统，缺乏可操作性" in {item.get("title") for item in data.get("pending_review_items", [])}
    assert "唱标内容存在模糊表述，可能引发争议" in {item.get("title") for item in data.get("pending_review_items", [])}
    assert all(
        not any(token in str(title) for token in ("需确认", "需警惕", "需结合项目规模评估"))
        for title in formal_titles
    )


def test_ra3_diesel_replay_downgrades_weak_acceptance_items_and_keeps_hard_risks() -> None:
    data = _load_output(DIESEL_RA3_RUN)

    assert _find_layer(data, "将项目验收方案纳入评审因素，违反评审规则合规性要求") == "formal_risks"
    assert _find_layer(data, "评分描述量化口径不足，存在评审一致性风险") == "formal_risks"
    assert _find_layer(data, "验收标准来源表述不清，容易引发验收依据理解歧义") == "pending_review_items"
    assert _find_layer(data, "验收主体及流程描述不完整，缺乏不合格处理机制") == "pending_review_items"


def test_ra3_web_view_only_displays_admitted_formal_risks(monkeypatch) -> None:
    run_dir = DIESEL_RA3_RUN.parent
    monkeypatch.setattr("app.web.v2_app.find_run_dir", lambda run_id: run_dir if run_id == "ra3-diesel" else None)

    app = create_app()
    with app.test_request_context():
        result = load_result_by_run_id("ra3-diesel")

    assert result is not None
    displayed_titles = [item["title"] for item in result["review_view"]["all_cards"]]
    assert "将项目验收方案纳入评审因素，违反评审规则合规性要求" in displayed_titles
    assert "验收标准来源表述不清，容易引发验收依据理解歧义" not in displayed_titles
    assert "验收主体及流程描述不完整，缺乏不合格处理机制" not in displayed_titles


def test_w011_fujian_replay_stabilizes_titles_and_severity() -> None:
    data = _load_output(FUJIAN_W011_RUN)
    formal_by_title = {item.get("title"): item for item in data.get("formal_risks", [])}

    info_item = formal_by_title.get("评分标准中“信息化软件服务能力”要求著作权人为投标人，可能限制竞争")
    no_crime_item = formal_by_title.get("商务条款中关于“无犯罪证明”的提交时限及无效投标处理存在法律风险")

    assert info_item is not None
    assert info_item.get("severity") == "中风险"
    assert no_crime_item is not None
    assert no_crime_item.get("severity") == "中风险"
    assert "评分标准中设置“信息化软件服务能力”要求，存在倾向性" not in formal_by_title
    assert "评分标准中设置“无犯罪证明”作为中标后承诺，存在法律风险" not in formal_by_title


def test_w011_diesel_replay_downgrades_missing_type_and_absorbs_supporting_risk() -> None:
    data = _load_output(DIESEL_W011_RUN)

    assert _find_layer(data, "拒绝进口 vs 外标/国外部件引用矛盾风险") == "formal_risks"
    assert _find_layer(data, "检测报告及认证资质要求缺失或表述不明") != "formal_risks"
    assert _find_layer(data, "电磁兼容标准引用格式混乱且编号不完整") is None


def test_w011_final_output_markdown_and_web_are_consistent(monkeypatch) -> None:
    run_dir = DIESEL_W011_RUN.parent
    monkeypatch.setattr("app.web.v2_app.find_run_dir", lambda run_id: run_dir if run_id == "w011-diesel" else None)

    app = create_app()
    with app.test_request_context():
        result = load_result_by_run_id("w011-diesel")

    assert result is not None
    final_output = _load_output(DIESEL_W011_RUN)
    markdown = parse_review_markdown((run_dir / "final_review.md").read_text(encoding="utf-8"))
    web_titles = [item["title"] for item in result["review_view"]["all_cards"]]
    final_titles = [item["title"] for item in final_output.get("formal_risks", [])]
    markdown_titles = [item.title for item in markdown.risk_points]

    assert set(final_titles) == set(markdown_titles) == set(web_titles)
    assert "检测报告及认证资质要求缺失或表述不明" not in web_titles
    assert "电磁兼容标准引用格式混乱且编号不完整" not in web_titles
