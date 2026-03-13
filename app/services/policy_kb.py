from __future__ import annotations

import hashlib
import re
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from pypdf import PdfReader
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import Policy, PolicyIngestionLog, PolicyKnowledgeChunk, PolicyKnowledgeDocument

_STOP_WORDS = {
    "政策",
    "企业",
    "项目",
    "支持",
    "补贴",
    "申报",
    "要求",
    "材料",
    "需要",
    "可以",
    "什么",
    "怎么",
    "以及",
    "有没有",
    "有无",
}
_FOOTER_LINE_PATTERNS = [
    re.compile(r"^陈灵林\s+\d{11}$"),
    re.compile(r"^第\s*\d+\s*页\s*共\s*\d+\s*页$"),
    re.compile(r"^第\s*\d+\s*页$"),
]


def _split_meaningful_tokens(token: str) -> list[str]:
    pieces = [token]
    for stop in sorted(_STOP_WORDS, key=len, reverse=True):
        next_pieces: list[str] = []
        for item in pieces:
            next_pieces.extend(re.split(re.escape(stop), item))
        pieces = next_pieces
    return [item for item in pieces if len(item) >= 2]


def _clean_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = text.replace("\r", "\n")
    filtered_lines: list[str] = []
    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if any(pattern.match(line) for pattern in _FOOTER_LINE_PATTERNS):
            continue
        filtered_lines.append(raw_line)
    text = "\n".join(filtered_lines)
    text = re.sub(r"陈灵林\s+\d{11}", "", text)
    text = re.sub(r"第\s*\d+\s*页\s*共\s*\d+\s*页", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_terms(text: str) -> list[str]:
    parts = re.findall(r"[A-Za-z0-9_-]+|[\u4e00-\u9fff]{2,}", text.lower())
    terms: list[str] = []
    for part in parts:
        token = part.strip()
        if not token or token in _STOP_WORDS:
            continue
        if re.fullmatch(r"[\u4e00-\u9fff]{4,}", token):
            meaningful = _split_meaningful_tokens(token)
            if meaningful:
                terms.extend(meaningful)
                continue
        terms.append(token)
    return list(dict.fromkeys(terms))


def _chunk_text(text: str, max_chars: int = 500, overlap: int = 80) -> list[str]:
    normalized = _clean_text(text)
    if not normalized:
        return []

    paragraphs = [p.strip() for p in normalized.split("\n") if p.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        next_piece = paragraph if not current else f"{current}\n{paragraph}"
        if len(next_piece) <= max_chars:
            current = next_piece
            continue
        if current:
            chunks.append(current)
            current = current[-overlap:] + "\n" + paragraph if overlap > 0 else paragraph
            if len(current) > max_chars:
                chunks.append(current[:max_chars])
                current = current[max_chars - overlap :] if len(current) > max_chars else ""
        else:
            start = 0
            while start < len(paragraph):
                end = start + max_chars
                chunks.append(paragraph[start:end])
                if end >= len(paragraph):
                    break
                start = max(end - overlap, start + 1)
            current = ""
    if current:
        chunks.append(current)
    return [c.strip() for c in chunks if c.strip()]


def _content_hash(text: str, source_uri: str) -> str:
    return hashlib.sha256(f"{source_uri}\n{text}".encode("utf-8")).hexdigest()


def _text_from_pdf_bytes(content: bytes) -> str:
    with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
        tmp.write(content)
        tmp.flush()
        reader = PdfReader(tmp.name)
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
    return "\n\n".join(p for p in pages if p)


def _extract_text_from_pdf_file(file_path: str) -> str:
    reader = PdfReader(file_path)
    pages = [(page.extract_text() or "").strip() for page in reader.pages]
    return "\n\n".join(p for p in pages if p)


def _extract_text_from_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    body = soup.get_text("\n", strip=True)
    return _clean_text(f"{title}\n{body}")


def _guess_source_domain(source_uri: str) -> str | None:
    parsed = urlparse(source_uri)
    return parsed.netloc or None


def _fetch_url_content(source_url: str) -> tuple[str, str]:
    with httpx.Client(follow_redirects=True, timeout=12.0) as client:
        resp = client.get(source_url)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "").lower()
        if "pdf" in content_type or source_url.lower().endswith(".pdf"):
            return "pdf", _extract_text_from_pdf_bytes(resp.content)
        return "html", _extract_text_from_html(resp.text)


def _build_policy_structured_text(policy: Policy) -> str:
    hard_lines = [f"- {item.get('label', '')}" for item in (policy.hard_conditions or []) if item.get("label")]
    score_lines = [f"- {item.get('label', '')}" for item in (policy.scoring_conditions or []) if item.get("label")]
    material_lines = [f"- {item}" for item in (policy.required_materials or [])]
    return _clean_text(
        "\n".join(
            [
                f"政策标题：{policy.title}",
                f"区域：{policy.region_code}",
                f"层级：{policy.level}",
                f"原文链接：{policy.source_url}",
                f"生效时间：{policy.effective_from} 至 {policy.effective_to or '长期'}",
                "硬性条件：",
                *hard_lines,
                "加分条件：",
                *score_lines,
                "所需材料：",
                *material_lines,
            ]
        )
    )


def _save_document(
    session: Session,
    *,
    title: str,
    source_type: str,
    source_uri: str,
    raw_text: str,
    cleaned_text: str,
    policy_id: str | None = None,
    metadata_json: dict | None = None,
) -> PolicyKnowledgeDocument:
    content_hash = _content_hash(cleaned_text, source_uri)
    existing = session.scalars(
        select(PolicyKnowledgeDocument)
        .where(
            PolicyKnowledgeDocument.source_type == source_type,
            PolicyKnowledgeDocument.source_uri == source_uri,
        )
        .order_by(PolicyKnowledgeDocument.updated_at.desc())
    ).first()
    if not existing:
        existing = session.scalars(
            select(PolicyKnowledgeDocument).where(PolicyKnowledgeDocument.content_hash == content_hash)
        ).first()
    if existing:
        duplicate_ids = session.scalars(
            select(PolicyKnowledgeDocument.id).where(
                PolicyKnowledgeDocument.source_type == source_type,
                PolicyKnowledgeDocument.source_uri == source_uri,
                PolicyKnowledgeDocument.id != existing.id,
            )
        ).all()
        existing.title = title
        existing.policy_id = policy_id
        existing.content_hash = content_hash
        existing.raw_text = raw_text
        existing.cleaned_text = cleaned_text
        existing.metadata_json = metadata_json or {}
        existing.ingest_status = "ready"
        existing.source_type = source_type
        existing.source_uri = source_uri
        existing.source_domain = _guess_source_domain(source_uri)
        session.execute(delete(PolicyKnowledgeChunk).where(PolicyKnowledgeChunk.document_id == existing.id))
        if duplicate_ids:
            session.execute(delete(PolicyKnowledgeChunk).where(PolicyKnowledgeChunk.document_id.in_(duplicate_ids)))
            session.execute(delete(PolicyIngestionLog).where(PolicyIngestionLog.document_id.in_(duplicate_ids)))
            session.execute(delete(PolicyKnowledgeDocument).where(PolicyKnowledgeDocument.id.in_(duplicate_ids)))
        document = existing
    else:
        document = PolicyKnowledgeDocument(
            title=title,
            source_type=source_type,
            source_uri=source_uri,
            source_domain=_guess_source_domain(source_uri),
            content_hash=content_hash,
            raw_text=raw_text,
            cleaned_text=cleaned_text,
            metadata_json=metadata_json or {},
            ingest_status="ready",
            policy_id=policy_id,
        )
        session.add(document)
        session.flush()

    chunks = _chunk_text(cleaned_text)
    session.add_all(
        [
            PolicyKnowledgeChunk(
                document_id=document.id,
                policy_id=policy_id,
                chunk_index=index,
                content=chunk,
                char_count=len(chunk),
                keywords=_extract_terms(chunk)[:20],
                metadata_json={"title": title, "source_uri": source_uri},
            )
            for index, chunk in enumerate(chunks)
        ]
    )
    session.add(
        PolicyIngestionLog(
            document_id=document.id,
            source_type=source_type,
            source_uri=source_uri,
            status="success",
            message=f"chunks={len(chunks)}",
        )
    )
    session.commit()
    session.refresh(document)
    return document


def ingest_policy_source(
    session: Session,
    *,
    source_type: str,
    source_uri: str,
    title: str | None = None,
    policy_id: str | None = None,
    raw_text: str | None = None,
    metadata_json: dict | None = None,
) -> PolicyKnowledgeDocument:
    if source_type == "raw_text":
        if not raw_text:
            raise ValueError("raw_text is required")
        extracted_text = raw_text
    elif source_type == "file":
        path = Path(source_uri)
        if not path.exists():
            raise ValueError("file not found")
        if path.suffix.lower() == ".pdf":
            extracted_text = _extract_text_from_pdf_file(str(path))
        else:
            extracted_text = path.read_text(encoding="utf-8")
    elif source_type == "url":
        _, extracted_text = _fetch_url_content(source_uri)
    elif source_type == "policy_structured":
        policy = session.get(Policy, policy_id) if policy_id else None
        if not policy:
            raise ValueError("policy not found")
        extracted_text = _build_policy_structured_text(policy)
        title = title or policy.title
        source_uri = source_uri or policy.source_url
    else:
        raise ValueError("unsupported source type")

    cleaned_text = _clean_text(extracted_text)
    if not cleaned_text:
        raise ValueError("empty content")

    return _save_document(
        session,
        title=title or Path(source_uri).stem or "未命名政策文档",
        source_type=source_type,
        source_uri=source_uri,
        raw_text=extracted_text,
        cleaned_text=cleaned_text,
        policy_id=policy_id,
        metadata_json=metadata_json or {},
    )


def sync_policy_knowledge_base(session: Session) -> int:
    policies = session.scalars(select(Policy)).all()
    synced = 0
    for policy in policies:
        ingest_policy_source(
            session,
            source_type="policy_structured",
            source_uri=policy.source_url,
            title=policy.title,
            policy_id=policy.id,
            metadata_json={"sync_mode": "policy_structured"},
        )
        synced += 1
    return synced


def search_knowledge_chunks(
    session: Session,
    *,
    query: str,
    limit: int = 5,
    policy_id: str | None = None,
) -> list[dict]:
    terms = _extract_terms(query)
    if not terms:
        return []

    stmt = select(PolicyKnowledgeChunk, PolicyKnowledgeDocument).join(
        PolicyKnowledgeDocument, PolicyKnowledgeDocument.id == PolicyKnowledgeChunk.document_id
    )
    if policy_id:
        stmt = stmt.where(PolicyKnowledgeChunk.policy_id == policy_id)
    rows = session.execute(stmt).all()

    scored: list[dict] = []
    for chunk, document in rows:
        text = chunk.content.lower()
        score = 0
        for term in terms:
            if term in text:
                score += 8
            if term in document.title.lower():
                score += 12
        if policy_id and chunk.policy_id == policy_id:
            score += 6
        if score <= 0:
            continue
        scored.append(
            {
                "document_id": document.id,
                "policy_id": chunk.policy_id,
                "title": document.title,
                "source_uri": document.source_uri,
                "source_type": document.source_type,
                "chunk_id": chunk.id,
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "score": score,
            }
        )

    scored.sort(key=lambda item: (-item["score"], item["chunk_index"]))
    return scored[:limit]
