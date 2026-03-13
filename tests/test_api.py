def login_and_get_headers(client, username="enterprise", password="123456"):
    login = client.post(
        "/api/v1/auth/password/login",
        json={"username": username, "password": password},
    )
    assert login.status_code == 200
    token = login.json()["data"]["token"]
    return {"Authorization": f"Bearer {token}"}


def create_enterprise(client, headers, uscc="913100000000000001"):
    payload = {
        "enterprise_name": "上海某科技有限公司",
        "uscc": uscc,
        "region_code": "SH-PD",
        "industry_code": "C39",
        "contact_name": "张三",
        "contact_mobile": "13800138000",
        "employee_scale": "50-99",
        "revenue_range": "1000万-5000万",
        "rd_ratio": 6,
        "qualification_tags": ["高新技术企业", "创新型中小企业"],
        "ip_count": 15,
    }
    resp = client.post("/api/v1/enterprise-profiles", json=payload, headers=headers)
    assert resp.status_code == 200
    return resp.json()["data"]["enterprise_id"]


def test_login_required_for_business_apis(client):
    no_auth_profile = client.post(
        "/api/v1/enterprise-profiles",
        json={
            "enterprise_name": "A公司",
            "uscc": "913100000000000099",
            "region_code": "SH-PD",
            "industry_code": "C39",
            "contact_name": "张三",
            "contact_mobile": "13800138000",
        },
    )
    assert no_auth_profile.status_code == 401

    no_auth_me = client.get("/api/v1/auth/me")
    assert no_auth_me.status_code == 401


