import re
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EnterpriseProfile, MatchResult, MatchTask, Policy
from app.services.llm_client import generate_with_glm
from app.services.policy_kb import search_knowledge_chunks

_INSUFFICIENT_COUNTER: dict[str, int] = {}
_DIALOG_HISTORY: dict[str, list[dict]] = {}
_CONVERSATION_STATE: dict[str, dict] = {}
_MAX_HISTORY_TURNS = 6
_HIGH_RISK_KEYWORDS = ["保证通过", "100%", "是否违法", "法律责任", "合规风险", "违规", "规避监管"]
_HUMAN_HANDOFF_KEYWORDS = ["人工", "顾问", "客服", "电话联系", "尽快联系", "转人工"]
_MISSING_OR_REJECTION_KEYWORDS = ["不符合", "不能", "失败", "驳回", "怎么补", "缺什么", "缺少"]
_TITLE_STOP_WORDS = ["政策", "企业", "支持", "补贴", "培育", "研发", "项目", "资金", "专项"]
_CONTINUATION_KEYWORDS = [
    "继续",
    "展开",
    "拆解",
    "细一点",
    "详细一点",
    "再说说",
    "然后呢",
    "往下说",
    "接着说",
    "还有吗",
    "还有别的",
    "还有别的吗",
    "还有其他",
    "还有其他吗",
    "除此之外",
    "后面呢",
]
_FOCUSABLE_INTENTS = {"summary", "materials", "gap", "policy_explain", "eligibility", "discovery"}
_QUERY_STOP_WORDS = {
    "这条",
    "政策",
    "请问",
    "一下",
    "什么",
    "怎么",
    "可以",
    "是否",
    "需要",
    "补贴",
    "有没有",
    "有无",
    "当前",
    "现在",
}
_REGION_LABEL = {"SH-ALL": "全上海", "SH-PD": "浦东新区", "SH-MH": "闵行区"}
_LEVEL_LABEL = {"city": "市级", "district": "区级"}


def _split_meaningful_tokens(token: str, stop_words: set[str]) -> list[str]:
    pieces = [token]
    for stop in sorted(stop_words, key=len, reverse=True):
        next_pieces: list[str] = []
        for item in pieces:
            next_pieces.extend(re.split(re.escape(stop), item))
        pieces = next_pieces
    return [item for item in pieces if len(item) >= 2]


def _region_name(code: str | None) -> str:
    if not code:
        return "未知区域"
    return _REGION_LABEL.get(code, code)


def _level_name(level: str | None) -> str:
    if not level:
        return "未知层级"
    return _LEVEL_LABEL.get(level, level)


def _get_latest_task(session: Session, enterprise_id: str) -> MatchTask | None:
    return session.scalars(
        select(MatchTask).where(MatchTask.enterprise_id == enterprise_id).order_by(MatchTask.created_at.desc())
    ).first()


def _get_match_bundle(session: Session, enterprise_id: str) -> tuple[MatchTask | None, list[MatchResult], dict[str, MatchResult]]:
    latest_task = _get_latest_task(session, enterprise_id)
    if not latest_task:
        return None, [], {}
    rows = session.scalars(select(MatchResult).where(MatchResult.task_id == latest_task.id)).all()
    rows.sort(key=lambda item: (-item.score, item.policy_id))
    return latest_task, rows, {row.policy_id: row for row in rows}


def _extract_terms(text: str) -> list[str]:
    parts = re.findall(r"[A-Za-z0-9_-]+|[\u4e00-\u9fff]{2,}", text)
    terms: list[str] = []
    for item in parts:
        token = item.strip().lower()
        if not token or token in _QUERY_STOP_WORDS:
            continue
        if re.fullmatch(r"[\u4e00-\u9fff]{2,}", token):
            meaningful = _split_meaningful_tokens(token, _QUERY_STOP_WORDS)
            if meaningful:
                terms.extend(meaningful)
                continue
        terms.append(token)
    return list(dict.fromkeys(terms))


def _active_policies(session: Session) -> list[Policy]:
    today = date.today()
    return session.scalars(
        select(Policy).where(
            Policy.effective_from <= today,
            (Policy.effective_to.is_(None) | (Policy.effective_to >= today)),
        )
    ).all()


def _title_keywords(title: str) -> list[str]:
    text = title
    for stop in _TITLE_STOP_WORDS:
        text = text.replace(stop, " ")
    parts = re.findall(r"[\u4e00-\u9fff]{2,}", text)
    keys = [p for p in parts if len(p) >= 2]
    if title not in keys:
        keys.append(title)
    return list(dict.fromkeys(keys))


