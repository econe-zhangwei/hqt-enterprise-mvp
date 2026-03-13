from __future__ import annotations

import hashlib
import re
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Policy, PolicyKnowledgeDocument

_TITLE_PATTERN = re.compile(r"^\d+．\s*(.+)$")
_SECTION_STOP_PATTERN = re.compile(r"^[（(][一二三四五六七八九十]+[）)]")
_FOOTER_PATTERN = re.compile(r"^陈灵林\s+\d+|^第\s*\d+\s*页")
_POLICY_HINTS = ("资金", "基金", "认定", "评价入库", "培育体系", "支持", "补贴")
_CULTURE_PREFIXES = ["R", "P", "N", "S"]
_TECH_PREFIXES = ["C", "I", "J", "M"]
_OFFICIAL_SOURCE_MAP = {
    "上海市促进文化创意产业发展财政扶持资金": "https://www.shanghai.gov.cn/jcsfbsbtz/20230517/c62cfb7ddde147ada48dc7959302c663.html",
    "浦东新区宣传文化发展基金": "https://www.pudong.gov.cn/zwgk/006004003/2022/302256677.html",
    "科技型中小企业评价入库政策与服务": "https://www.shanghai.gov.cn/nw12344/20240703/8d5db20233c3474a98bf4f410619ddb6.html",
    "上海市科技型中小企业技术创新资金": "https://stcsm.sh.gov.cn/zwgk/wgjd/20240529/f98f34efdd36415f951eb4d0f7d98f4d.html",
    "高新技术企业认定": "https://kjgl.stcsm.sh.gov.cn/wdcms/xmsb/625.jhtml",
    "专精特新企业梯度培育体系": "https://www.shanghai.gov.cn/gwk/search/content/8a5e879096ed8f3c0196f0f7e5526aff",
    "张江科学城专项发展资金": "https://www.pudong.gov.cn/zwgk/106008001/2022/106008001001_11324.html",
}
_OUTLINE_HEADINGS = {
    "政策概述": ("政策概述", "体系概述", "定位"),
    "支持内容": ("支持方向", "支持方向与范围", "支持方式与标准", "各级定位与关系"),
    "申报时间": ("申报时间", "时间安排", "申报时间与平台"),
    "申报平台": ("申报平台", "申报平台与流程", "申报时间与平台"),
    "申报条件": ("申报主体条件", "评价标准（需同时满足）", "评价标准", "核心认定条件", "创新能力评价"),
    "办理流程": ("基本流程", "申报平台与流程"),
    "后期管理": ("后期管理",),
    "核心价值": ("对普通企业的核心价值", "对常规企业的核心价值", "入库的核心价值", "普通企业应对策略"),
}


def _clean_line(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip())


def _clean_title(title: str) -> str:
    title = _clean_line(title)
    title = re.split(r"[：:]", title, maxsplit=1)[0]
    title = title.rstrip("。；; ")
    title = title.replace("“", "").replace("”", "")
    return title


def _preview_url(document_id: str) -> str:
    return f"/api/v1/knowledge-base/documents/{document_id}/preview"


def _official_source_url(title: str) -> str:
    return _OFFICIAL_SOURCE_MAP.get(title, "")


def _extract_materials(body: str) -> list[str]:
    materials: list[str] = []
    patterns = [
        r"准备核心佐证[:：]\s*([^\n]+)",
        r"提交申报书、([^\n]+)",
        r"需准备[“\"]?([^。\n]+)[”\"]?",
    ]
    for pattern in patterns:
        match = re.search(pattern, body)
        if not match:
            continue
        text = match.group(1)
        for item in re.split(r"[、，,；;]\s*", text):
            cleaned = item.strip("“”\" ")
            if cleaned and len(cleaned) <= 30:
                materials.append(cleaned)
    return list(dict.fromkeys(materials))[:6]


def _normalize_title(title: str) -> str:
    return re.sub(r"[“”\"'：: \-]", "", title)