def test_healthz_returns_ok(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert resp.json()["bootstrap_on_startup"] is False


def test_full_flow_with_password_login(client):
    headers = login_and_get_headers(client)
    enterprise_id = create_enterprise(client, headers=headers)

    create_task = client.post("/api/v1/policy-matches", json={"enterprise_id": enterprise_id}, headers=headers)
    assert create_task.status_code == 200
    task_id = create_task.json()["data"]["task_id"]

    full_result = client.get(f"/api/v1/policy-matches/{task_id}?view=full", headers=headers)
    assert full_result.status_code == 200
    data = full_result.json()["data"]
    assert data["view"] == "full"
    assert len(data["results"]) > 0
    assert "not_eligible_count" not in data["summary"]
    assert data["results"][0]["next_action"] in {"准备申报材料", "补齐条件后再评估"}
    for item in data["results"]:
        assert item["eligibility"] in {"eligible", "potential"}
        assert "/knowledge/#/detail2/" in item["source_url"]

    top_policy_id = data["results"][0]["policy_id"]
    policy_detail = client.get(f"/api/v1/policies/{top_policy_id}", headers=headers)
    assert policy_detail.status_code == 200
    assert policy_detail.json()["data"]["id"] == top_policy_id
    assert "/knowledge/#/detail2/" in policy_detail.json()["data"]["source_url"]
    assert len(policy_detail.json()["data"]["outline_sections"]) >= 5

    qa_resp = client.post(
        "/api/v1/qa/policy",
        json={
            "enterprise_id": enterprise_id,
            "question": "为什么我符合这条政策？",
            "context_policy_id": top_policy_id,
        },
        headers=headers,
    )
    assert qa_resp.status_code == 200
    qa_data = qa_resp.json()["data"]
    assert qa_data["answer"]
    assert len(qa_data["citations"]) >= 1
    assert "confidence" in qa_data
    assert "risk_flags" in qa_data
    assert "next_actions" in qa_data
    assert "evidence_snippets" in qa_data

    ticket_resp = client.post(
        "/api/v1/service-tickets",
        json={
            "enterprise_id": enterprise_id,
            "issue_type": "eligibility_consult",
            "description": "请人工确认补贴申报优先级",
            "contact_mobile": "13800138000",
        },
        headers=headers,
    )
    assert ticket_resp.status_code == 200
    ticket_id = ticket_resp.json()["data"]["ticket_id"]

    get_ticket = client.get(f"/api/v1/service-tickets/{ticket_id}", headers=headers)
    assert get_ticket.status_code == 200
    assert get_ticket.json()["data"]["status"] == "pending"


def test_ticket_transition_rules(client):
    headers = login_and_get_headers(client)
    enterprise_id = create_enterprise(client, headers=headers, uscc="913100000000000002")

    create = client.post(
        "/api/v1/service-tickets",
        json={
            "enterprise_id": enterprise_id,
            "issue_type": "eligibility_consult",
            "description": "需要人工确认",
            "contact_mobile": "13800138000",
        },
        headers=headers,
    )
    assert create.status_code == 200
    ticket_id = create.json()["data"]["ticket_id"]

    invalid_transition = client.patch(
        f"/api/v1/service-tickets/{ticket_id}",
        json={"status": "resolved", "log_message": "跳过处理中"},
        headers=headers,
    )
    assert invalid_transition.status_code == 400

    to_processing = client.patch(
        f"/api/v1/service-tickets/{ticket_id}",
        json={"status": "processing", "log_message": "顾问接单"},
        headers=headers,
    )
    assert to_processing.status_code == 200

    to_resolved = client.patch(
        f"/api/v1/service-tickets/{ticket_id}",
        json={"status": "resolved", "log_message": "已给出建议"},
        headers=headers,
    )
    assert to_resolved.status_code == 200

    to_closed = client.patch(
        f"/api/v1/service-tickets/{ticket_id}",
        json={"status": "closed", "log_message": "用户确认关闭"},
        headers=headers,
    )
    assert to_closed.status_code == 200


def test_qa_guardrails(client):
    headers = login_and_get_headers(client)
    enterprise_id = create_enterprise(client, headers=headers, uscc="913100000000000003")

    q1 = client.post(
        "/api/v1/qa/policy",
        json={"enterprise_id": enterprise_id, "question": "这条政策我能不能报？"},
        headers=headers,
    )
    assert q1.status_code == 200

    q2 = client.post(
        "/api/v1/qa/policy",
        json={"enterprise_id": enterprise_id, "question": "为什么还不确定？"},
        headers=headers,
    )
    assert q2.status_code == 200
    assert q2.json()["data"]["recommend_handoff"] is True

    q3 = client.post(
        "/api/v1/qa/policy",
        json={"enterprise_id": enterprise_id, "question": "你能保证100%通过并规避法律责任吗？"},
        headers=headers,
    )
    assert q3.status_code == 200
    assert q3.json()["data"]["recommend_handoff"] is True
    assert q3.json()["data"]["handoff_reason"]


def test_qa_handoff_ticket_creation(client):
    headers = login_and_get_headers(client)
    enterprise_id = create_enterprise(client, headers=headers, uscc="913100000000000006")
    qa_resp = client.post(
        "/api/v1/qa/policy",
        json={
            "enterprise_id": enterprise_id,
            "question": "这条政策我还缺什么，建议人工协助",
        },
        headers=headers,
    )
    assert qa_resp.status_code == 200
    qa_data = qa_resp.json()["data"]

    handoff = client.post(
        "/api/v1/qa/handoff-ticket",
        json={
            "enterprise_id": enterprise_id,
            "question": "这条政策我还缺什么，建议人工协助",
            "answer": qa_data["answer"],
            "handoff_reason": qa_data.get("handoff_reason"),
            "context_policy_id": None,
        },
        headers=headers,
    )
    assert handoff.status_code == 200
    handoff_data = handoff.json()["data"]
    assert handoff_data["status"] == "pending"
    assert handoff_data["issue_type"] == "qa_handoff"

    get_ticket = client.get(f"/api/v1/service-tickets/{handoff_data['ticket_id']}", headers=headers)
    assert get_ticket.status_code == 200


def test_qa_can_reselect_policy_by_question(client):
    headers = login_and_get_headers(client)
    enterprise_id = create_enterprise(client, headers=headers, uscc="913100000000000007")

    create_task = client.post("/api/v1/policy-matches", json={"enterprise_id": enterprise_id}, headers=headers)
    assert create_task.status_code == 200
    task_id = create_task.json()["data"]["task_id"]
    full_result = client.get(f"/api/v1/policy-matches/{task_id}?view=full", headers=headers)
    assert full_result.status_code == 200
    context_policy_id = full_result.json()["data"]["results"][0]["policy_id"]

    qa_resp = client.post(
        "/api/v1/qa/policy",
        json={
            "enterprise_id": enterprise_id,
            "question": "专精特新这条政策，哪些指标补齐后成功率更高？",
            "context_policy_id": context_policy_id,
        },
        headers=headers,
    )
    assert qa_resp.status_code == 200
    data = qa_resp.json()["data"]
    assert len(data["citations"]) >= 1
    assert "专精特新" in data["citations"][0]["title"]
    assert "policy_reselected" in data["risk_flags"]


def test_qa_summary_intent_uses_match_results(client):
    headers = login_and_get_headers(client)
    enterprise_id = create_enterprise(client, headers=headers, uscc="913100000000000107")

    create_task = client.post("/api/v1/policy-matches", json={"enterprise_id": enterprise_id}, headers=headers)
    assert create_task.status_code == 200

    qa_resp = client.post(
        "/api/v1/qa/policy",
        json={"enterprise_id": enterprise_id, "question": "总共我能匹配到几条政策？优先看哪几条？"},
        headers=headers,
    )
    assert qa_resp.status_code == 200
    data = qa_resp.json()["data"]
    assert data["intent"] == "summary"
    assert "summary_intent" in data["risk_flags"]
    assert "insufficient_context" not in data["risk_flags"]
    assert "匹配到" in data["answer"] or "可申报" in data["answer"]
    assert "如果你愿意" not in data["answer"]
    assert data["selected_policy_id"]


def test_qa_followup_continues_previous_materials_topic(client, monkeypatch):
    from app.services import qa as qa_service

    headers = login_and_get_headers(client)
    enterprise_id = create_enterprise(client, headers=headers, uscc="913100000000000109")
    monkeypatch.setattr(qa_service, "generate_with_glm", lambda *args, **kwargs: None)

    create_task = client.post("/api/v1/policy-matches", json={"enterprise_id": enterprise_id}, headers=headers)
    assert create_task.status_code == 200
    task_id = create_task.json()["data"]["task_id"]
    full_result = client.get(f"/api/v1/policy-matches/{task_id}?view=full", headers=headers)
    assert full_result.status_code == 200
    context_policy_id = full_result.json()["data"]["results"][0]["policy_id"]

    first = client.post(
        "/api/v1/qa/policy",
        json={
            "enterprise_id": enterprise_id,
            "question": "高新技术企业研发补贴 需要哪些材料？",
            "context_policy_id": context_policy_id,
        },
        headers=headers,
    )
    assert first.status_code == 200
    first_data = first.json()["data"]
    assert first_data["intent"] == "materials"

    second = client.post(
        "/api/v1/qa/policy",
        json={
            "enterprise_id": enterprise_id,
            "question": "继续给我拆解",
            "context_policy_id": context_policy_id,
        },
        headers=headers,
    )
    assert second.status_code == 200
    second_data = second.json()["data"]
    assert second_data["intent"] == "materials"
    assert "材料" in second_data["answer"] or "证书" in second_data["answer"] or "审计报告" in second_data["answer"]
    assert "命中的核心依据" not in second_data["answer"]


def test_qa_short_probe_stays_on_materials_topic(client, monkeypatch):
    from app.services import qa as qa_service

    headers = login_and_get_headers(client)
    enterprise_id = create_enterprise(client, headers=headers, uscc="913100000000000209")

    create_task = client.post("/api/v1/policy-matches", json={"enterprise_id": enterprise_id}, headers=headers)
    assert create_task.status_code == 200
    task_id = create_task.json()["data"]["task_id"]
    full_result = client.get(f"/api/v1/policy-matches/{task_id}?view=full", headers=headers)
    assert full_result.status_code == 200
    context_policy_id = full_result.json()["data"]["results"][1]["policy_id"]

    monkeypatch.setattr(qa_service, "generate_with_glm", lambda *args, **kwargs: None)

    first = client.post(
        "/api/v1/qa/policy",
        json={
            "enterprise_id": enterprise_id,
            "question": "专精特新企业培育支持 这个需要什么材料？",
            "context_policy_id": context_policy_id,
        },
        headers=headers,
    )
    assert first.status_code == 200

    second = client.post(
        "/api/v1/qa/policy",
        json={
            "enterprise_id": enterprise_id,
            "question": "继续给我拆解",
            "context_policy_id": context_policy_id,
        },
        headers=headers,
    )
    assert second.status_code == 200

    third = client.post(
        "/api/v1/qa/policy",
        json={
            "enterprise_id": enterprise_id,
            "question": "还有吗？",
            "context_policy_id": context_policy_id,
        },
        headers=headers,
    )
    assert third.status_code == 200
    third_data = third.json()["data"]
    assert third_data["intent"] == "materials"
    assert "营业执照" in third_data["answer"] or "申报表" in third_data["answer"] or "盖章要求" in third_data["answer"]
    assert "基于《专精特新企业培育支持》" not in third_data["answer"]


def test_qa_prefers_llm_reply_when_available(client, monkeypatch):
    from app.services import qa as qa_service

    headers = login_and_get_headers(client)
    enterprise_id = create_enterprise(client, headers=headers, uscc="913100000000000110")

    create_task = client.post("/api/v1/policy-matches", json={"enterprise_id": enterprise_id}, headers=headers)
    assert create_task.status_code == 200

    monkeypatch.setattr(qa_service, "generate_with_glm", lambda *args, **kwargs: "这是模型直接生成的回复。")

    qa_resp = client.post(
        "/api/v1/qa/policy",
        json={"enterprise_id": enterprise_id, "question": "总共我能匹配到几条政策？"},
        headers=headers,
    )
    assert qa_resp.status_code == 200
    data = qa_resp.json()["data"]
    assert data["answer"] == "这是模型直接生成的回复。"


def test_qa_discovery_intent_can_answer_from_knowledge_base(client):
    headers = login_and_get_headers(client)
    enterprise_id = create_enterprise(client, headers=headers, uscc="913100000000000108")

    import_resp = client.post(
        "/api/v1/knowledge-base/import",
        json={
            "source_type": "raw_text",
            "source_uri": "manual://policy-note-3",
            "title": "上海算力补贴政策摘要",
            "raw_text": "上海算力补贴通常围绕智算服务、算力券、模型训练和推理资源采购展开，申报前需结合所在区和年度指南核对条件。",
        },
        headers=headers,
    )
    assert import_resp.status_code == 200

    qa_resp = client.post(
        "/api/v1/qa/policy",
        json={"enterprise_id": enterprise_id, "question": "有没有算力补贴政策？"},
        headers=headers,
    )
    assert qa_resp.status_code == 200
    data = qa_resp.json()["data"]
    assert data["intent"] == "discovery"
    assert "discovery_intent" in data["risk_flags"]
    assert len(data["citations"]) >= 1
    assert "算力补贴" in data["citations"][0]["title"]
    assert any(keyword in data["answer"] for keyword in ["所在区", "哪个区", "全上海", "浦东新区", "各区", "年度指南"])
    assert "参考依据" not in data["answer"]


def test_qa_confidence_drops_when_insufficient(client):
    headers = login_and_get_headers(client)
    payload = {
        "enterprise_name": "无上下文企业",
        "uscc": "913100000000000008",
        "region_code": "SH-PD",
        "industry_code": "C39",
        "contact_name": "李一",
        "contact_mobile": "13800138008",
        "employee_scale": "10-49",
        "revenue_range": "1000万以下",
        "rd_ratio": 1,
        "qualification_tags": [],
        "ip_count": 0,
    }
    profile = client.post("/api/v1/enterprise-profiles", json=payload, headers=headers)
    assert profile.status_code == 200
    enterprise_id = profile.json()["data"]["enterprise_id"]

    qa_resp = client.post(
        "/api/v1/qa/policy",
        json={"enterprise_id": enterprise_id, "question": "请问我应该怎么申报？"},
        headers=headers,
    )
    assert qa_resp.status_code == 200
    data = qa_resp.json()["data"]
    assert "insufficient_context" in data["risk_flags"]
    assert data["confidence"] <= 0.5


def test_low_relevance_policies_are_filtered(client):
    headers = login_and_get_headers(client)
    payload = {
        "enterprise_name": "低匹配企业",
        "uscc": "913100000000000088",
        "region_code": "SH-MH",
        "industry_code": "C39",
        "contact_name": "赵六",
        "contact_mobile": "13800138088",
        "employee_scale": "10-49",
        "revenue_range": "1000万以下",
        "rd_ratio": 1,
        "qualification_tags": [],
        "ip_count": 1,
    }
    resp = client.post("/api/v1/enterprise-profiles", json=payload, headers=headers)
    assert resp.status_code == 200
    enterprise_id = resp.json()["data"]["enterprise_id"]

    create_task = client.post("/api/v1/policy-matches", json={"enterprise_id": enterprise_id}, headers=headers)
    assert create_task.status_code == 200
    task_id = create_task.json()["data"]["task_id"]

    full_result = client.get(f"/api/v1/policy-matches/{task_id}?view=full", headers=headers)
    assert full_result.status_code == 200
    data = full_result.json()["data"]
    assert data["summary"]["eligible_count"] == 0
    assert data["summary"]["potential_count"] == 0
    assert data["results"] == []


def test_shanghai_all_region_can_match_cross_district_policies(client):
    headers = login_and_get_headers(client)
    payload = {
        "enterprise_name": "全市检索企业",
        "uscc": "913100000000000077",
        "region_code": "SH-ALL",
        "industry_code": "C39",
        "contact_name": "王五",
        "contact_mobile": "13800138077",
        "employee_scale": "50-99",
        "revenue_range": "1000万-5000万",
        "rd_ratio": 6,
        "qualification_tags": ["高新技术企业", "创新型中小企业"],
        "ip_count": 12,
    }
    resp = client.post("/api/v1/enterprise-profiles", json=payload, headers=headers)
    assert resp.status_code == 200
    enterprise_id = resp.json()["data"]["enterprise_id"]

    create_task = client.post("/api/v1/policy-matches", json={"enterprise_id": enterprise_id}, headers=headers)
    assert create_task.status_code == 200
    task_id = create_task.json()["data"]["task_id"]

    full_result = client.get(f"/api/v1/policy-matches/{task_id}?view=full", headers=headers)
    assert full_result.status_code == 200
    data = full_result.json()["data"]
    assert data["results"]
    assert any(item["policy_title"] == "高新技术企业研发补贴" for item in data["results"])


def test_knowledge_base_import_and_search(client, tmp_path):
    headers = login_and_get_headers(client)

    raw_import = client.post(
        "/api/v1/knowledge-base/import",
        json={
            "source_type": "raw_text",
            "source_uri": "manual://policy-note-1",
            "title": "算力补贴政策摘要",
            "raw_text": "上海算力补贴通常关注算力券、智算中心、人工智能训练推理场景和服务器采购补贴。",
        },
        headers=headers,
    )
    assert raw_import.status_code == 200
    assert raw_import.json()["data"]["chunk_count"] >= 1

    note_file = tmp_path / "policy.txt"
    note_file.write_text("浦东新区文创项目支持原创内容开发、文化科技融合和品牌活动。", encoding="utf-8")
    file_import = client.post(
        "/api/v1/knowledge-base/import",
        json={
            "source_type": "file",
            "source_uri": str(note_file),
            "title": "浦东文创政策笔记",
        },
        headers=headers,
    )
    assert file_import.status_code == 200

    search_resp = client.post(
        "/api/v1/knowledge-base/search",
        json={"query": "算力补贴 智算中心", "limit": 3},
        headers=headers,
    )
    assert search_resp.status_code == 200
    data = search_resp.json()["data"]
    assert len(data) >= 1
    assert "算力补贴" in data[0]["title"]


def test_qa_can_use_knowledge_base_without_policy_context(client):
    headers = login_and_get_headers(client)
    enterprise_id = create_enterprise(client, headers=headers, uscc="913100000000000099")

    import_resp = client.post(
        "/api/v1/knowledge-base/import",
        json={
            "source_type": "raw_text",
            "source_uri": "manual://policy-note-2",
            "title": "算力补贴政策摘要",
            "raw_text": "上海人工智能算力补贴通常围绕智算服务、算力券、模型训练和推理资源采购展开，申报前要核对所在区和年度指南。",
        },
        headers=headers,
    )
    assert import_resp.status_code == 200

    qa_resp = client.post(
        "/api/v1/qa/policy",
        json={"enterprise_id": enterprise_id, "question": "算力补贴政策有没有？"},
        headers=headers,
    )
    assert qa_resp.status_code == 200
    data = qa_resp.json()["data"]
    assert len(data["citations"]) >= 1
    assert "算力补贴" in data["citations"][0]["title"]
    assert "insufficient_context" not in data["risk_flags"]


def test_imported_knowledge_can_be_structured_into_matchable_policies(client):
    headers = login_and_get_headers(client)
    enterprise_id = create_enterprise(client, headers=headers, uscc="913100000000000066")

    raw_text = """
一、科技类政策
1．高新技术企业认定
维度 详细说明与核心要点
政策概述
性质：国家级企业资质认定。
核心认定条件
企业须同时满足以下条件：
1. 注册成立满一年。
2. 需具备至少1项核心知识产权。
3. 研发费用占比应达到高企认定最低线。
4. 主要产品技术属于重点支持领域。
申报时间与平台
上海市通常每年 5 月至 9 月受理，通过“一网通办”申报。
基本流程
企业自评、网上申报、区级推荐、市级评审、公示发证。

2．科技型中小企业评价入库政策与服务
维度 详细说明与核心要点
政策概述
定位：国家级科技型中小企业入库服务。
评价标准（需同时满足）
1. 建议形成持续研发投入。
2. 企业规模需处于中小企业区间。
3. 可准备知识产权证书、研发项目立项材料。
申报平台与流程
通过优质中小企业梯度培育平台在线填报。
    """.strip()

    import_resp = client.post(
        "/api/v1/knowledge-base/import",
        json={
            "source_type": "raw_text",
            "source_uri": "manual://structured-tech-policies",
            "title": "科技政策汇编",
            "raw_text": raw_text,
        },
        headers=headers,
    )
    assert import_resp.status_code == 200

    policies_resp = client.get("/api/v1/policies?page=1&page_size=50", headers=headers)
    assert policies_resp.status_code == 200
    titles = [item["title"] for item in policies_resp.json()["data"]]
    assert "高新技术企业认定" in titles
    assert "科技型中小企业评价入库政策与服务" in titles

    create_task = client.post("/api/v1/policy-matches", json={"enterprise_id": enterprise_id}, headers=headers)
    assert create_task.status_code == 200
    task_id = create_task.json()["data"]["task_id"]

    full_result = client.get(f"/api/v1/policy-matches/{task_id}?view=full", headers=headers)
    assert full_result.status_code == 200
    result_titles = [item["policy_title"] for item in full_result.json()["data"]["results"]]
    assert "高新技术企业认定" in result_titles

    preview = client.get("/api/v1/knowledge-base/documents/" + import_resp.json()["data"]["id"] + "/preview")
    assert preview.status_code == 200
    assert "科技政策汇编" in preview.text


def test_imported_document_removes_footer_and_uses_official_source_url(client):
    headers = login_and_get_headers(client)
    raw_text = """
陈灵林 13818957602
第 1 页 共 2 页
1．高新技术企业认定
维度 详细说明与核心要点
政策概述
性质：国家级企业资质认定。
核心认定条件
1. 注册成立满一年。
2. 需具备至少1项核心知识产权。
3. 研发费用占比应达到高企认定最低线。
4. 主要产品技术属于重点支持领域。
申报时间与平台
上海市通常每年 5 月至 9 月受理，通过“一网通办”申报。
陈灵林 13818957602
第 2 页 共 2 页
    """.strip()

    import_resp = client.post(
        "/api/v1/knowledge-base/import",
        json={
            "source_type": "raw_text",
            "source_uri": "manual://footer-clean-check",
            "title": "高企资料样本",
            "raw_text": raw_text,
        },
        headers=headers,
    )
    assert import_resp.status_code == 200
    document_id = import_resp.json()["data"]["id"]

    doc_detail = client.get(f"/api/v1/knowledge-base/documents/{document_id}", headers=headers)
    assert doc_detail.status_code == 200
    cleaned_text = doc_detail.json()["data"]["cleaned_text"]
    assert "陈灵林 13818957602" not in cleaned_text
    assert "第 1 页 共 2 页" not in cleaned_text

    policies_resp = client.get("/api/v1/policies?page=1&page_size=50", headers=headers)
    assert policies_resp.status_code == 200
    high_tech = next(item for item in policies_resp.json()["data"] if item["title"] == "高新技术企业认定")
    assert high_tech["source_url"].startswith("https://")
    assert "stcsm.sh.gov.cn" in high_tech["source_url"] or "shanghai.gov.cn" in high_tech["source_url"]


def test_policy_detail_returns_outline_sections(client):
    headers = login_and_get_headers(client)
    raw_text = """
1．专精特新企业梯度培育体系
政策概述
面向创新能力较强的中小企业，建立创新型中小企业、专精特新中小企业、专精特新“小巨人”梯度培育路径。
支持方向与范围
提供资质认定、项目辅导、融资对接、市场拓展等支持。
申报时间
原则上按年度组织，以上海市主管部门通知为准。
申报主体条件
企业需处于中小企业规模区间，且具备创新型中小企业基础资质。
基本流程
企业在线提交材料，区级初审后报市级复核。
后期管理
认定后需按要求参与年度复核，并持续保持合规经营。
对普通企业的核心价值
有助于获取资质背书、政策推荐和融资资源。
    """.strip()

    import_resp = client.post(
        "/api/v1/knowledge-base/import",
        json={
            "source_type": "raw_text",
            "source_uri": "manual://outline-sections-check",
            "title": "专精特新政策样本",
            "raw_text": raw_text,
        },
        headers=headers,
    )
    assert import_resp.status_code == 200

    policies_resp = client.get("/api/v1/policies?page=1&page_size=50", headers=headers)
    assert policies_resp.status_code == 200
    policy = next(item for item in policies_resp.json()["data"] if item["title"] == "专精特新企业梯度培育体系")

    detail_resp = client.get(f"/api/v1/policies/{policy['id']}", headers=headers)
    assert detail_resp.status_code == 200
    outline = detail_resp.json()["data"]["outline_sections"]
    titles = [section["title"] for section in outline]
    assert "政策概述" in titles
    assert "支持内容" in titles
    assert "申报条件" in titles
    assert all(section["items"] for section in outline)
