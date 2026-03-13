from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


JSONType = JSON().with_variant(JSONB, "postgresql")


class EnterpriseProfile(Base):
    __tablename__ = "enterprise_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    enterprise_name: Mapped[str] = mapped_column(String(120), nullable=False)
    uscc: Mapped[str] = mapped_column(String(18), nullable=False, unique=True, index=True)
    region_code: Mapped[str] = mapped_column(String(20), nullable=False)
    industry_code: Mapped[str] = mapped_column(String(20), nullable=False)
    contact_name: Mapped[str] = mapped_column(String(30), nullable=False)
    contact_mobile: Mapped[str] = mapped_column(String(20), nullable=False)
    employee_scale: Mapped[str | None] = mapped_column(String(20), nullable=True)
    revenue_range: Mapped[str | None] = mapped_column(String(30), nullable=True)
    rd_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    qualification_tags: Mapped[list[str]] = mapped_column(JSONType, nullable=False, default=list)
    ip_count: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Policy(Base):
    __tablename__ = "policies"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    region_code: Mapped[str] = mapped_column(String(20), nullable=False)
    level: Mapped[str] = mapped_column(String(20), nullable=False)
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    hard_conditions: Mapped[list[dict]] = mapped_column(JSONType, nullable=False, default=list)
    scoring_conditions: Mapped[list[dict]] = mapped_column(JSONType, nullable=False, default=list)
    required_materials: Mapped[list[str]] = mapped_column(JSONType, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PolicyKnowledgeDocument(Base):
    __tablename__ = "policy_knowledge_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    policy_id: Mapped[str | None] = mapped_column(ForeignKey("policies.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_uri: Mapped[str] = mapped_column(String(1000), nullable=False)
    source_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    cleaned_text: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    ingest_status: Mapped[str] = mapped_column(String(20), nullable=False, default="ready")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PolicyKnowledgeChunk(Base):
    __tablename__ = "policy_knowledge_chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id: Mapped[str] = mapped_column(ForeignKey("policy_knowledge_documents.id"), nullable=False, index=True)
    policy_id: Mapped[str | None] = mapped_column(ForeignKey("policies.id"), nullable=True, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    keywords: Mapped[list[str]] = mapped_column(JSONType, nullable=False, default=list)
    metadata_json: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PolicyIngestionLog(Base):
    __tablename__ = "policy_ingestion_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id: Mapped[str | None] = mapped_column(ForeignKey("policy_knowledge_documents.id"), nullable=True, index=True)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_uri: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MatchTask(Base):
    __tablename__ = "match_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    enterprise_id: Mapped[str] = mapped_column(ForeignKey("enterprise_profiles.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="done")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MatchResult(Base):
    __tablename__ = "match_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id: Mapped[str] = mapped_column(ForeignKey("match_tasks.id"), nullable=False, index=True)
    policy_id: Mapped[str] = mapped_column(ForeignKey("policies.id"), nullable=False)
    eligibility: Mapped[str] = mapped_column(String(20), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    reasons: Mapped[list[str]] = mapped_column(JSONType, nullable=False, default=list)
    missing_items: Mapped[list[str]] = mapped_column(JSONType, nullable=False, default=list)


class ServiceTicket(Base):
    __tablename__ = "service_tickets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    enterprise_id: Mapped[str] = mapped_column(ForeignKey("enterprise_profiles.id"), nullable=False, index=True)
    issue_type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    contact_mobile: Mapped[str] = mapped_column(String(20), nullable=False)
    callback_time: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    logs: Mapped[list[dict]] = mapped_column(JSONType, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