def _split_summary_items(text: str, limit: int = 3) -> list[str]:
    cleaned = text.replace("\n", " ")
    segments = re.split(r"(?:\d+\.\s*|•|●|；|。)", cleaned)
    items = []
    for seg in segments:
        value = _clean_line(seg)
        if len(value) < 6:
            continue
        items.append(value)
    if not items:
        items = [_clean_line(cleaned)]
    return items[:limit]


def _extract_heading_blocks(body: str) -> dict[str, str]:
    lines = [_clean_line(line) for line in body.splitlines() if _clean_line(line)]
    blocks: dict[str, list[str]] = {}
    current_heading: str | None = None
    for line in lines:
        matched_heading = None
        for heading_group in _OUTLINE_HEADINGS.values():
            for heading in heading_group:
                if line.startswith(heading):
                    matched_heading = heading
                    break
            if matched_heading:
                break
        if matched_heading:
            current_heading = matched_heading
            blocks.setdefault(current_heading, [])
            suffix = line[len(matched_heading) :].strip(" ：:")
            if suffix:
                blocks[current_heading].append(suffix)
            continue
        if current_heading:
            blocks.setdefault(current_heading, []).append(line)
    return {key: "\n".join(value).strip() for key, value in blocks.items() if value}


def _infer_support_type(title: str) -> str:
    if "认定" in title or "培育体系" in title:
        return "资质认定"
    if "评价入库" in title:
        return "资质入库"
    if "资金" in title or "基金" in title or "补贴" in title:
        return "财政补贴"
    return "政策支持"


def _base_policy_payload(document: PolicyKnowledgeDocument, title: str) -> dict:
    level = "district" if "浦东新区" in title else "city"
    region_code = "SH-PD" if "浦东新区" in title else "SH-ALL"
    policy_id = "KB-" + hashlib.sha1(f"{document.id}:{title}".encode("utf-8")).hexdigest()[:10].upper()
    return {
        "id": policy_id,
        "title": title,
        "region_code": region_code,
        "level": level,
        "source_url": _official_source_url(title),
        "effective_from": date(2026, 1, 1),
        "effective_to": date(2026, 12, 31),
        "hard_conditions": [],
        "scoring_conditions": [],
        "required_materials": [],
    }


