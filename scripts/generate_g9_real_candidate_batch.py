from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = Path("/Users/linzeran/code/2026-zn/test_target/合规性审查点反馈表分层映射清单.md")

CANDIDATE_ROOT = ROOT / "rules" / "candidates"
SOURCE_INDEX_PATH = CANDIDATE_ROOT / "sources" / "external-review-points-real-2026-04-07.md"
IMPORT_PATH = CANDIDATE_ROOT / "imports" / "candidate_rules_2026-04-07_real_batch_001.yaml"
LEDGER_PATH = CANDIDATE_ROOT / "mappings" / "candidate_rule_ledger_2026-04-07_real_batch_001.yaml"
SUMMARY_PATH = CANDIDATE_ROOT / "mappings" / "candidate_rule_triage_summary_2026-04-07_real_batch_001.yaml"
SNAPSHOT_PATH = CANDIDATE_ROOT / "snapshots" / "SNAP-2026-04-07-triage-002.md"

BATCH_ID = "CAND-IMPORT-2026-04-07-REAL-001"
SNAPSHOT_ID = "SNAP-2026-04-07-triage-002"
TASK_ID = "Task-G9"

ABSORBED_RULES = {
    "不得将“项目验收方案”作为评审因素，": ("R-003", "R-003A"),
    "不得将“付款方式”作为评审因素。": ("R-004", "R-004-F"),
    "不得要求提供赠品、回扣或者与采购无关的其他商品、服务": ("R-005", "R-005"),
    "含有GB（不含GB/T）或国家强制性标准的描述中需含有★号": ("R-002", "R-002"),
    "非进口项目不得设置国际标准": ("R-001", "R-001"),
    "不得要求中标人承担验收产生的检测费用": ("R-007", "R-007"),
    "不得限定证书的认证机构": ("R-006", "R-006"),
}

DROP_TEXTS = {
    "货物类质保期的不得超出24个月",
    "涉及高空服务的项目，必须设置特种作业操作证（作业类别：高处作业）",
}

CAPABILITY_TEXTS = {
    "内容一致性校验",
    "参数要求偏离强制性国家标准",
    "引用标准与采购标的物无关",
    "进口产品厂家证明文件要求",
    "内容应能定位到章节、段落、表格、附件",
    "表格证据至少应定位到行",
    "表格证据较优应定位到单元格",
    "表格证据最佳应定位到单元格内问题片段",
    "文件乱码检测",
    "疑似错别字检查",
    "不得出现主观性表述",
    "不得设置敏感风险词",
}

CONDITIONAL_TEXTS = {
    "证书设置的合理性",
    "会计服务需设定《会计师事务所执业证书》",
    "法律服务需设定《律师事务所执业许可证》",
    "正确设置供应商医疗资质",
    "正确设置《医疗器械注册证》",
    "燃气具安装维修资质",
    "体系认证证书不得要求特定认证范围",
    "需明确投标人资质证明及资料提交形式",
    "设定样品制作标准与要求",
    "合理设定学位材料为加分条件",
    "合理设定学历材料为加分条件",
    "设定职称证书需限定专业",
    "400万以下小额项目不得设置国家级证书",
    "评定分离项目未采用自定法定标",
    "评定分离项目设定候选供应商数量须为三家",
    "评定分离项目须采用综合评分法评标",
    "除重大项目和特定品目外的项目，评标办法不得选用评定分离",
    "明确最高限价",
    "货物采购项目须设定专门面向中小企业采购",
    "须设定履约保证金退还方式",
    "要求提供CMA标识检测报告的需设定相关检测标准",
    "检测报告具有CMA标识的相关描述是否合规",
    "检测报告数量原则上不得超过五份",
    "检测标准一致性审查",
    "设定货物参数的标准与要求",
    "货物类采购文件需设置合规的技术参数区间描述",
    "不得出现品牌型号",
    "不得限定或者指定特定的商标、品牌或者供应商",
    "不得用主观性的描述定义品牌要求",
    "限定或指定特定专利",
    "限定或指定特定专利/技术参数需设置为区间值",
    "货物不接受进口产品的不得要求生产厂家授权等证明文件",
    "货物接受进口产品的必须要求生产厂家授权等证明文件",
    "招标公告未载明是否接受进口产品",
    "不得限定原厂维修或售后",
    "采购强制节能产品的，需提供《中国节能产品认证证书》",
    "合理设置本国产品声明函",
    "非进口项目不得要求CE认证、ROHS认证、FCC、UL、能源之星CE等强制认证",
    "不得出现强制节能产品",
    "必须设定履约验收方案",
    "采购人应当在收到发票后10个工作日内完成资金支付",
    "采购文件必须载明付款方式",
    "设置合理的售后方案",
    "设置合理的培训服务方案",
    "设置合理的应急预案",
    "设置清晰、完整的物业管理服务范围",
    "详细说明服务范围及服务内容",
    "货物采购项目必须设定交货地点",
    "货物采购项目必须设定交货时间",
    "服务采购项目必须设定服务地点",
    "服务采购项目必须设定服务期限",
    "服务合同履行期限不得超过36个月",
    "货物合同履行期限不得超过24个月",
    "采购人允许采用分包方式履行合同的，未在采购文件中明确分包的具体内容、金额（比例）",
    "需设定联合体企业合同金额比例",
    "按政策要求设置项目经费比例",
}

