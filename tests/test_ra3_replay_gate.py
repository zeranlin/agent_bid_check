from __future__ import annotations

import json
from pathlib import Path

from app.common.parser import parse_review_markdown
from app.web.v2_app import create_app, load_result_by_run_id


FUJIAN_RA3_RUN = Path("data/results/v2/20260409-ra3f-fujian-091728/final_output.json")
DIESEL_RA3_RUN = Path("data/results/v2/20260409-ra3f-diesel-091728/final_output.json")
FUJIAN_W011_RUN = Path("data/results/v2/20260409-w011-fujian/final_output.json")
DIESEL_W011_RUN = Path("data/results/v2/20260409-w011-diesel/final_output.json")
FUJIAN_W012_RUN = Path("data/results/v2/20260409-w012-fujian/final_output.json")
DIESEL_W012_RUN = Path("data/results/v2/20260409-w012-diesel/final_output.json")
FUJIAN_W013_RUN = Path("data/results/v2/20260409-w013-fujian/final_output.json")
DIESEL_W013_RUN = Path("data/results/v2/20260409-w013-diesel/final_output.json")
W014_RUN = Path("data/results/v2/20260409-w014-post/final_output.json")
AR1_FUZHOU_RUN = Path("data/results/v2/20260409-ar1-fuzhou/final_output.json")
AR2_FUZHOU_RUN = Path("data/results/v2/20260409-ar2-fuzhou/final_output.json")
Q1_DIESEL_RUN = Path("data/results/v2/20260410-q1f-diesel/final_output.json")
Q3_DIESEL_RUN = Path("data/results/v2/20260410-q3-diesel/final_output.json")
Q3_FUZHOU_RUN = Path("data/results/v2/20260410-q3-fuzhou/final_output.json")
Q4_DIESEL_RUN = Path("data/results/v2/20260410-q4-diesel/final_output.json")
Q4_FUZHOU_RUN = Path("data/results/v2/20260410-q4-fuzhou/final_output.json")


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


def test_w012_diesel_replay_keeps_single_certification_main_risk(monkeypatch) -> None:
    data = _load_output(DIESEL_W012_RUN)
    formal_titles = [item.get("title") for item in data.get("formal_risks", [])]

    assert formal_titles.count("以特定认证及特定发证机构作为评分条件，存在倾向性评分和限制竞争风险") == 1
    assert "以特定认证证书作为高分条件，存在限定特定供应商和倾向性评分风险" not in formal_titles
    assert "评分标准中要求特定非强制性认证证书，具有倾向性" not in formal_titles
    assert "指定特定认证机构，具有排他性" not in formal_titles
    assert "综合实力评分中三项体系认证‘全有或全无’设置不合理" not in formal_titles

    run_dir = DIESEL_W012_RUN.parent
    monkeypatch.setattr("app.web.v2_app.find_run_dir", lambda run_id: run_dir if run_id == "w012-diesel" else None)
    app = create_app()
    with app.test_request_context():
        result = load_result_by_run_id("w012-diesel")
    assert result is not None
    web_titles = [
        item["title"]
        for item in result["review_view"]["all_cards"]
        if "认证" in item["title"] or "证书" in item["title"] or "发证机构" in item["title"]
    ]
    assert [title for title in formal_titles if "认证" in title or "证书" in title or "发证机构" in title] == web_titles


def test_w013_basis_summary_uses_admission_formal_only_for_fujian() -> None:
    run_dir = FUJIAN_W013_RUN.parent
    final_output = _load_output(FUJIAN_W013_RUN)
    markdown = parse_review_markdown((run_dir / "final_review.md").read_text(encoding="utf-8"))

    assert final_output["basis_summary"] == markdown.basis_summary
    assert "《政府采购需求管理办法》第二十一条：履约验收方案应当包括验收主体、验收方式、验收标准、验收程序等内容。" not in final_output["basis_summary"]