def _infer_conditions(title: str, body: str) -> tuple[list[dict], list[dict], list[str]]:
    hard_conditions: list[dict] = []
    scoring_conditions: list[dict] = []
    required_materials = _extract_materials(body)

    if "浦东新区" in title or "在浦东新区注册" in body or "在浦东新区注册或实际经营" in body:
        hard_conditions.append(
            {"field": "region_code", "op": "eq", "value": "SH-PD", "label": "企业注册地需在浦东新区"}
        )

    if any(keyword in title for keyword in ["文化", "文创", "宣传文化"]):
        hard_conditions.append(
            {
                "field": "industry_code",
                "op": "prefix_in",
                "value": _CULTURE_PREFIXES,
                "label": "行业需属于文化创意/公共服务相关领域",
            }
        )

    if any(keyword in title for keyword in ["科技型中小企业", "技术创新资金", "高新技术企业", "专精特新"]):
        hard_conditions.append(
            {
                "field": "industry_code",
                "op": "prefix_in",
                "value": _TECH_PREFIXES,
                "label": "行业需属于科技创新或先进制造相关领域",
            }
        )

    if "高新技术企业认定" in title:
        hard_conditions.extend(
            [
                {"field": "rd_ratio", "op": ">=", "value": 3, "label": "研发费用占比需达到高企认定最低线"},
                {"field": "ip_count", "op": ">=", "value": 1, "label": "需具备至少1项核心知识产权"},
            ]
        )
        scoring_conditions.append({"field": "ip_count", "op": ">=", "value": 5, "weight": 12, "label": "知识产权数量较充足"})
        required_materials.extend(["知识产权证书", "研发费用专项审计报告"])

    elif "科技型中小企业评价入库" in title:
        hard_conditions.extend(
            [
                {"field": "rd_ratio", "op": ">=", "value": 1, "label": "建议已形成持续研发投入"},
                {
                    "field": "employee_scale",
                    "op": "in",
                    "value": ["10-49", "50-99", "100-299"],
                    "label": "企业规模需处于中小企业区间",
                },
            ]
        )
        scoring_conditions.append({"field": "ip_count", "op": ">=", "value": 1, "weight": 10, "label": "已有知识产权或科技成果"})
        required_materials.extend(["知识产权证书", "研发项目立项材料"])

    elif "技术创新资金" in title:
        hard_conditions.extend(
            [
                {"field": "rd_ratio", "op": ">=", "value": 20, "label": "研发费用占比需不低于20%"},
                {"field": "ip_count", "op": ">=", "value": 1, "label": "项目核心技术需具备自主知识产权"},
                {
                    "field": "qualification_tags",
                    "op": "contains",
                    "value": "科技型中小企业",
                    "label": "建议已取得科技型中小企业入库编号",
                },
            ]
        )
        scoring_conditions.append({"field": "qualification_tags", "op": "contains", "value": "创新型中小企业", "weight": 8, "label": "已具备创新型中小企业资质"})
        required_materials.extend(["科技型中小企业入库编号", "项目申报书"])

    elif "专精特新" in title:
        hard_conditions.extend(
            [
                {
                    "field": "employee_scale",
                    "op": "in",
                    "value": ["10-49", "50-99", "100-299"],
                    "label": "企业规模需处于中小企业区间",
                },
                {
                    "field": "qualification_tags",
                    "op": "contains",
                    "value": "创新型中小企业",
                    "label": "建议先具备创新型中小企业资质",
                },
                {"field": "rd_ratio", "op": ">=", "value": 3, "label": "研发投入占比建议不低于3%"},
            ]
        )
        scoring_conditions.append({"field": "ip_count", "op": ">=", "value": 5, "weight": 10, "label": "知识产权储备越充分越有利"})
        required_materials.extend(["创新型中小企业认定材料", "近两年财务报表"])

    elif "宣传文化发展基金" in title:
        required_materials.extend(["项目方案", "预算说明"])

    elif "文化创意产业发展财政扶持资金" in title:
        required_materials.extend(["可行性报告", "财务报表"])

    dedup_materials = [item for item in dict.fromkeys(required_materials) if item]
    return hard_conditions, scoring_conditions, dedup_materials[:6]


def extract_policy_sections(text: str) -> list[dict]:
    lines = [_clean_line(line) for line in text.splitlines()]
    title_rows: list[tuple[int, str]] = []
    for idx, line in enumerate(lines):
        match = _TITLE_PATTERN.match(line)
        if not match:
            continue
        title = _clean_title(match.group(1))
        if len(title) < 4 or len(title) > 50:
            continue
        if not any(hint in title for hint in _POLICY_HINTS):
            continue
        title_rows.append((idx, title))

    sections: list[dict] = []
    for pos, (line_index, title) in enumerate(title_rows):
        next_index = title_rows[pos + 1][0] if pos + 1 < len(title_rows) else len(lines)
        body_lines: list[str] = []
        for line in lines[line_index + 1 : next_index]:
            if not line or _FOOTER_PATTERN.search(line) or _SECTION_STOP_PATTERN.match(line):
                continue
            body_lines.append(line)
        body = "\n".join(body_lines).strip()
        if len(body) < 120:
            continue
        sections.append({"title": title, "body": body})
    return sections


def sync_policies_from_knowledge_base(session: Session) -> int:
    docs = session.scalars(
        select(PolicyKnowledgeDocument).where(PolicyKnowledgeDocument.source_type != "policy_structured")
    ).all()
    synced = 0
    existing_by_title = {p.title: p for p in session.scalars(select(Policy)).all()}
    for doc in docs:
        for item in extract_policy_sections(doc.cleaned_text):
            title = item["title"]
            body = item["body"]
            hard_conditions, scoring_conditions, materials = _infer_conditions(title, body)
            if not hard_conditions:
                continue
            payload = _base_policy_payload(doc, title)
            payload["hard_conditions"] = hard_conditions
            payload["scoring_conditions"] = scoring_conditions
            payload["required_materials"] = materials
            existing = existing_by_title.get(title) or session.get(Policy, payload["id"])
            if existing:
                for key, value in payload.items():
                    setattr(existing, key, value)
            else:
                existing = Policy(**payload)
                session.add(existing)
                existing_by_title[title] = existing
            synced += 1
    session.commit()
    return synced