CONDITIONAL_SECTION_HINTS = ("RP-012", "RP-013", "RP-014")

NEGATIVE_CONDITIONS = {
    "formal_rule": ["已被现有规则吸收或需落入明确业务场景时，避免重复立项和重复纳管。"],
    "conditional_rule": ["仅在采购品类、地区政策或业务画像满足前提时才可继续纳管。"],
    "capability_item": ["不直接升级为正式规则，应由召回、知识映射、结构化或证据能力承接。"],
    "drop": ["保留来源痕迹即可，不进入正式规则纳管和运行时规则开发。"],
}


def parse_source_items() -> list[dict[str, str]]:
    section_stack: list[tuple[int, str]] = []
    items: list[dict[str, str]] = []
    for raw_line in SOURCE_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        heading = re.match(r"^(#+)\s+`?(.*?)`?\s*$", line)
        if heading:
            level = len(heading.group(1))
            title = heading.group(2).strip()
            while section_stack and section_stack[-1][0] >= level:
                section_stack.pop()
            section_stack.append((level, title))
            continue

        bullet = re.match(r"^- `(.+?)`(?:[:：].*)?$", line)
        if not bullet:
            continue

        text = bullet.group(1).strip()
        titles = [title for _, title in section_stack]
        if not any(title.startswith(("4.", "5.")) for title in titles):
            continue
        if text in {"评审", "评审项"} or text.startswith("{这里填写新增的审查点名称}"):
            continue

        section_codes = []
        for title in titles:
            match = re.search(r"(RP|CCK)-\d+(?:-S\d+)?", title)
            if match:
                section_codes.append(match.group(0))
        section_code = section_codes[-1] if section_codes else "GENERAL"
        top_section = next((title for title in titles if title.startswith(("4.", "5."))), titles[-1] if titles else "未分类")
        sub_section = section_codes[-1] if section_codes else (titles[-1] if titles else "未分类")
        items.append(
            {
                "source_rule_text": text,
                "source_category": top_section,
                "source_section": section_code,
                "source_subsection": sub_section,
            }
        )

    deduped: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in items:
        text = item["source_rule_text"]
        if text in seen:
            continue
        seen.add(text)
        deduped.append(item)
    return deduped


def classify(item: dict[str, str]) -> dict[str, str]:
    text = item["source_rule_text"]
    source_section = item["source_section"]

    if text in ABSORBED_RULES:
        target_rule_id, task_id = ABSORBED_RULES[text]
        return {
            "decision": "formal_rule",
            "decision_reason": f"语义稳定且已被现有正式规则 {target_rule_id} 吸收，本轮只保留候选来源痕迹与吸收关系，不重复立项。",
            "target_rule_id": target_rule_id,
            "target_layer": "formal_risks",
            "profile_dependency": "none",
            "samples_status": "ready",
            "tests_status": "ready",
            "task_id": task_id,
            "status": "absorbed",
        }

    if text in DROP_TEXTS:
        return {
            "decision": "drop",
            "decision_reason": "来源文档已明确提示退出全国通用母版或删除，本轮保留痕迹但不继续纳管。",
            "target_rule_id": "",
            "target_layer": "excluded_risks",
            "profile_dependency": "依赖地方/品类 profile，当前不进入通用规则库",
            "samples_status": "not_planned",
            "tests_status": "not_planned",
            "task_id": TASK_ID,
            "status": "rejected",
        }

    if text in CAPABILITY_TEXTS or source_section.startswith("CCK-"):
        return {
            "decision": "capability_item",
            "decision_reason": "更适合作为 cross-cutting 能力或知识映射能力承接，不直接沉淀为单条正式规则。",
            "target_rule_id": "",
            "target_layer": "capability",
            "profile_dependency": "依赖结构召回、表格定位、知识映射或文本质量能力",
            "samples_status": "missing",
            "tests_status": "missing",
            "task_id": TASK_ID,
            "status": "triaged",
        }

    if text in CONDITIONAL_TEXTS or any(hint in source_section for hint in CONDITIONAL_SECTION_HINTS):
        return {
            "decision": "conditional_rule",
            "decision_reason": "业务价值存在，但依赖采购品类、政策画像、知识边界或标题重写，不宜直接按全国统一正式规则启用。",
            "target_rule_id": "",
            "target_layer": "pending_review_items",
            "profile_dependency": "存在地区政策、品类画像、知识图谱或标题条件化依赖",
            "samples_status": "missing",
            "tests_status": "missing",
            "task_id": TASK_ID,
            "status": "triaged",
        }

    return {
        "decision": "formal_rule",
        "decision_reason": "禁限或 must-have 语义较稳定，可作为首轮真实候选中的正式规则纳管对象继续推进。",
        "target_rule_id": "",
        "target_layer": "formal_risks",
        "profile_dependency": "none",
        "samples_status": "seeded",
        "tests_status": "seeded",
        "task_id": TASK_ID,
        "status": "triaged",
    }