def test_w013_basis_summary_uses_admission_formal_only_for_diesel(monkeypatch) -> None:
    run_dir = DIESEL_W013_RUN.parent
    final_output = _load_output(DIESEL_W013_RUN)
    markdown = parse_review_markdown((run_dir / "final_review.md").read_text(encoding="utf-8"))

    assert final_output["basis_summary"] == markdown.basis_summary
    assert "《强制性产品认证管理规定》：列入目录的产品必须经过认证。" not in final_output["basis_summary"]

    monkeypatch.setattr("app.web.v2_app.find_run_dir", lambda run_id: run_dir if run_id == "w013-diesel" else None)
    app = create_app()
    with app.test_request_context():
        result = load_result_by_run_id("w013-diesel")
    assert result is not None
    web_titles = [item["title"] for item in result["review_view"]["all_cards"]]
    formal_titles = [item["title"] for item in final_output["formal_risks"]]
    assert set(web_titles) == set(formal_titles)


def test_w014_fuzhou_replay_fixes_false_positive_layering_and_cluster_dedup(monkeypatch) -> None:
    run_dir = W014_RUN.parent
    data = _load_output(W014_RUN)
    formal_titles = [item.get("title") for item in data.get("formal_risks", [])]
    pending_titles = [item.get("title") for item in data.get("pending_review_items", [])]
    excluded_titles = [item.get("title") for item in data.get("excluded_risks", [])]

    assert "商务条款中关于“无犯罪证明”的提交时限及无效投标处理存在法律风险" not in formal_titles
    assert "缺乏预付款安排，资金压力较大" not in formal_titles
    assert "开标记录签字确认的默认认可条款" not in formal_titles
    assert "远程开标解密时限及后果条款的合理性审查" not in formal_titles
    assert "商务条款中采购人单方变更权过大且结算方式不明" in formal_titles
    assert "验收标准引用“厂家验收标准”及“样品”，存在模糊表述和单方裁量风险" in formal_titles
    assert "技术参数存在错误或异常标准引用，可能导致技术要求失真" in formal_titles
    assert "检测报告限定福建省检测机构，存在检测机构地域限制风险" in formal_titles
    assert formal_titles.count("技术参数过细且特征化，存在指向性风险") == 1
    assert formal_titles.count("样品要求过细且评审规则失衡，存在样品门槛风险") == 1
    assert "缺乏预付款安排，资金压力较大" in pending_titles
    assert "远程开标解密时限及后果条款的合理性审查" in pending_titles
    assert "开标记录签字确认的默认认可条款" in excluded_titles
    assert "验收时间条款留白，导致履约验收时点不明确，缺乏可操作性" in excluded_titles

    monkeypatch.setattr("app.web.v2_app.find_run_dir", lambda run_id: run_dir if run_id == "w014-fuzhou" else None)
    app = create_app()
    with app.test_request_context():
        result = load_result_by_run_id("w014-fuzhou")

    assert result is not None
    web_titles = [item["title"] for item in result["review_view"]["all_cards"]]
    markdown = parse_review_markdown((run_dir / "final_review.md").read_text(encoding="utf-8"))
    markdown_titles = [item.title for item in markdown.risk_points]
    assert set(web_titles) == set(formal_titles) == set(markdown_titles)
    assert "商务条款中关于“无犯罪证明”的提交时限及无效投标处理存在法律风险" not in web_titles


