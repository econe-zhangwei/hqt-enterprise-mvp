from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import EnterpriseProfile, MatchResult, MatchTask, Policy


def _compare(actual, op: str, expected, field: str | None = None) -> bool:
    if actual is None:
        return False
    if field == "region_code" and actual == "SH-ALL":
        # “全上海”作为广域检索模式，不按单一区做硬过滤。
        return True
    if op == "eq":
        return actual == expected
    if op == "in":
        return actual in expected
    if op == ">=":
        return float(actual) >= float(expected)
    if op == "<=":
        return float(actual) <= float(expected)
    if op == "contains":
        if isinstance(actual, list):
            return expected in actual
        if isinstance(actual, str):
            return str(expected) in actual
        return False
    if op == "prefix_in":
        actual_text = str(actual)
        return any(actual_text.startswith(str(item)) for item in expected)
    return False


def _evaluate_policy(profile: EnterpriseProfile, policy: Policy) -> dict:
    reasons: list[str] = []
    missing_items: list[str] = []

    passed_hard = 0
    for cond in policy.hard_conditions:
        field = cond.get("field")
        op = cond.get("op")
        value = cond.get("value")
        label = cond.get("label", f"{field} {op} {value}")
        actual = getattr(profile, field, None)
        if _compare(actual, op, value, field):
            reasons.append(f"命中条件：{label}")
            passed_hard += 1
        else:
            missing_items.append(label)

    score = 60.0
    for cond in policy.scoring_conditions:
        field = cond.get("field")
        op = cond.get("op")
        value = cond.get("value")
        weight = float(cond.get("weight", 0))
        label = cond.get("label", f"{field} {op} {value}")
        actual = getattr(profile, field, None)
        if _compare(actual, op, value, field):
            score += weight
            reasons.append(f"加分项：{label}")

    if not policy.hard_conditions or passed_hard == len(policy.hard_conditions):
        eligibility = "eligible"
    else:
        eligibility = "potential"
        penalty = 20 if len(missing_items) == 1 else 40
        score = max(score - penalty, 0)

    hard_total = len(policy.hard_conditions or [])
    hard_match_ratio = (passed_hard / hard_total) if hard_total else 1.0

    return {
        "eligibility": eligibility,
        "score": round(score, 2),
        "reasons": reasons,
        "missing_items": missing_items,
        "hard_matched": passed_hard,
        "hard_total": hard_total,
        "hard_match_ratio": round(hard_match_ratio, 4),
    }


def _is_relevant_result(evaluated: dict) -> bool:
    # 结果只保留“可申报”和高相关“需完善”，降低噪音推荐。
    if evaluated["eligibility"] == "eligible":
        return True

    hard_total = int(evaluated.get("hard_total", 0))
    hard_matched = int(evaluated.get("hard_matched", 0))
    score = float(evaluated.get("score", 0))

    if hard_total > 0:
        return hard_matched > 0 and score >= 45
    return score >= 55


def run_match_task(session: Session, enterprise_id: str) -> MatchTask:
    enterprise = session.get(EnterpriseProfile, enterprise_id)
    if not enterprise:
        raise ValueError("enterprise not found")

    task = MatchTask(enterprise_id=enterprise_id, status="done")
    session.add(task)
    session.flush()

    today = date.today()
    policies = session.scalars(
        select(Policy).where(
            Policy.effective_from <= today,
            (Policy.effective_to.is_(None) | (Policy.effective_to >= today)),
        )
    ).all()

    results: list[MatchResult] = []
    for policy in policies:
        evaluated = _evaluate_policy(enterprise, policy)
        if not _is_relevant_result(evaluated):
            continue
        results.append(
            MatchResult(
                task_id=task.id,
                policy_id=policy.id,
                eligibility=evaluated["eligibility"],
                score=evaluated["score"],
                reasons=evaluated["reasons"],
                missing_items=evaluated["missing_items"],
            )
        )

    # 幂等：同 task_id 不重复插入
    session.execute(delete(MatchResult).where(MatchResult.task_id == task.id))
    session.add_all(results)
    session.commit()
    session.refresh(task)
    return task


def _next_action_by_eligibility(eligibility: str) -> str:
    if eligibility == "eligible":
        return "准备申报材料"
    return "补齐条件后再评估"


def get_task_result(session: Session, task_id: str, view: str = "full") -> dict | None:
    task = session.get(MatchTask, task_id)
    if not task:
        return None

    rows = session.scalars(select(MatchResult).where(MatchResult.task_id == task_id)).all()
    eligibility_order = {"eligible": 0, "potential": 1}
    rows = sorted(
        rows,
        key=lambda x: (
            eligibility_order.get(x.eligibility, 99),
            -x.score,
            len(x.missing_items or []),
        ),
    )
    policy_map = {
        p.id: p
        for p in session.scalars(select(Policy).where(Policy.id.in_([r.policy_id for r in rows]))).all()
    }

    summary = {
        "eligible_count": sum(1 for r in rows if r.eligibility == "eligible"),
        "potential_count": sum(1 for r in rows if r.eligibility == "potential"),
    }

    result_items = [
        {
            "policy_id": r.policy_id,
            "policy_title": policy_map.get(r.policy_id).title if policy_map.get(r.policy_id) else r.policy_id,
            "source_url": policy_map.get(r.policy_id).source_url if policy_map.get(r.policy_id) else "",
            "eligibility": r.eligibility,
            "score": r.score,
            "reasons": r.reasons,
            "missing_items": r.missing_items,
            "next_action": _next_action_by_eligibility(r.eligibility),
        }
        for r in rows
    ]

    if view == "summary":
        preview = [
            {
                "policy_id": item["policy_id"],
                "policy_title": item["policy_title"],
                "eligibility": item["eligibility"],
                "next_action": item["next_action"],
            }
            for item in result_items[:3]
        ]
        return {
            "status": task.status,
            "view": "summary",
            "summary": summary,
            "results": preview,
            "login_required_for_full": True,
        }

    return {
        "status": task.status,
        "view": "full",
        "summary": summary,
        "results": result_items,
    }