def _policy_search_text(policy: Policy) -> str:
    labels = []
    for cond in (policy.hard_conditions or []):
        labels.append(str(cond.get("label", "")))
    for cond in (policy.scoring_conditions or []):
        labels.append(str(cond.get("label", "")))
    labels.extend(policy.required_materials or [])
    return f"{policy.title} {' '.join(labels)}".lower()


def _is_followup_question(question: str) -> bool:
    q = question.strip()
    return len(q) <= 24 and any(x in q for x in ["这条", "这个", "那我", "上面", "刚才", "继续", "那条", "再说"])


def _is_continuation_prompt(question: str) -> bool:
    q = question.strip()
    return len(q) <= 20 and any(keyword in q for keyword in _CONTINUATION_KEYWORDS)


def _is_short_followup_probe(question: str) -> bool:
    q = question.strip()
    if len(q) > 12:
        return False
    probe_keywords = ["还有", "然后", "接着", "下一步", "后面", "再", "那呢"]
    return any(keyword in q for keyword in probe_keywords)


def _detect_intent(question: str, context_policy_id: str | None, history: list[dict]) -> str:
    q = question.strip()
    if any(k in q for k in _HUMAN_HANDOFF_KEYWORDS):
        return "handoff"
    if any(k in q for k in ["几条政策", "多少条政策", "总共", "汇总", "总览", "概览", "整体情况", "匹配结果", "优先看"]):
        return "summary"
    if any(k in q for k in ["缺什么", "还差", "补齐", "不满足", "不符合", "驳回", "失败原因"]):
        return "gap"
    if any(k in q for k in ["材料", "准备什么", "申报书", "台账", "附件", "清单"]):
        return "materials"
    if any(k in q for k in ["解释", "解读", "什么意思", "怎么理解", "详细说说", "展开讲讲"]):
        return "policy_explain"
    if any(k in q for k in ["能不能报", "能报吗", "符合吗", "适合吗", "能申请吗", "可以申报吗"]):
        return "eligibility"
    if any(k in q for k in ["有没有", "还有哪些", "找一下", "推荐", "搜一下", "相关政策", "算力", "文创", "人工智能"]):
        return "discovery"
    if context_policy_id or _is_followup_question(q) or history:
        return "followup"
    return "generic"


def _extract_clause_labels(policy: Policy | None) -> list[str]:
    if not policy:
        return []
    clauses: list[str] = []
    for cond in (policy.hard_conditions or []):
        label = str(cond.get("label", "")).strip()
        if label:
            clauses.append(f"硬条件：{label}")
    for cond in (policy.scoring_conditions or []):
        label = str(cond.get("label", "")).strip()
        if label:
            clauses.append(f"加分项：{label}")
    return clauses


def _get_history(enterprise_id: str) -> list[dict]:
    return _DIALOG_HISTORY.get(enterprise_id, [])


def _conversation_state(enterprise_id: str) -> dict:
    return _CONVERSATION_STATE.get(enterprise_id, {})


def _resolve_effective_intent(question: str, detected_intent: str, enterprise_id: str) -> tuple[str, bool]:
    state = _conversation_state(enterprise_id)
    focus_intent = state.get("focus_intent")
    continuation = _is_continuation_prompt(question)
    if continuation and focus_intent in _FOCUSABLE_INTENTS:
        return str(focus_intent), True
    if detected_intent == "followup" and focus_intent in _FOCUSABLE_INTENTS:
        return str(focus_intent), continuation or _is_short_followup_probe(question)
    return detected_intent, continuation


def _push_history(enterprise_id: str, question: str, answer: str, intent: str, policy_id: str | None, continuation: bool) -> None:
    history = _DIALOG_HISTORY.get(enterprise_id, [])
    history.append({"role": "user", "content": question[:180], "intent": intent})
    history.append({"role": "assistant", "content": answer[:260], "policy_id": policy_id})
    max_items = _MAX_HISTORY_TURNS * 2
    if len(history) > max_items:
        history = history[-max_items:]
    _DIALOG_HISTORY[enterprise_id] = history
    previous_round = int(_conversation_state(enterprise_id).get("detail_round", 0))
    _CONVERSATION_STATE[enterprise_id] = {
        "last_intent": intent,
        "focus_intent": intent if intent in _FOCUSABLE_INTENTS else _conversation_state(enterprise_id).get("focus_intent"),
        "current_policy_id": policy_id,
        "detail_round": previous_round + 1 if continuation else 1,
        "updated_at": date.today().isoformat(),
    }


