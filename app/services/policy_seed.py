from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Policy
from app.services.policy_kb import sync_policy_knowledge_base


def seed_policies(session: Session) -> None:
    policy_payloads = [
        {
            "id": "SH-2026-0001",
            "title": "高新技术企业研发补贴",
            "region_code": "SH-PD",
            "level": "city",
            "source_url": "https://shpolicy.ssme.sh.gov.cn/knowledge/#/detail2/ZZ41584670",
            "effective_from": date(2026, 1, 1),
            "effective_to": date(2026, 12, 31),
            "hard_conditions": [
                {"field": "region_code", "op": "eq", "value": "SH-PD", "label": "企业注册地需在浦东新区"},
                {"field": "rd_ratio", "op": ">=", "value": 5, "label": "研发投入占比需>=5%"},
                {
                    "field": "qualification_tags",
                    "op": "contains",
                    "value": "高新技术企业",
                    "label": "需具备高新技术企业资质",
                },
            ],
            "scoring_conditions": [
                {"field": "ip_count", "op": ">=", "value": 10, "weight": 20, "label": "知识产权数量>=10"}
            ],
            "required_materials": ["高新技术企业证书", "研发费用专项审计报告"],
        },
        {
            "id": "SH-2026-0002",
            "title": "专精特新企业培育支持",
            "region_code": "SH-PD",
            "level": "district",
            "source_url": "https://shpolicy.ssme.sh.gov.cn/knowledge/#/detail2/ZZ36037570",
            "effective_from": date(2026, 1, 1),
            "effective_to": date(2026, 12, 31),
            "hard_conditions": [
                {
                    "field": "employee_scale",
                    "op": "in",
                    "value": ["10-49", "50-99", "100-299"],
                    "label": "企业规模需在中小企业区间",
                },
                {
                    "field": "qualification_tags",
                    "op": "contains",
                    "value": "创新型中小企业",
                    "label": "建议具备创新型中小企业资质",
                },
            ],
            "scoring_conditions": [
                {"field": "rd_ratio", "op": ">=", "value": 3, "weight": 15, "label": "研发投入占比>=3%"}
            ],
            "required_materials": ["创新型中小企业认定材料", "近两年财务报表"],
        },
        {
            "id": "SH-2026-0003",
            "title": "中小企业稳岗补贴",
            "region_code": "SH-PD",
            "level": "city",
            "source_url": "https://shpolicy.ssme.sh.gov.cn/knowledge/#/detail2/ZZ44201630",
            "effective_from": date(2026, 1, 1),
            "effective_to": date(2026, 12, 31),
            "hard_conditions": [
                {"field": "region_code", "op": "eq", "value": "SH-PD", "label": "企业注册地需在浦东新区"}
            ],
            "scoring_conditions": [],
            "required_materials": ["社保缴纳证明", "劳动用工台账"],
        },
    ]

    existing_map = {
        p.id: p for p in session.scalars(select(Policy).where(Policy.id.in_([x["id"] for x in policy_payloads]))).all()
    }
    for payload in policy_payloads:
        existing = existing_map.get(payload["id"])
        if existing:
            for key, value in payload.items():
                setattr(existing, key, value)
        else:
            session.add(Policy(**payload))

    session.commit()
    sync_policy_knowledge_base(session)