def test_ar1_fuzhou_replay_proves_final_layering_no_longer_comes_from_compare(monkeypatch) -> None:
    run_dir = AR1_FUZHOU_RUN.parent
    comparison = _load_output(run_dir / "comparison.json")
    admission = _load_output(run_dir / "risk_admission_output.json")
    final_output = _load_output(AR1_FUZHOU_RUN)

    assert comparison["metadata"]["pending_review_items"] == []
    assert comparison["metadata"]["excluded_risks"] == []
    assert len(admission["pending_review_items"]) > 0
    assert len(admission["excluded_risks"]) > 0
    assert any(item["title"] == "缺乏预付款安排，资金压力较大" for item in admission["pending_review_items"])
    assert any(item["title"] == "开标记录签字确认的默认认可条款" for item in admission["excluded_risks"])
    compare_titles = [item["title"] for item in comparison["clusters"]]
    assert "缺乏预付款安排，资金压力较大" in compare_titles
    assert "商务条款中采购人单方变更权过大且结算方式不明" in compare_titles

    monkeypatch.setattr("app.web.v2_app.find_run_dir", lambda run_id: run_dir if run_id == "ar1-fuzhou" else None)
    app = create_app()
    with app.test_request_context():
        result = load_result_by_run_id("ar1-fuzhou")

    assert result is not None
    web_titles = [item["title"] for item in result["review_view"]["all_cards"]]
    assert "商务条款中采购人单方变更权过大且结算方式不明" in web_titles
    assert "缺乏预付款安排，资金压力较大" not in web_titles


def test_ar2_replay_requires_governance_to_stop_emitting_final_layers() -> None:
    run_dir = AR2_FUZHOU_RUN.parent
    governed = _load_output(run_dir / "governed_output.json")
    admission = _load_output(run_dir / "risk_admission_output.json")

    assert "governed_candidates" in governed
    assert "formal_risks" not in governed
    assert "pending_review_items" not in governed
    assert "excluded_risks" not in governed
    assert all("target_layer" not in item.get("decision", {}) for item in governed.get("governed_candidates", []))
    assert len(admission["formal_risks"]) > 0
    assert len(admission["pending_review_items"]) > 0
    assert len(admission["excluded_risks"]) > 0


def test_q1_diesel_replay_cleans_formal_pool_and_records_formal_gate_trace() -> None:
    run_dir = Q1_DIESEL_RUN.parent
    final_output = _load_output(Q1_DIESEL_RUN)
    admission = _load_output(run_dir / "risk_admission_output.json")

    formal_titles = {item["title"] for item in final_output["formal_risks"]}
    pending_titles = {item["title"] for item in final_output["pending_review_items"]}

    assert "拒绝进口 vs 外标/国外部件引用矛盾风险" in formal_titles
    assert "检测报告及认证资质要求缺失或表述不明" not in formal_titles
    assert "检测报告及认证资质要求缺失或表述不明" in pending_titles
    assert "节能环保产品政策条款缺失" not in formal_titles
    assert "节能环保产品政策条款缺失" in pending_titles

    pending_item = next(item for item in admission["pending_review_items"] if item["title"] == "检测报告及认证资质要求缺失或表述不明")
    pending_decision = admission["decisions"][pending_item["rule_id"]]
    formal_item = next(item for item in admission["formal_risks"] if item["title"] == "拒绝进口 vs 外标/国外部件引用矛盾风险")
    formal_decision = admission["decisions"][formal_item["rule_id"]]

    assert pending_decision["formal_gate_passed"] is False
    assert pending_decision["formal_gate_rule"] == "downgrade_evidence_insufficient"
    assert formal_decision["formal_gate_passed"] is True
    assert formal_decision["formal_gate_rule"] in {"stable_family_hard_evidence_gate", "hard_evidence_gate", "hard_formal_rule", "formal_whitelist"}


def test_q2_diesel_replay_absorbs_supporting_formal_titles_and_keeps_trace() -> None:
    run_dir = Path("data/results/v2/20260410-q2-diesel")
    final_output = _load_output(run_dir / "final_output.json")
    admission = _load_output(run_dir / "risk_admission_output.json")

    formal_titles = {item["title"] for item in final_output["formal_risks"]}

    assert "拒绝进口 vs 外标/国外部件引用矛盾风险" in formal_titles
    assert "燃油标准引用已废止标准 GB252" not in formal_titles

    main = next(item for item in admission["formal_risks"] if item["title"] == "拒绝进口 vs 外标/国外部件引用矛盾风险")
    absorbed = main["extras"].get("absorbed_risks", [])
    absorbed_titles = {item["absorbed_title"] for item in absorbed}

    assert "燃油标准引用已废止标准 GB252" in absorbed_titles
    assert any(item["blocked_from_formal"] is True for item in absorbed if item["absorbed_title"] == "燃油标准引用已废止标准 GB252")