def _enterprise_snapshot(profile: EnterpriseProfile | None) -> str:
    if not profile:
        return "暂无企业画像。"
    qualifications = "、".join(profile.qualification_tags or []) or "暂无"
    return (
        f"企业名称：{profile.enterprise_name}\n"
        f"所在区域：{_region_name(profile.region_code)}\n"
        f"行业代码：{profile.industry_code}\n"
        f"员工规模：{profile.employee_scale or '未填写'}\n"
        f"营收区间：{profile.revenue_range or '未填写'}\n"
        f"研发投入占比：{profile.rd_ratio if profile.rd_ratio is not None else '未填写'}\n"
        f"资质标签：{qualifications}\n"
        f"知识产权数量：{profile.ip_count if profile.ip_count is not None else '未填写'}"
    )


def _focus_snapshot(enterprise_id: str) -> str:
    state = _conversation_state(enterprise_id)
    if not state:
        return "暂无会话焦点。"
    return (
        f"当前焦点主题：{state.get('focus_intent') or '未定义'}\n"
        f"当前政策ID：{state.get('current_policy_id') or '无'}\n"
        f"续聊轮次：{state.get('detail_round') or 0}"
    )


def _match_summary(match_results: list[MatchResult], policy_map: dict[str, Policy]) -> str:
    if not match_results:
        return "当前还没有匹配结果。"
    eligible = [row for row in match_results if row.eligibility == "eligible"]
    potential = [row for row in match_results if row.eligibility == "potential"]
    top_lines = []
    for row in match_results[:3]:
        policy = policy_map.get(row.policy_id)
        if not policy:
            continue
        top_lines.append(
            f"- {policy.title} | {row.eligibility} | {row.score}分 | 缺口：{('；'.join(row.missing_items) or '无')}"
        )
    return (
        f"共匹配 {len(match_results)} 条政策，可申报 {len(eligible)} 条，需完善 {len(potential)} 条。\n"
        + "\n".join(top_lines)
    )


def _policy_brief(policy: Policy | None, match_result: MatchResult | None) -> str:
    if not policy:
        return "暂无当前政策上下文。"
    lines = [
        f"政策标题：{policy.title}",
        f"政策层级：{_level_name(policy.level)}",
        f"政策区域：{_region_name(policy.region_code)}",
        f"生效时间：{policy.effective_from} 至 {policy.effective_to or '长期'}",
        f"材料：{'、'.join(policy.required_materials or []) or '暂无'}",
    ]
    if match_result:
        lines.extend(
            [
                f"匹配分类：{match_result.eligibility}",
                f"匹配分数：{match_result.score}",
                f"命中原因：{'；'.join(match_result.reasons or []) or '无'}",
                f"缺口项：{'；'.join(match_result.missing_items or []) or '无'}",
            ]
        )
    clause_lines = _extract_clause_labels(policy)[:5]
    if clause_lines:
        lines.append("条款：")
        lines.extend(clause_lines)
    return "\n".join(lines)


def _search_knowledge_context(
    session: Session,
    *,
    query: str,
    policy: Policy | None,
    profile: EnterpriseProfile | None,
    intent: str,
    limit: int = 5,
) -> list[dict]:
    queries = [query]
    if policy:
        queries.append(policy.title)
    if profile and intent in {"summary", "generic"}:
        queries.append(f"{_region_name(profile.region_code)} {profile.industry_code} 政策")

    merged: dict[str, dict] = {}
    for current_query in queries:
        hits = search_knowledge_chunks(session, query=current_query, policy_id=policy.id if policy else None, limit=limit)
        for hit in hits:
            existing = merged.get(hit["chunk_id"])
            if not existing or hit["score"] > existing["score"]:
                merged[hit["chunk_id"]] = hit

    results = sorted(merged.values(), key=lambda item: (-item["score"], item["chunk_index"]))
    return results[:limit]


