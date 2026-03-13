from datetime import UTC, datetime
from html import escape

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import EnterpriseProfile, Policy, PolicyKnowledgeChunk, PolicyKnowledgeDocument, ServiceTicket
from app.schemas import (
    APIResponse,
    AuthPasswordLoginIn,
    AuthSMSIn,
    AuthSMSLoginIn,
    CreateMatchTaskIn,
    EnterpriseProfileIn,
    KnowledgeDocumentOut,
    KnowledgeImportIn,
    KnowledgeSearchIn,
    PolicyOut,
    QAHandoffTicketIn,
    QAIn,
    ServiceTicketIn,
    ServiceTicketOut,
    ServiceTicketUpdateIn,
)
from app.services.auth import (
    login_with_code,
    login_with_password,
    send_code,
    verify_authorization_header,
)
from app.services.policy_kb import ingest_policy_source, search_knowledge_chunks
from app.services.matching import get_task_result, run_match_task
from app.services.qa import answer_question, build_handoff_ticket_payload
from app.services.policy_structurer import build_policy_outline, sync_policies_from_knowledge_base

router = APIRouter(prefix="/api/v1", tags=["api"])
ALLOWED_TICKET_TRANSITIONS = {
    "pending": {"processing"},
    "processing": {"resolved"},
    "resolved": {"closed"},
    "closed": set(),
}


def _infer_support_type(policy: Policy) -> str:
    title = policy.title
    if "认定" in title or "培育体系" in title:
        return "资质认定"
    if "评价入库" in title:
        return "资质入库"
    if "资金" in title or "基金" in title or "补贴" in title:
        return "财政补贴"
    return "政策支持"


def _require_login(authorization: str | None = Header(default=None)) -> dict:
    session_data = verify_authorization_header(authorization)
    if not session_data:
        raise HTTPException(status_code=401, detail="login required")
    return session_data


@router.get("/healthz", response_model=APIResponse)
def healthz() -> APIResponse:
    return APIResponse(data={"status": "ok", "ts": datetime.now(UTC).isoformat()})


@router.get("/auth/me", response_model=APIResponse)
def auth_me(session_data: dict = Depends(_require_login)) -> APIResponse:
    return APIResponse(data={"subject": session_data["subject"], "login_type": session_data["login_type"]})


