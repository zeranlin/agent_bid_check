from __future__ import annotations

import re
from collections import Counter

from app.pipelines.v2.problem_layer.models import ProblemLayerResult

from .schemas import DocumentDomain, DomainClassification


DOMAIN_RULES: dict[DocumentDomain, dict[str, object]] = {
    "engineering_maintenance_construction": {
        "policy_id": "domain-policy-engineering-v1",
        "patterns": (
            r"操场",
            r"跑道",
            r"篮球场",
            r"维护项目",
            r"施工",
            r"维修",
            r"养护",
            r"改造",
            r"修缮",
            r"施工工程",
            r"维护工程",
            r"修缮工程",
        ),
    },
    "goods_procurement": {
        "policy_id": "domain-policy-goods-v1",
        "patterns": (
            r"货物类",
            r"家具采购",
            r"学生宿舍家具",
            r"设备采购",
            r"机电设备",
            r"柴油发电机组",
            r"货物采购",
            r"机组",
        ),
    },
    "service_procurement": {
        "policy_id": "domain-policy-service-v1",
        "patterns": (
            r"物业",
            r"服务采购",
            r"物业管理服务",
            r"保洁",
            r"管理服务",
            r"清洗服务",
            r"服务项目",
        ),
    },
}


def _build_domain_blob(document_name: str, comparison, problems: ProblemLayerResult) -> str:
    parts: list[str] = [document_name]
    parts.extend(cluster.title for cluster in getattr(comparison, "clusters", []) if str(cluster.title).strip())
    for cluster in getattr(comparison, "clusters", []):
        parts.extend(str(item).strip() for item in getattr(cluster, "source_excerpts", []) if str(item).strip())
        parts.extend(str(item).strip() for item in getattr(cluster, "source_locations", []) if str(item).strip())
    for problem in getattr(problems, "problems", []):
        parts.append(problem.canonical_title)
        parts.extend(str(item).strip() for item in getattr(problem, "topic_sources", []) if str(item).strip())
    return "\n".join(part for part in parts if str(part).strip())


def classify_document_domain(document_name: str, comparison, problems: ProblemLayerResult) -> DomainClassification:
    blob = _build_domain_blob(document_name, comparison, problems)
    scores: Counter[str] = Counter()
    evidence: dict[str, list[str]] = {key: [] for key in DOMAIN_RULES}

    for domain, rule in DOMAIN_RULES.items():
        for pattern in rule["patterns"]:
            if re.search(pattern, blob):
                scores[domain] += 1
                evidence[domain].append(pattern)

    if not scores:
        return DomainClassification(
            document_domain="goods_procurement",
            domain_confidence=0.4,
            domain_evidence=["default_fallback:goods_procurement"],
            domain_policy_id=str(DOMAIN_RULES["goods_procurement"]["policy_id"]),
        )

    ranked = scores.most_common()
    primary, primary_score = ranked[0]
    secondary_score = ranked[1][1] if len(ranked) > 1 else 0
    confidence = 0.6 if primary_score == secondary_score else 0.75
    if primary_score >= secondary_score + 2:
        confidence = 0.88
    if primary_score >= 4:
        confidence = max(confidence, 0.93)

    return DomainClassification(
        document_domain=primary,  # type: ignore[arg-type]
        domain_confidence=confidence,
        domain_evidence=evidence[primary][:5],
        domain_policy_id=str(DOMAIN_RULES[primary]["policy_id"]),
    )