def _select_policy_for_question(
    session: Session,
    *,
    enterprise_id: str,
    question: str,
    context_policy_id: str | None,
    intent: str,
    match_results: list[MatchResult],
    match_map: dict[str, MatchResult],
) -> tuple[Policy | None, MatchResult | None, bool]:
    active_policies = _active_policies(session)
    policy_by_id = {policy.id: policy for policy in active_policies}
    context_policy = policy_by_id.get(context_policy_id) if context_policy_id else None

    if intent == "summary":
        if context_policy:
            return context_policy, match_map.get(context_policy.id), False
        if match_results:
            top_match = match_results[0]
            return policy_by_id.get(top_match.policy_id), top_match, False
        return None, None, False

    terms = _extract_terms(question)
    candidates = active_policies or [session.get(Policy, context_policy_id)] if context_policy_id else active_policies
    scored: list[tuple[int, Policy]] = []
    for policy in candidates:
        if not policy:
            continue
        score = 0
        text = _policy_search_text(policy)
        title = policy.title.lower()
        if context_policy_id and policy.id == context_policy_id and intent not in {"discovery", "generic"}:
            score += 16
        if policy.id in match_map and intent not in {"discovery", "generic"}:
            score += 14 if match_map[policy.id].eligibility == "eligible" else 8
        if intent in {"gap", "materials", "policy_explain", "eligibility", "followup"} and context_policy_id == policy.id:
            score += 18
        for key in _title_keywords(policy.title):
            if key and key in question:
                score += 28
        for term in terms:
            if term in title:
                score += 22
            elif term in text:
                score += 6
        scored.append((score, policy))

    scored.sort(key=lambda item: item[0], reverse=True)
    if not scored:
        return None, None, False

    best_score, best_policy = scored[0]
    if intent == "discovery" and best_score < 22:
        return None, None, False
    if context_policy and intent in {"gap", "materials", "policy_explain", "eligibility", "followup"} and best_score < 28:
        return context_policy, match_map.get(context_policy.id), False

    if best_score <= 0:
        if match_results and intent not in {"discovery", "generic"}:
            top_match = match_results[0]
            return policy_by_id.get(top_match.policy_id), top_match, False
        return None, None, False

    selected_match = match_map.get(best_policy.id)
    switched = bool(context_policy_id and best_policy.id != context_policy_id and best_score >= 28)
    return best_policy, selected_match, switched


def _build_evidence_snippets(
    policy: Policy | None,
    match_result: MatchResult | None,
    match_results: list[MatchResult],
    policy_map: dict[str, Policy],
    knowledge_hits: list[dict],
    intent: str,
) -> list[str]:
    snippets: list[str] = []
    if intent == "summary" and match_results:
        eligible = len([row for row in match_results if row.eligibility == "eligible"])
        snippets.append(f"匹配汇总：共 {len(match_results)} 条，可申报 {eligible} 条。")
        for row in match_results[:2]:
            current = policy_map.get(row.policy_id)
            if current:
                snippets.append(f"优先政策：{current.title}（{row.score}分）")
    if policy:
        snippets.append(f"当前政策：{policy.title}（{_level_name(policy.level)}/{_region_name(policy.region_code)}）")
    if match_result:
        if match_result.reasons:
            snippets.append(f"命中依据：{match_result.reasons[0]}")
        if match_result.missing_items:
            snippets.append(f"关键缺口：{match_result.missing_items[0]}")
    if policy and len(snippets) < 4:
        for clause in _extract_clause_labels(policy):
            snippets.append(f"条款依据：{clause}")
            if len(snippets) >= 4:
                break
    for hit in knowledge_hits[:2]:
        snippets.append(f"知识库：{hit['title']} - {hit['content'][:80]}")
    return snippets[:5]


def _build_citations(
    policy: Policy | None,
    match_results: list[MatchResult],
    policy_map: dict[str, Policy],
    knowledge_hits: list[dict],
    evidence_snippets: list[str],
    intent: str,
) -> list[dict]:
    citations: list[dict] = []
    if knowledge_hits:
        for item in knowledge_hits[:3]:
            citations.append(
                {
                    "title": item["title"],
                    "url": item["source_uri"],
                    "snippet": item["content"][:180],
                }
            )
    elif intent == "summary" and match_results:
        for row in match_results[:3]:
            current = policy_map.get(row.policy_id)
            if current and current.source_url:
                citations.append(
                    {
                        "title": current.title,
                        "url": current.source_url,
                        "snippet": "；".join(row.reasons[:2]) if row.reasons else "",
                    }
                )
    elif policy:
        citations.append(
            {
                "title": policy.title,
                "url": policy.source_url,
                "snippet": evidence_snippets[0] if evidence_snippets else "",
            }
        )
    return citations[:3]


def _build_clarification_question(
    intent: str,
    profile: EnterpriseProfile | None,
    policy: Policy | None,
    knowledge_hits: list[dict],
) -> str | None:
    if intent == "summary":
        return None
    if intent in {"gap", "materials", "policy_explain", "eligibility"} and not policy:
        return "你可以直接发政策名称，或者先点一条匹配结果，我再按那条政策继续拆解。"
    if intent in {"discovery", "generic"} and not knowledge_hits:
        if profile and profile.region_code and profile.region_code != "SH-ALL":
            return f"你是想继续看{_region_name(profile.region_code)}的政策，还是切到全上海？也可以补充“补贴/认定/人才”方向。"
        return "你更想看全上海还是先锁定某个区？也可以补充政策方向，比如补贴、认定、人才或融资。"
    if intent in {"discovery", "generic"} and knowledge_hits:
        return "如果你告诉我更关注哪个区、哪类支持，或者是否已有高新/专精特新资质，我可以继续缩到更适合你的范围。"
    return None