@router.post("/auth/password/login", response_model=APIResponse)
def password_login(payload: AuthPasswordLoginIn) -> APIResponse:
    try:
        data = login_with_password(payload.username, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return APIResponse(data=data)


@router.post("/auth/sms/send", response_model=APIResponse)
def send_sms_code(payload: AuthSMSIn) -> APIResponse:
    # MVP 阶段仅提供 mock 接口，真实短信通道后续接入
    return APIResponse(data=send_code(payload.mobile))


@router.post("/auth/sms/login", response_model=APIResponse)
def login_with_sms(payload: AuthSMSLoginIn) -> APIResponse:
    try:
        data = login_with_code(payload.mobile, payload.code)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return APIResponse(data=data)


@router.post("/enterprise-profiles", response_model=APIResponse)
def upsert_enterprise_profile(
    payload: EnterpriseProfileIn,
    _session_data: dict = Depends(_require_login),
    db: Session = Depends(get_session),
) -> APIResponse:
    profile = db.scalars(select(EnterpriseProfile).where(EnterpriseProfile.uscc == payload.uscc)).first()
    if profile:
        for key, value in payload.model_dump().items():
            setattr(profile, key, value)
    else:
        profile = EnterpriseProfile(**payload.model_dump())
        db.add(profile)

    db.commit()
    db.refresh(profile)
    return APIResponse(data={"enterprise_id": profile.id})


@router.get("/enterprise-profiles/{enterprise_id}", response_model=APIResponse)
def get_enterprise_profile(
    enterprise_id: str,
    _session_data: dict = Depends(_require_login),
    db: Session = Depends(get_session),
) -> APIResponse:
    profile = db.get(EnterpriseProfile, enterprise_id)
    if not profile:
        raise HTTPException(status_code=404, detail="enterprise not found")
    return APIResponse(data={
        "id": profile.id,
        "enterprise_name": profile.enterprise_name,
        "uscc": profile.uscc,
        "region_code": profile.region_code,
        "industry_code": profile.industry_code,
        "contact_name": profile.contact_name,
        "contact_mobile": profile.contact_mobile,
        "employee_scale": profile.employee_scale,
        "revenue_range": profile.revenue_range,
        "rd_ratio": profile.rd_ratio,
        "qualification_tags": profile.qualification_tags,
        "ip_count": profile.ip_count,
    })


@router.post("/policy-matches", response_model=APIResponse)
def create_match_task(
    payload: CreateMatchTaskIn,
    _session_data: dict = Depends(_require_login),
    db: Session = Depends(get_session),
) -> APIResponse:
    try:
        task = run_match_task(db, payload.enterprise_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return APIResponse(data={"task_id": task.id, "status": task.status})


@router.get("/policy-matches/{task_id}", response_model=APIResponse)
def query_match_result(
    task_id: str,
    view: str = Query(default="full", pattern="^(summary|full)$"),
    _session_data: dict = Depends(_require_login),
    db: Session = Depends(get_session),
) -> APIResponse:
    result = get_task_result(db, task_id, view=view)
    if not result:
        raise HTTPException(status_code=404, detail="task not found")
    return APIResponse(data=result)


@router.get("/policies", response_model=APIResponse)
def list_policies(
    page: int = 1,
    page_size: int = 20,
    _session_data: dict = Depends(_require_login),
    db: Session = Depends(get_session),
) -> APIResponse:
    offset = max(page - 1, 0) * page_size
    rows = db.scalars(select(Policy).offset(offset).limit(page_size)).all()
    return APIResponse(data=[PolicyOut.model_validate(r).model_dump() for r in rows])


@router.get("/policies/{policy_id}", response_model=APIResponse)
def get_policy(
    policy_id: str,
    _session_data: dict = Depends(_require_login),
    db: Session = Depends(get_session),
) -> APIResponse:
    policy = db.get(Policy, policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="policy not found")
    data = PolicyOut.model_validate(policy).model_dump()
    data["support_type"] = _infer_support_type(policy)
    data["updated_at"] = policy.updated_at.isoformat() if policy.updated_at else None
    data["outline_sections"] = build_policy_outline(policy, db)
    return APIResponse(data=data)


@router.post("/knowledge-base/import", response_model=APIResponse)
def import_knowledge_document(
    payload: KnowledgeImportIn,
    _session_data: dict = Depends(_require_login),
    db: Session = Depends(get_session),
) -> APIResponse:
    try:
        document = ingest_policy_source(
            db,
            source_type=payload.source_type,
            source_uri=payload.source_uri or "",
            title=payload.title,
            policy_id=payload.policy_id,
            raw_text=payload.raw_text,
        )
        sync_policies_from_knowledge_base(db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"knowledge import failed: {exc}") from exc

    chunk_count = db.scalar(
        select(func.count()).select_from(PolicyKnowledgeChunk).where(PolicyKnowledgeChunk.document_id == document.id)
    )
    data = KnowledgeDocumentOut.model_validate(document, from_attributes=True).model_dump()
    data["chunk_count"] = chunk_count or 0
    return APIResponse(data=data)


@router.get("/knowledge-base/documents", response_model=APIResponse)
def list_knowledge_documents(
    page: int = 1,
    page_size: int = 20,
    _session_data: dict = Depends(_require_login),
    db: Session = Depends(get_session),
) -> APIResponse:
    offset = max(page - 1, 0) * page_size
    rows = db.scalars(
        select(PolicyKnowledgeDocument)
        .order_by(PolicyKnowledgeDocument.updated_at.desc())
        .offset(offset)
        .limit(page_size)
    ).all()
    return APIResponse(data=[KnowledgeDocumentOut.model_validate(r, from_attributes=True).model_dump() for r in rows])


@router.get("/knowledge-base/documents/{document_id}", response_model=APIResponse)
def get_knowledge_document(
    document_id: str,
    _session_data: dict = Depends(_require_login),
    db: Session = Depends(get_session),
) -> APIResponse:
    row = db.get(PolicyKnowledgeDocument, document_id)
    if not row:
        raise HTTPException(status_code=404, detail="document not found")
    return APIResponse(
        data={
            "id": row.id,
            "title": row.title,
            "source_type": row.source_type,
            "source_uri": row.source_uri,
            "cleaned_text": row.cleaned_text,
        }
    )


@router.get("/knowledge-base/documents/{document_id}/preview", response_class=HTMLResponse)
def preview_knowledge_document(
    document_id: str,
    db: Session = Depends(get_session),
) -> HTMLResponse:
    row = db.get(PolicyKnowledgeDocument, document_id)
    if not row:
        raise HTTPException(status_code=404, detail="document not found")
    html = (
        "<!doctype html><html lang='zh-CN'><head><meta charset='UTF-8'>"
        f"<title>{escape(row.title)}</title>"
        "<style>body{font-family:PingFang SC,Arial,sans-serif;padding:24px;line-height:1.7;max-width:1100px;margin:0 auto;color:#132033}"
        "pre{white-space:pre-wrap;word-break:break-word;background:#f7fafc;border:1px solid #dbe4f0;border-radius:12px;padding:16px}"
        "h1{font-size:28px} .muted{color:#526173}</style></head><body>"
        f"<h1>{escape(row.title)}</h1>"
        f"<p class='muted'>来源：{escape(row.source_uri)}</p>"
        f"<pre>{escape(row.cleaned_text)}</pre>"
        "</body></html>"
    )
    return HTMLResponse(content=html)


@router.post("/knowledge-base/search", response_model=APIResponse)
def search_knowledge_base(
    payload: KnowledgeSearchIn,
    _session_data: dict = Depends(_require_login),
    db: Session = Depends(get_session),
) -> APIResponse:
    return APIResponse(
        data=search_knowledge_chunks(
            db,
            query=payload.query,
            policy_id=payload.policy_id,
            limit=payload.limit,
        )
    )


@router.post("/qa/policy", response_model=APIResponse)
def qa_policy(
    payload: QAIn,
    _session_data: dict = Depends(_require_login),
    db: Session = Depends(get_session),
) -> APIResponse:
    answer = answer_question(
        db,
        enterprise_id=payload.enterprise_id,
        question=payload.question,
        context_policy_id=payload.context_policy_id,
    )
    return APIResponse(data=answer)


@router.post("/qa/handoff-ticket", response_model=APIResponse)
def qa_handoff_ticket(
    payload: QAHandoffTicketIn,
    _session_data: dict = Depends(_require_login),
    db: Session = Depends(get_session),
) -> APIResponse:
    try:
        ticket_payload = build_handoff_ticket_payload(
            db,
            enterprise_id=payload.enterprise_id,
            question=payload.question,
            answer=payload.answer,
            context_policy_id=payload.context_policy_id,
            handoff_reason=payload.handoff_reason,
            callback_time=payload.callback_time,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    ticket = ServiceTicket(
        enterprise_id=ticket_payload["enterprise_id"],
        issue_type=ticket_payload["issue_type"],
        description=ticket_payload["description"],
        contact_mobile=ticket_payload["contact_mobile"],
        callback_time=ticket_payload["callback_time"],
        status="pending",
        logs=[{"at": datetime.now(UTC).isoformat(), "message": "AI问答触发转人工工单"}],
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return APIResponse(
        data={
            "ticket_id": ticket.id,
            "status": ticket.status,
            "issue_type": ticket.issue_type,
            "contact_mobile": ticket.contact_mobile,
        }
    )


@router.post("/service-tickets", response_model=APIResponse)
def create_service_ticket(
    payload: ServiceTicketIn,
    _session_data: dict = Depends(_require_login),
    db: Session = Depends(get_session),
) -> APIResponse:
    profile = db.get(EnterpriseProfile, payload.enterprise_id)
    if not profile:
        raise HTTPException(status_code=404, detail="enterprise not found")

    ticket = ServiceTicket(
        enterprise_id=payload.enterprise_id,
        issue_type=payload.issue_type,
        description=payload.description,
        contact_mobile=payload.contact_mobile,
        callback_time=payload.callback_time,
        status="pending",
        logs=[{"at": datetime.now(UTC).isoformat(), "message": "工单已创建"}],
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return APIResponse(data={"ticket_id": ticket.id, "status": ticket.status})


@router.get("/service-tickets/{ticket_id}", response_model=APIResponse)
def get_service_ticket(
    ticket_id: str,
    _session_data: dict = Depends(_require_login),
    db: Session = Depends(get_session),
) -> APIResponse:
    ticket = db.get(ServiceTicket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="ticket not found")
    return APIResponse(data=ServiceTicketOut.model_validate(ticket).model_dump())


@router.patch("/service-tickets/{ticket_id}", response_model=APIResponse)
def update_service_ticket(
    ticket_id: str,
    payload: ServiceTicketUpdateIn,
    _session_data: dict = Depends(_require_login),
    db: Session = Depends(get_session),
) -> APIResponse:
    ticket = db.get(ServiceTicket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="ticket not found")

    if payload.status:
        current = ticket.status
        if payload.status not in ALLOWED_TICKET_TRANSITIONS:
            raise HTTPException(status_code=400, detail="invalid status")
        if payload.status not in ALLOWED_TICKET_TRANSITIONS[current]:
            raise HTTPException(status_code=400, detail=f"invalid transition: {current} -> {payload.status}")
        ticket.status = payload.status

    if payload.log_message:
        logs = list(ticket.logs or [])
        logs.append({"at": datetime.now(UTC).isoformat(), "message": payload.log_message})
        ticket.logs = logs

    db.commit()
    db.refresh(ticket)
    return APIResponse(data={"ticket_id": ticket.id, "status": ticket.status, "logs": ticket.logs})