def _find_policy_body_in_documents(session: Session, policy: Policy) -> str | None:
    target = _normalize_title(policy.title)
    docs = session.scalars(
        select(PolicyKnowledgeDocument).where(PolicyKnowledgeDocument.source_type != "policy_structured")
    ).all()
    for doc in docs:
        for section in extract_policy_sections(doc.cleaned_text):
            if _normalize_title(section["title"]) == target:
                return section["body"]
    return None


def _region_label(region_code: str) -> str:
    return {
        "SH-ALL": "全上海",
        "SH-PD": "浦东新区",
        "SH-MH": "闵行区",
    }.get(region_code, region_code)


def _level_label(level: str) -> str:
    return {"city": "市级", "district": "区级"}.get(level, level)


def _ensure_outline_section(outline: list[dict], title: str, items: list[str]) -> None:
    if any(section["title"] == title for section in outline):
        return
    values = [item for item in items if item]
    if values:
        outline.append({"title": title, "items": values[:3]})


def build_policy_outline(policy: Policy, session: Session) -> list[dict]:
    outline: list[dict] = []
    body = _find_policy_body_in_documents(session, policy)
    blocks = _extract_heading_blocks(body) if body else {}

    for section_title, heading_candidates in _OUTLINE_HEADINGS.items():
        for heading in heading_candidates:
            if heading in blocks:
                outline.append({"title": section_title, "items": _split_summary_items(blocks[heading])})
                break

    if policy.hard_conditions:
        outline.append(
            {
                "title": "匹配条件",
                "items": [item.get("label", "") for item in policy.hard_conditions if item.get("label")][:4],
            }
        )
    if policy.scoring_conditions:
        outline.append(
            {
                "title": "加分关注",
                "items": [item.get("label", "") for item in policy.scoring_conditions if item.get("label")][:3],
            }
        )
    if policy.required_materials:
        outline.append({"title": "所需材料", "items": policy.required_materials[:6]})

    support_type = _infer_support_type(policy.title)
    _ensure_outline_section(
        outline,
        "政策概述",
        [f"该政策属于{_level_label(policy.level)}政策，适用区域为{_region_label(policy.region_code)}。", f"当前支持类型为{support_type}。"],
    )
    _ensure_outline_section(
        outline,
        "支持内容",
        [
            f"主要提供{support_type}相关支持，具体标准以主管部门当期通知为准。",
            "建议先核对本企业是否具备对应资质或项目基础，再准备申报材料。",
        ],
    )
    _ensure_outline_section(
        outline,
        "申报时间",
        [f"当前有效期为 {policy.effective_from} 至 {policy.effective_to or '长期'}。", "正式申报时间以官方通知或系统开放时间为准。"],
    )
    _ensure_outline_section(
        outline,
        "申报条件",
        [item.get("label", "") for item in policy.hard_conditions if item.get("label")],
    )
    _ensure_outline_section(
        outline,
        "办理流程",
        ["先确认企业画像与资质条件，再准备材料并进入官方渠道填报。", "提交后通常需经过区级或市级审核，请关注补正与公示通知。"],
    )
    _ensure_outline_section(
        outline,
        "所需材料",
        policy.required_materials[:6],
    )

    deduped: list[dict] = []
    seen_titles: set[str] = set()
    for section in outline:
        title = section["title"]
        items = [item for item in section["items"] if item]
        if title in seen_titles or not items:
            continue
        deduped.append({"title": title, "items": items[:3]})
        seen_titles.add(title)
    return deduped[:8]