def _material_detail_lines(policy: Policy) -> list[str]:
    details: list[str] = []
    for item in policy.required_materials[:4]:
        if "证书" in item or "资质" in item or "认定" in item:
            details.append(f"{item}主要用来证明企业主体资格。")
        elif "审计" in item or "财务" in item or "报表" in item:
            details.append(f"{item}主要用于核验研发投入或经营数据。")
        elif "台账" in item or "立项" in item or "项目" in item:
            details.append(f"{item}用来支撑项目过程和真实性说明。")
        else:
            details.append(f"{item}建议按当年申报通知准备原件和盖章件。")
    if len(details) < 3:
        details.append("另外通常还要配合营业执照、联系人信息和基础财务资料一起提交。")
    return details[:3]


def _continuation_answer(
    *,
    intent: str,
    policy: Policy | None,
    match_result: MatchResult | None,
    match_results: list[MatchResult],
    policy_map: dict[str, Policy],
    detail_round: int,
) -> str | None:
    if intent == "summary" and match_results:
        top_rows = match_results[:2]
        lines = []
        for row in top_rows:
            current = policy_map.get(row.policy_id)
            if not current:
                continue
            reason = (row.reasons or ["匹配分较高"])[0]
            lines.append(f"{current.title}可以优先看，主要是因为{reason}。")
        if lines:
            return "先从前两条说起：" + " ".join(lines[:2])
    if not policy:
        return None
    if intent == "materials":
        if detail_round >= 2:
            supplements = ["营业执照", "联系人与申报主体信息", "基础财务资料或佐证附件"]
            if match_result and match_result.eligibility == "eligible":
                supplements.insert(2, "按当年通知填写的申报表或承诺书")
            supplement_text = "、".join(supplements[:4])
            return (
                f"还有。除了前面两项核心件，通常还要补这组基础材料：{supplement_text}。"
                "真正提交前再对照当年申报通知核一遍附件模板和盖章要求，就不会漏。"
            )
        return "这条先拆成两类材料来看：" + " ".join(_material_detail_lines(policy))
    if intent == "gap" and match_result and match_result.missing_items:
        main_gap = match_result.missing_items[0]
        return f"你现在先盯住这一项：{main_gap}。补齐后再回头看其他条件，效率会更高。"
    if intent == "policy_explain":
        return f"这条政策你可以先理解成一件事：它核心看的是{policy.title}对应的主体资格和关键经营指标，不是填个表就能直接报。"
    if intent == "eligibility" and match_result:
        if match_result.eligibility == "eligible":
            return "就你当前画像看，这条是可以往申报方向推进的，重点是把材料准备完整。"
        return f"这条暂时还差一步，最关键的是先补齐{(match_result.missing_items or ['核心条件'])[0]}。"
    return None


def _build_policy_messages(
    *,
    question: str,
    intent: str,
    profile: EnterpriseProfile | None,
    policy: Policy | None,
    match_result: MatchResult | None,
    match_results: list[MatchResult],
    policy_map: dict[str, Policy],
    dialog_history: list[dict],
    knowledge_hits: list[dict],
    clarification_question: str | None,
    continuation: bool,
) -> list[dict]:
    system = (
        "你是惠企通的企业政策顾问助手。"
        "你是主回答者，不是补充模块。只要上下文里有信息，就由你直接组织自然回复。"
        "回答要像一位专业顾问在聊天，语气自然，不要机械，不要像接口返回。"
        "不要总用“我先给你一个明确结论”“如果你愿意”这类固定套话。"
        "优先直接回答，再自然补一句建议或追问；不需要罗列参考依据、字段名或结构化标签。"
        "如果是总览类问题，优先总结企业匹配结果，不要强行围绕单条政策。"
        "如果用户是在继续追问，就沿着上一轮主题往下讲，不要换成别的角度重新回答。"
        "如果证据不足，不要空泛拒答，要明确指出还缺哪一类信息，并只追问一个最关键的问题。"
        "禁止承诺通过率、禁止法律结论、禁止编造政策。"
        "总字数控制在180字内。"
    )

    history_lines = []
    for item in dialog_history[-4:]:
        role = "用户" if item.get("role") == "user" else "助手"
        history_lines.append(f"{role}: {item.get('content', '')}")
    history_text = "\n".join(history_lines) if history_lines else "无历史对话"

    knowledge_lines = [
        f"[{idx + 1}] {item['title']} | {item['content'][:120]}"
        for idx, item in enumerate(knowledge_hits[:2])
    ]

    context_text = (
        f"问题意图：{intent}\n\n"
        f"企业画像：\n{_enterprise_snapshot(profile)}\n\n"
        f"会话焦点：\n{_focus_snapshot(profile.id if profile else '')}\n\n"
        f"匹配结果摘要：\n{_match_summary(match_results, policy_map)}\n\n"
        f"当前政策：\n{_policy_brief(policy, match_result)}\n\n"
        f"知识库证据：\n{chr(10).join(knowledge_lines) if knowledge_lines else '无'}\n\n"
        f"最近对话：\n{history_text}\n\n"
        f"是否续聊：{'是' if continuation else '否'}\n"
        f"如需追问，可优先问：{clarification_question or '无'}"
    )
    user = f"用户当前问题：{question}\n请仅基于给定上下文回复。"
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": context_text},
        {"role": "user", "content": user},
    ]


