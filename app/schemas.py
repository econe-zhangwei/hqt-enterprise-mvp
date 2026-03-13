from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class APIResponse(BaseModel):
    code: int = 0
    message: str = "ok"
    data: Any | None = None


class EnterpriseProfileIn(BaseModel):
    enterprise_name: str = Field(min_length=2, max_length=120)
    uscc: str = Field(min_length=18, max_length=18)
    region_code: str
    industry_code: str
    contact_name: str = Field(min_length=2, max_length=30)
    contact_mobile: str = Field(pattern=r"^1[3-9]\d{9}$")
    employee_scale: str | None = None
    revenue_range: str | None = None
    rd_ratio: float | None = Field(default=None, ge=0, le=100)
    qualification_tags: list[str] = []
    ip_count: int | None = Field(default=None, ge=0)


class EnterpriseProfileOut(EnterpriseProfileIn):
    id: str

    model_config = ConfigDict(from_attributes=True)


class CreateMatchTaskIn(BaseModel):
    enterprise_id: str


class MatchResultOut(BaseModel):
    policy_id: str
    policy_title: str
    source_url: str
    eligibility: str
    score: float
    reasons: list[str]
    missing_items: list[str]
    next_action: str


class MatchTaskResultOut(BaseModel):
    status: str
    summary: dict
    results: list[MatchResultOut]


class PolicyOut(BaseModel):
    id: str
    title: str
    region_code: str
    level: str
    source_url: str
    effective_from: date
    effective_to: date | None
    hard_conditions: list[dict]
    scoring_conditions: list[dict]
    required_materials: list[str]
    support_type: str | None = None
    updated_at: datetime | str | None = None
    outline_sections: list[dict] = []

    model_config = ConfigDict(from_attributes=True)


class KnowledgeImportIn(BaseModel):
    source_type: str = Field(pattern=r"^(url|file|raw_text)$")
    source_uri: str | None = None
    title: str | None = None
    policy_id: str | None = None
    raw_text: str | None = None


class KnowledgeDocumentOut(BaseModel):
    id: str
    policy_id: str | None
    title: str
    source_type: str
    source_uri: str
    source_domain: str | None
    ingest_status: str

    model_config = ConfigDict(from_attributes=True)


class KnowledgeSearchIn(BaseModel):
    query: str = Field(min_length=2)
    policy_id: str | None = None
    limit: int = Field(default=5, ge=1, le=10)


class QAIn(BaseModel):
    enterprise_id: str
    question: str
    context_policy_id: str | None = None


class QAOut(BaseModel):
    answer: str
    citations: list[dict]
    recommend_handoff: bool
    confidence: float
    risk_flags: list[str]
    handoff_reason: str | None = None
    next_actions: list[str]
    evidence_snippets: list[str]
    intent: str | None = None
    selected_policy_id: str | None = None
    selected_policy_title: str | None = None
    clarification_needed: bool = False


class QAHandoffTicketIn(BaseModel):
    enterprise_id: str
    question: str = Field(min_length=2)
    answer: str = Field(min_length=2)
    context_policy_id: str | None = None
    handoff_reason: str | None = None
    callback_time: str | None = None


class ServiceTicketIn(BaseModel):
    enterprise_id: str
    issue_type: str
    description: str = Field(min_length=3)
    contact_mobile: str = Field(pattern=r"^1[3-9]\d{9}$")
    callback_time: str | None = None


class ServiceTicketUpdateIn(BaseModel):
    status: str | None = None
    log_message: str | None = None


class ServiceTicketOut(BaseModel):
    id: str
    enterprise_id: str
    issue_type: str
    description: str
    contact_mobile: str
    callback_time: str | None
    status: str
    logs: list[dict]

    model_config = ConfigDict(from_attributes=True)


class AuthSMSIn(BaseModel):
    mobile: str = Field(pattern=r"^1[3-9]\d{9}$")


class AuthSMSLoginIn(BaseModel):
    mobile: str = Field(pattern=r"^1[3-9]\d{9}$")
    code: str = Field(min_length=4, max_length=8)


class AuthPasswordLoginIn(BaseModel):
    username: str = Field(min_length=3, max_length=60)
    password: str = Field(min_length=4, max_length=60)