def test_q3_diesel_replay_only_keeps_stable_hard_risks_in_formal() -> None:
    run_dir = Q3_DIESEL_RUN.parent
    final_output = _load_output(Q3_DIESEL_RUN)
    admission = _load_output(run_dir / "risk_admission_output.json")

    formal_titles = {item["title"] for item in final_output["formal_risks"]}
    pending_titles = {item["title"] for item in final_output["pending_review_items"]}

    assert "要求现场技术人员必须为制造商原厂工程师，存在排斥代理商风险" not in formal_titles
    assert "要求现场技术人员必须为制造商原厂工程师，存在排斥代理商风险" in pending_titles
    assert "踏勘现场作为资格性审查条件，违反规定" not in formal_titles
    assert "项目负责人学历与职称要求过高，可能构成不合理门槛" not in formal_titles
    assert "以特定认证及特定发证机构作为评分条件，存在倾向性评分和限制竞争风险" in formal_titles

    item = next(i for i in admission["pending_review_items"] if i["title"] == "要求现场技术人员必须为制造商原厂工程师，存在排斥代理商风险")
    decision = admission["decisions"][item["rule_id"]]
    assert decision["formal_gate_rule"] == "stable_family_gate_block"
    assert decision["formal_gate_family_allowed"] is False
    assert decision["formal_gate_evidence_passed"] is True


def test_q3_fuzhou_replay_keeps_confirmed_hard_risks_and_drops_unstable_formal_items() -> None:
    run_dir = Q3_FUZHOU_RUN.parent
    final_output = _load_output(Q3_FUZHOU_RUN)
    admission = _load_output(run_dir / "risk_admission_output.json")

    formal_titles = {item["title"] for item in final_output["formal_risks"]}
    pending_titles = {item["title"] for item in final_output["pending_review_items"]}

    assert "商务条款中采购人单方变更权过大且结算方式不明" in formal_titles
    assert "验收标准引用“厂家验收标准”及“样品”，存在模糊表述和单方裁量风险" in formal_titles
    assert "家具产品执行标准引用不明确，仅使用'国家标准'泛称" not in formal_titles
    assert "政策依据引用不完整，存在表述截断风险" not in formal_titles
    assert "家具产品执行标准引用不明确，仅使用'国家标准'泛称" in pending_titles
    assert "政策依据引用不完整，存在表述截断风险" in pending_titles

    hard_item = next(i for i in admission["formal_risks"] if i["title"] == "验收标准引用“厂家验收标准”及“样品”，存在模糊表述和单方裁量风险")
    hard_decision = admission["decisions"][hard_item["rule_id"]]
    assert hard_decision["formal_gate_rule"] == "formal_whitelist"
    assert hard_decision["formal_gate_exception_whitelist_hit"] is True