def _should_try_llm(risk_flags: list[str], intent: str, clarification_question: str | None) -> bool:
    if "high_risk_question" in risk_flags:
        return False
    return True


def _next_actions(
    intent: str,
    match_result: MatchResult | None,
    match_results: list[MatchResult],
    recommend_handoff: bool,
) -> list[str]:
    if intent == "summary":
        actions = ["先查看前 2 条高分政策详情", "确认最优先的一条并准备材料"]
    elif not match_result:
        actions = ["补充企业区域、资质或政策主题", "补充后继续提问或重新匹配"]
    elif match_result.eligibility == "eligible":
        actions = ["准备申报材料", "核对申报窗口与官方入口", "必要时请顾问复核口径"]
    else:
        actions = ["优先补齐缺口项", "完善对应资质或经营指标", "补齐后重新匹配确认"]

    if intent == "discovery":
        actions.insert(0, "先锁定政策主题和区域范围")
    if match_results and intent == "summary":
        actions.append("我也可以继续帮你拆解为什么这几条最优先")
    if recommend_handoff:
        actions.append("点击“一键转人工”生成顾问工单")
    return actions[:4]


def _summary_answer(match_results: list[MatchResult], policy_map: dict[str, Policy]) -> str:
    if not match_results:
        return "你这边暂时还没有可用的匹配结果。先把企业信息保存并跑一次匹配，我再帮你判断优先级。"

    eligible = [row for row in match_results if row.eligibility == "eligible"]
    potential = [row for row in match_results if row.eligibility == "potential"]
    top_titles = [policy_map[row.policy_id].title for row in match_results[:2] if row.policy_id in policy_map]
    top_text = "、".join(top_titles) if top_titles else "当前高分政策"
    return (
        f"目前共匹配到 {len(match_results)} 条政策，其中可申报 {len(eligible)} 条、需完善 {len(potential)} 条。"
        f"建议先看 {top_text}。要我接着帮你把前两条拆开说，也可以。"
    )


def _discovery_answer(knowledge_hits: list[dict], clarification_question: str | None) -> str:
    if not knowledge_hits:
        return f"我暂时没在现有政策库里找到足够相关的内容。{clarification_question or '你补充一下政策方向和所在区，我继续帮你筛。'}"
    titles = "、".join(dict.fromkeys(item["title"] for item in knowledge_hits[:3]))
    return (
        f"我先查到几条比较接近的线索：{titles}。"
        f"{clarification_question or '你再说细一点，我帮你继续收窄。'}"
    )


def _fallback_answer(
    *,
    question: str,
    enterprise_id: str,
    intent: str,
    continuation: bool,
    policy: Policy | None,
    match_result: MatchResult | None,
    match_results: list[MatchResult],
    policy_map: dict[str, Policy],
    risk_flags: list[str],
    recommend_handoff: bool,
    knowledge_hits: list[dict],
    clarification_question: str | None,
) -> str:
    if "high_risk_question" in risk_flags:
        return "这个问题涉及高风险判断，我这边不适合直接给确定性承诺，最好转人工顾问复核。"
    if continuation:
        continued = _continuation_answer(
            intent=intent,
            policy=policy,
            match_result=match_result,
            match_results=match_results,
            policy_map=policy_map,
            detail_round=int(_conversation_state(enterprise_id).get("detail_round", 0)),
        )
        if continued:
            return continued
    if intent == "summary":
        return _summary_answer(match_results, policy_map)
    if intent == "discovery":
        return _discovery_answer(knowledge_hits, clarification_question)
    if clarification_question and not policy and not knowledge_hits:
        return f"现在信息还不够。{clarification_question}"
    if not policy and knowledge_hits:
        top_hit = knowledge_hits[0]
        return (
            f"我查到一条相关信息。按《{top_hit['title']}》来看，{top_hit['content'][:72]}。"
            f"{clarification_question or '你再补充一下所在区或资质情况，我就能继续往下判断。'}"
        )
    if not policy:
        return f"现在还不能可靠判断。{clarification_question or '你补充一下政策名称、所在区或资质标签，我继续查。'}"

    parts = [f"基于《{policy.title}》，可以先做个初步判断。"]
    if intent == "materials":
        parts.append(f"当前先准备这些核心材料：{'、'.join(policy.required_materials[:3]) or '请以官方通知为准'}。")
    elif match_result and match_result.missing_items and intent in {"gap", "eligibility"}:
        parts.append(f"你现在最主要的缺口是：{match_result.missing_items[0]}。")
    elif match_result and match_result.reasons:
        parts.append(f"当前命中的核心依据是：{match_result.reasons[0]}。")
    else:
        parts.append(f"它属于{_level_name(policy.level)}政策，适用区域是{_region_name(policy.region_code)}。")
    if recommend_handoff:
        parts.append("这类问题建议人工顾问再复核一次。")
    else:
        parts.append(clarification_question or "要的话，我可以继续帮你往下拆。")
    return " ".join(parts)