def build_entries(items: list[dict[str, str]]) -> tuple[list[dict[str, object]], Counter]:
    entries: list[dict[str, object]] = []
    counts: Counter = Counter()
    for idx, item in enumerate(items, start=1):
        decision_meta = classify(item)
        candidate_id = f"RC-{idx:03d}"
        entry = {
            "candidate_id": candidate_id,
            "source_name": "合规性审查点反馈表分层映射清单",
            "source_rule_text": item["source_rule_text"],
            "source_category": item["source_category"],
            "source_section": item["source_section"],
            "source_subsection": item["source_subsection"],
            "decision": decision_meta["decision"],
            "decision_reason": decision_meta["decision_reason"],
            "target_rule_id": decision_meta["target_rule_id"],
            "target_layer": decision_meta["target_layer"],
            "profile_dependency": decision_meta["profile_dependency"],
            "negative_conditions": NEGATIVE_CONDITIONS[decision_meta["decision"]],
            "samples_status": decision_meta["samples_status"],
            "tests_status": decision_meta["tests_status"],
            "task_id": decision_meta["task_id"],
            "status": decision_meta["status"],
            "snapshot_id": SNAPSHOT_ID,
        }
        entries.append(entry)
        counts[entry["decision"]] += 1
    return entries, counts


def write_yaml(path: Path, payload: dict) -> None:
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")


def write_source_index(total_candidates: int, counts: Counter) -> None:
    content = f"""# 真实候选规则来源说明（G9）

- 来源名称：`合规性审查点反馈表分层映射清单`
- 来源时间：`2026-04-07`
- 来源路径：`{SOURCE_PATH}`
- 导入批次：`{BATCH_ID}`
- 任务单：`{TASK_ID}`
- 来源说明：基于用户指定的真实来源文件开展首轮候选规则分流，不伪造独立来源副本，只在候选池内保留来源索引与治理产物。

## 真实导入说明

- 原文在“反馈表总体情况”中声明唯一审查点约 `150` 个。
- 本轮从 `RP-* / CCK-* / 建议条件化或删除项` 中按治理视角抽取并去重后，形成 `total_candidates = {total_candidates}` 条首轮候选治理条目。
- 条目数略高于文内统计，是因为本轮同时保留了 `cross-cutting` 能力项、`待删除/退出全国母版` 项和 `建议条件化` 项，便于后续 `G10+` 继续演进。

## 首轮分流统计

- `formal_rule = {counts['formal_rule']}`
- `conditional_rule = {counts['conditional_rule']}`
- `capability_item = {counts['capability_item']}`
- `drop = {counts['drop']}`

## 对应治理文件

- 导入文件：`rules/candidates/imports/{IMPORT_PATH.name}`
- 分流台账：`rules/candidates/mappings/{LEDGER_PATH.name}`
- 统计摘要：`rules/candidates/mappings/{SUMMARY_PATH.name}`
- 分流快照：`rules/candidates/snapshots/{SNAPSHOT_PATH.name}`
"""
    SOURCE_INDEX_PATH.write_text(content, encoding="utf-8")