def test_q4_diesel_replay_keeps_formal_pool_stable_and_records_registry_source() -> None:
    run_dir = Q4_DIESEL_RUN.parent
    final_output = _load_output(Q4_DIESEL_RUN)
    admission = _load_output(run_dir / "risk_admission_output.json")

    formal_titles = [item["title"] for item in final_output["formal_risks"]]

    assert formal_titles == [
        "拒绝进口 vs 外标/国外部件引用矛盾风险",
        "强制性标准条款未按评审规则标注★，可能导致实质性响应边界不清",
        "将项目验收方案纳入评审因素，违反评审规则合规性要求",
        "以特定认证及特定发证机构作为评分条件，存在倾向性评分和限制竞争风险",
        "验收检测及相关部门验收费用表述笼统，存在费用边界不清和潜在转嫁风险",
        "业绩评分限定特定行政区域，存在地域排斥风险",
        "项目负责人评分项设置过高且累计分值不合理，存在重复评价和倾向性风险",
    ]

    import_item = next(item for item in admission["formal_risks"] if item["title"] == "拒绝进口 vs 外标/国外部件引用矛盾风险")
    import_decision = admission["decisions"][import_item["rule_id"]]
    region_item = next(item for item in admission["formal_risks"] if item["title"] == "业绩评分限定特定行政区域，存在地域排斥风险")
    region_decision = admission["decisions"][region_item["rule_id"]]

    assert import_decision["formal_gate_rule"] == "registry_family_hard_evidence_gate"
    assert import_decision["formal_gate_registry_rule_id"] == "R-001"
    assert import_decision["formal_gate_registry_source"] == "registry"
    assert import_decision["formal_gate_registry_resolution"] == "matched"
    assert region_decision["formal_gate_rule"] == "registry_family_hard_evidence_gate"
    assert region_decision["formal_gate_registry_rule_id"] == "GOV-regional_performance"
    assert region_decision["formal_gate_registry_source"] == "governance_config"
    assert region_decision["formal_gate_registry_resolution"] == "matched"


def test_q4_fuzhou_replay_keeps_formal_pool_stable_and_uses_registry_driven_gate(monkeypatch) -> None:
    run_dir = Q4_FUZHOU_RUN.parent
    final_output = _load_output(Q4_FUZHOU_RUN)
    admission = _load_output(run_dir / "risk_admission_output.json")

    formal_titles = [item["title"] for item in final_output["formal_risks"]]

    assert formal_titles == [
        "验收检测及相关部门验收费用表述笼统，存在费用边界不清和潜在转嫁风险",
        "技术参数存在错误或异常标准引用，可能导致技术要求失真",
        "检测报告限定福建省检测机构，存在检测机构地域限制风险",
        "样品要求过细且评审规则失衡，存在样品门槛风险",
        "商务条款中采购人单方变更权过大且结算方式不明",
        "技术参数过细且特征化，存在指向性风险",
        "履约监督与解除条件失衡",
        "验收标准引用“厂家验收标准”及“样品”，存在模糊表述和单方裁量风险",
    ]

    abnormal_item = next(item for item in admission["formal_risks"] if item["title"] == "技术参数存在错误或异常标准引用，可能导致技术要求失真")
    abnormal_decision = admission["decisions"][abnormal_item["rule_id"]]
    whitelist_item = next(item for item in admission["formal_risks"] if item["title"] == "商务条款中采购人单方变更权过大且结算方式不明")
    whitelist_decision = admission["decisions"][whitelist_item["rule_id"]]

    assert abnormal_decision["formal_gate_rule"] == "registry_family_hard_evidence_gate"
    assert abnormal_decision["formal_gate_registry_rule_id"] == "GOV-abnormal_standard_reference"
    assert abnormal_decision["formal_gate_registry_source"] == "governance_config"
    assert abnormal_decision["formal_gate_registry_resolution"] == "matched"
    assert whitelist_decision["formal_gate_rule"] == "formal_whitelist"

    monkeypatch.setattr("app.web.v2_app.find_run_dir", lambda run_id: run_dir if run_id == "q4-fuzhou" else None)
    app = create_app()
    with app.test_request_context():
        result = load_result_by_run_id("q4-fuzhou")

    assert result is not None
    web_titles = [item["title"] for item in result["review_view"]["all_cards"]]
    markdown_titles = [item.title for item in parse_review_markdown((run_dir / "final_review.md").read_text(encoding="utf-8")).risk_points]
    assert set(web_titles) == set(formal_titles) == set(markdown_titles)