def _polish_answer(answer: str) -> str:
    text = re.sub(r"\s+", " ", answer).strip()
    replacements = [
        ("我先给你一个明确结论：", ""),
        ("我先给你结论：", ""),
        ("如果你愿意，", ""),
        ("如果你愿意", ""),
        ("参考依据：", ""),
        ("当前对焦：", ""),
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    text = re.sub(r"\s{2,}", " ", text).strip(" \n；;")
    return text


def _calculate_confidence(
    *,
    intent: str,
    has_policy: bool,
    has_match: bool,
    has_matches: bool,
    has_high_risk: bool,
    insufficient_context: bool,
    insufficient_count: int,
    evidence_count: int,
    clarification_needed: bool,
    answer_indicates_insufficient: bool,
) -> float:
    confidence = 0.52
    if has_policy:
        confidence += 0.16
    if has_match:
        confidence += 0.08
    if has_matches and intent == "summary":
        confidence += 0.16
    if evidence_count >= 2:
        confidence += 0.08
    elif evidence_count == 1:
        confidence += 0.03
    if has_high_risk:
        confidence -= 0.35
    if insufficient_context:
        confidence -= 0.18
    if insufficient_count >= 2:
        confidence -= 0.15
    if clarification_needed:
        confidence -= 0.12
    if answer_indicates_insufficient:
        confidence -= 0.18
    return max(0.05, min(0.96, round(confidence, 2)))


def answer_question(
    session: Session,
    enterprise_id: str,
    question: str,
    context_policy_id: str | None = None,
) -> dict:
    q = question.strip()
    profile = session.get(EnterpriseProfile, enterprise_id)
    dialog_history = _get_history(enterprise_id)
    detected_intent = _detect_intent(q, context_policy_id, dialog_history)
    intent, continuation = _resolve_effective_intent(q, detected_intent, enterprise_id)

    _, match_results, match_map = _get_match_bundle(session, enterprise_id)
    policy_ids = [row.policy_id for row in match_results]
    policy_map = {policy.id: policy for policy in session.scalars(select(Policy).where(Policy.id.in_(policy_ids))).all()} if policy_ids else {}

    policy, match_result, switched = _select_policy_for_question(
        session,
        enterprise_id=enterprise_id,
        question=q,
        context_policy_id=context_policy_id or _CONVERSATION_STATE.get(enterprise_id, {}).get("current_policy_id"),
        intent=intent,
        match_results=match_results,
        match_map=match_map,
    )
    if policy and policy.id not in policy_map:
        policy_map[policy.id] = policy

    knowledge_hits = _search_knowledge_context(
        session,
        query=q,
        policy=policy,
        profile=profile,
        intent=intent,
        limit=5,
    )
    generic_query = len(_extract_terms(q)) <= 1 or any(
        phrase in q for phrase in ["怎么申报", "怎么申请", "如何申报", "应该怎么", "怎么办", "怎么报"]
    )
    clarification_question = _build_clarification_question(intent, profile, policy, knowledge_hits)
    evidence_snippets = _build_evidence_snippets(policy, match_result, match_results, policy_map, knowledge_hits, intent)
    citations = _build_citations(policy, match_results, policy_map, knowledge_hits, evidence_snippets, intent)

    risk_flags: list[str] = []
    if any(k in q for k in _HIGH_RISK_KEYWORDS):
        risk_flags.append("high_risk_question")
    if any(k in q for k in _HUMAN_HANDOFF_KEYWORDS):
        risk_flags.append("user_requested_human")
    if switched:
        risk_flags.append("policy_reselected")
    if intent == "summary":
        risk_flags.append("summary_intent")
    if intent == "discovery":
        risk_flags.append("discovery_intent")
    if clarification_question:
        risk_flags.append("clarification_needed")
    if not policy and intent != "summary" and (not knowledge_hits or (intent in {"generic", "followup"} and generic_query)):
        risk_flags.append("insufficient_context")
        _INSUFFICIENT_COUNTER[enterprise_id] = _INSUFFICIENT_COUNTER.get(enterprise_id, 0) + 1
    else:
        _INSUFFICIENT_COUNTER[enterprise_id] = 0
    insufficient_count = _INSUFFICIENT_COUNTER.get(enterprise_id, 0)

    llm_answer = None
    if _should_try_llm(risk_flags, intent, clarification_question):
        llm_answer = generate_with_glm(
            _build_policy_messages(
                question=q,
                intent=intent,
                profile=profile,
                policy=policy,
                match_result=match_result,
                match_results=match_results,
                policy_map=policy_map,
                dialog_history=dialog_history,
                knowledge_hits=knowledge_hits,
                clarification_question=clarification_question,
                continuation=continuation,
            ),
            timeout_seconds=10,
            temperature=0.45,
            max_tokens=220,
        )

    answer = llm_answer or _fallback_answer(
        question=q,
        enterprise_id=enterprise_id,
        intent=intent,
        continuation=continuation,
        policy=policy,
        match_result=match_result,
        match_results=match_results,
        policy_map=policy_map,
        risk_flags=risk_flags,
        recommend_handoff=False,
        knowledge_hits=knowledge_hits,
        clarification_question=clarification_question,
    )
    answer = _polish_answer(answer)
    answer_indicates_insufficient = "信息不足" in answer or "证据不足" in answer
    if answer_indicates_insufficient and "insufficient_answer" not in risk_flags:
        risk_flags.append("insufficient_answer")

    confidence = _calculate_confidence(
        intent=intent,
        has_policy=bool(policy),
        has_match=bool(match_result),
        has_matches=bool(match_results),
        has_high_risk="high_risk_question" in risk_flags,
        insufficient_context="insufficient_context" in risk_flags,
        insufficient_count=insufficient_count,
        evidence_count=len(evidence_snippets),
        clarification_needed=bool(clarification_question),
        answer_indicates_insufficient=answer_indicates_insufficient,
    )

    handoff_reason = None
    if "high_risk_question" in risk_flags:
        handoff_reason = "问题涉及法律/合规或结果承诺类高风险判断"
    elif "user_requested_human" in risk_flags:
        handoff_reason = "用户明确要求人工顾问介入"
    elif insufficient_count >= 2:
        handoff_reason = "连续两次证据不足，建议转人工处理"
    elif confidence < 0.58:
        handoff_reason = "当前回答置信度偏低，建议人工复核"
    elif match_result and match_result.eligibility == "potential" and any(k in q for k in _MISSING_OR_REJECTION_KEYWORDS):
        handoff_reason = "涉及缺口补齐细节，建议人工逐项确认"

    recommend_handoff = bool(handoff_reason)
    next_actions = _next_actions(intent, match_result, match_results, recommend_handoff)
    _push_history(enterprise_id, q, answer, intent, policy.id if policy else None, continuation)

    return {
        "answer": answer,
        "citations": citations,
        "recommend_handoff": recommend_handoff,
        "confidence": confidence,
        "risk_flags": risk_flags,
        "handoff_reason": handoff_reason,
        "next_actions": next_actions,
        "evidence_snippets": evidence_snippets,
        "intent": intent,
        "selected_policy_id": policy.id if policy else None,
        "selected_policy_title": policy.title if policy else None,
        "clarification_needed": bool(clarification_question),
    }


def build_handoff_ticket_payload(
    session: Session,
    enterprise_id: str,
    question: str,
    answer: str,
    context_policy_id: str | None = None,
    handoff_reason: str | None = None,
    callback_time: str | None = None,
) -> dict:
    profile = session.get(EnterpriseProfile, enterprise_id)
    if not profile:
        raise ValueError("enterprise not found")

    policy_title = ""
    if context_policy_id:
        policy = session.get(Policy, context_policy_id)
        if policy:
            policy_title = policy.title

    policy_line = f"\n关联政策：{policy_title}" if policy_title else ""
    reason_line = f"\n转人工原因：{handoff_reason}" if handoff_reason else ""
    description = (
        f"【AI问答转人工】\n"
        f"用户问题：{question}\n"
        f"AI回复：{answer}"
        f"{policy_line}"
        f"{reason_line}\n"
        "请顾问基于企业画像进行人工复核。"
    )

    return {
        "enterprise_id": enterprise_id,
        "issue_type": "qa_handoff",
        "description": description,
        "contact_mobile": profile.contact_mobile,
        "callback_time": callback_time,
    }