def write_snapshot(total_candidates: int, counts: Counter) -> None:
    content = f"""# {SNAPSHOT_ID}

## 快照编号

- `{SNAPSHOT_ID}`

## 输入来源

- 来源索引：`rules/candidates/sources/{SOURCE_INDEX_PATH.name}`
- 导入文件：`rules/candidates/imports/{IMPORT_PATH.name}`

## 分流范围

- 分流台账：`rules/candidates/mappings/{LEDGER_PATH.name}`
- 统计摘要：`rules/candidates/mappings/{SUMMARY_PATH.name}`
- 覆盖候选：`RC-001 ~ RC-{total_candidates:03d}`
- 分流结论覆盖：`formal_rule / conditional_rule / capability_item / drop`

## 任务单范围

- 当前任务：`{TASK_ID}`
- 上游底座：`Task-G6 / Task-G7 / Task-G8`
- 本轮目标：将用户指定真实来源文件正式接入候选池并完成首轮真实分流

## 状态摘要

- 真实来源索引：已建立
- 真实导入批次：已建立
- 首轮分流台账：已建立
- 首轮统计结果：`formal_rule={counts['formal_rule']}, conditional_rule={counts['conditional_rule']}, capability_item={counts['capability_item']}, drop={counts['drop']}`
- 正式规则运行链路：本轮仅建立吸收关系与纳管建议，不直接变更 `rules/registry/`

## 回滚说明

### 场景 1：真实候选分流判断错误

- 回滚对象：
  - `rules/candidates/mappings/{LEDGER_PATH.name}`
  - `rules/candidates/mappings/{SUMMARY_PATH.name}`
  - `rules/candidates/snapshots/{SNAPSHOT_PATH.name}`
- 处理方式：
  - 保留真实导入批次不动，只回退分流判断和统计摘要
  - 修正后生成新的 `SNAP-YYYY-MM-DD-triage-XXX` 快照继续追踪

### 场景 2：后续首批纳管引入误报

- 回滚对象：
  - 对应迁移批次快照 `SNAP-YYYY-MM-DD-migrate-XXX`
  - `rules/registry/` 中对应正式规则
  - 对应样本、测试和任务单记录
- 处理方式：
  - 先按迁移批次回退，不直接破坏真实候选原始分流结果

### 场景 3：已被吸收的现有规则后续发现边界问题

- 回滚对象：
  - `rules/registry/R-xxx.yaml`
  - 本批分流台账中的吸收关系记录
  - 对应补强任务单与测试
- 处理方式：
  - 优先补强或降级现有规则，再决定是否调整候选吸收关系
"""
    SNAPSHOT_PATH.write_text(content, encoding="utf-8")


def main() -> int:
    items = parse_source_items()
    entries, counts = build_entries(items)

    import_payload = {
        "batch_id": BATCH_ID,
        "source_name": "合规性审查点反馈表分层映射清单",
        "source_path": str(SOURCE_PATH),
        "source_description": "基于用户指定真实来源文件生成的首轮真实候选导入批次，不伪造源文件语义。",
        "candidate_items": [
            {
                "candidate_id": entry["candidate_id"],
                "source_rule_text": entry["source_rule_text"],
                "source_category": entry["source_category"],
                "source_section": entry["source_section"],
            }
            for entry in entries
        ],
    }
    ledger_payload = {
        "ledger_version": 1,
        "decisions": ["formal_rule", "conditional_rule", "capability_item", "drop"],
        "entries": entries,
    }

    first_priority_candidates = [
        {
            "candidate_id": entry["candidate_id"],
            "source_rule_text": entry["source_rule_text"],
            "decision": entry["decision"],
            "target_rule_id": entry["target_rule_id"],
            "priority_reason": "已被现有规则吸收" if entry["target_rule_id"] else "可作为下一批正式纳管优先对象",
        }
        for entry in entries
        if entry["decision"] == "formal_rule"
    ][:12]
    capability_backlog = [
        {
            "candidate_id": entry["candidate_id"],
            "source_rule_text": entry["source_rule_text"],
            "source_section": entry["source_section"],
        }
        for entry in entries
        if entry["decision"] == "capability_item"
    ][:12]
    absorbed_candidates = [
        {
            "candidate_id": entry["candidate_id"],
            "source_rule_text": entry["source_rule_text"],
            "absorbed_by_rule_id": entry["target_rule_id"],
        }
        for entry in entries
        if entry["status"] == "absorbed"
    ]
    summary_payload = {
        "batch_id": BATCH_ID,
        "snapshot_id": SNAPSHOT_ID,
        "task_id": TASK_ID,
        "total_candidates": len(entries),
        "counts": {key: counts[key] for key in ["formal_rule", "conditional_rule", "capability_item", "drop"]},
        "first_priority_candidates": first_priority_candidates,
        "capability_backlog": capability_backlog,
        "absorbed_candidates": absorbed_candidates,
        "notes": [
            "来源文档正文声明唯一审查点约150个，本轮按治理视角抽取去重后形成154条真实候选治理条目。",
            "已被现有规则吸收的条目仅登记吸收关系，不重复立项。",
            "对边界不清、地域/品类依赖强或更适合作为能力建设的条目，优先分流到 conditional_rule 或 capability_item。",
        ],
    }

    write_source_index(len(entries), counts)
    write_yaml(IMPORT_PATH, import_payload)
    write_yaml(LEDGER_PATH, ledger_payload)
    write_yaml(SUMMARY_PATH, summary_payload)
    write_snapshot(len(entries), counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
