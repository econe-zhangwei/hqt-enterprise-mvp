(function () {
  const state = {
    token: localStorage.getItem("hqt_token") || "",
    user: localStorage.getItem("hqt_user") || "",
    enterpriseId: null,
    taskId: null,
    matchResults: [],
    topPolicyId: null,
    lastTicketId: null,
    lastQA: null,
    askingAI: false,
  };

  const views = {
    overview: {
      title: "总览",
      desc: "查看当前企业政策匹配整体状态与建议动作。",
    },
    profile: {
      title: "企业信息",
      desc: "维护企业画像字段，作为政策匹配输入。",
    },
    match: {
      title: "政策匹配",
      desc: "重点查看可申报与需完善政策。",
    },
    assistant: {
      title: "AI 助手",
      desc: "围绕当前企业画像和政策结果进行问答解释。",
    },
    ticket: {
      title: "工单中心",
      desc: "提交人工顾问协助并跟踪处理状态。",
    },
  };

  const ELIGIBILITY_LABEL = {
    eligible: "可申报",
    potential: "需完善",
  };

  const LEVEL_LABEL = {
    city: "市级",
    district: "区级",
  };

  const REGION_LABEL = {
    "SH-ALL": "全上海",
    "SH-PD": "浦东新区",
    "SH-MH": "闵行区",
  };

  function labelEligibility(code) {
    return ELIGIBILITY_LABEL[code] || code;
  }

  function labelAction(text) {
    const map = {
      prepare_materials: "准备申报材料",
      consult_human: "补齐条件后再评估",
    };
    return map[text] || text;
  }

  function sourceLinkHtml(url) {
    if (!url) return "";
    return `<div class="muted">来源：<a href="${url}" target="_blank">政策原文</a></div>`;
  }

  function policySourceDetailHtml(url) {
    if (!url) return "";
    return `<p class="muted">原文：<a href="${url}" target="_blank">${url}</a></p>`;
  }

  function escapeHtml(text) {
    return String(text || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function policyOutlineHtml(sections) {
    if (!sections || !sections.length) return "";
    return `
      <div class="detail-outline">
        ${sections
          .map((section) => `
            <section class="detail-section">
              <h4>${escapeHtml(section.title)}</h4>
              <ul>
                ${(section.items || [])
                  .map((item) => `<li>${escapeHtml(item)}</li>`)
                  .join("")}
              </ul>
            </section>
          `)
          .join("")}
      </div>
    `;
  }

  function headers() {
    return {
      "Content-Type": "application/json",
      Authorization: `Bearer ${state.token}`,
    };
  }

  async function api(path, options = {}) {
    const resp = await fetch(`/api/v1${path}`, {
      headers: headers(),
      ...options,
    });
    const data = await resp.json();
    if (!resp.ok) {
      if (resp.status === 401) {
        localStorage.removeItem("hqt_token");
        localStorage.removeItem("hqt_user");
        window.location.href = "/static/login.html";
      }
      throw new Error(data.detail || "请求失败");
    }
    return data;
  }

  async function checkAuth() {
    if (!state.token) {
      window.location.href = "/static/login.html";
      return;
    }
    const me = await api("/auth/me");
    state.user = me.data.subject;
    document.getElementById("authUser").textContent = `已登录：${state.user}`;
  }

  function switchView(name) {
    Object.keys(views).forEach((key) => {
      const view = document.getElementById(`view-${key}`);
      const btn = document.querySelector(`.nav button[data-view='${key}']`);
      if (key === name) {
        view.classList.add("active");
        btn.classList.add("active");
      } else {
        view.classList.remove("active");
        btn.classList.remove("active");
      }
    });
    document.getElementById("pageTitle").textContent = views[name].title;
    document.getElementById("pageDesc").textContent = views[name].desc;
  }

  function profilePayload() {
    return {
      enterprise_name: document.getElementById("enterprise_name").value.trim(),
      uscc: document.getElementById("uscc").value.trim(),
      region_code: document.getElementById("region_code").value,
      industry_code: document.getElementById("industry_code").value.trim(),
      contact_name: document.getElementById("contact_name").value.trim(),
      contact_mobile: document.getElementById("contact_mobile").value.trim(),
      employee_scale: document.getElementById("employee_scale").value,
      revenue_range: document.getElementById("revenue_range").value.trim(),
      rd_ratio: Number(document.getElementById("rd_ratio").value),
      ip_count: Number(document.getElementById("ip_count").value),
      qualification_tags: document
        .getElementById("qualification_tags")
        .value.split(",")
        .map((x) => x.trim())
        .filter(Boolean),
    };
  }

  async function saveProfile(alsoMatch) {
    const msg = document.getElementById("profileMsg");
    msg.textContent = "正在保存...";
    const resp = await api("/enterprise-profiles", {
      method: "POST",
      body: JSON.stringify(profilePayload()),
    });
    state.enterpriseId = resp.data.enterprise_id;
    msg.textContent = `保存成功，企业ID：${state.enterpriseId}`;

    if (alsoMatch) {
      await runMatch();
      switchView("match");
    }
  }

  function setOverview(summary) {
    document.getElementById("sEligible").textContent = summary.eligible_count ?? 0;
    document.getElementById("sPotential").textContent = summary.potential_count ?? 0;
    document.getElementById("sPriority").textContent =
      (summary.eligible_count ?? 0) + (summary.potential_count ?? 0);

    const actions = state.matchResults
      .slice(0, 3)
      .map((r) => `- ${r.policy_title}：${labelAction(r.next_action)}`)
      .join("\n");
    document.getElementById("nextActions").textContent = actions || "暂无建议动作";
  }

  function renderMatch(data) {
    state.matchResults = data.results || [];
    if (state.matchResults.length) state.topPolicyId = state.matchResults[0].policy_id;

    document.getElementById("matchSummary").textContent = `可申报 ${data.summary.eligible_count}，需完善 ${data.summary.potential_count}`;

    const list = document.getElementById("matchList");
    list.innerHTML = "";

    if (!state.matchResults.length) {
      list.innerHTML = `<div class="muted">当前企业画像下暂无高相关政策，建议先完善企业信息或转人工咨询。</div>`;
      setOverview(data.summary);
      return;
    }

    state.matchResults.forEach((item) => {
      const card = document.createElement("article");
      card.className = "policy-card";
      card.innerHTML = `
        <div class="policy-head">
          <strong>${item.policy_title}</strong>
          <span class="pill ${item.eligibility}">${labelEligibility(item.eligibility)}</span>
          <span class="tag">${item.score}分</span>
        </div>
        <div class="muted">下一步：${labelAction(item.next_action)}</div>
        ${sourceLinkHtml(item.source_url)}
        <div class="muted">命中原因：${(item.reasons || []).join("；") || "无"}</div>
        <div class="muted">缺口项：${(item.missing_items || []).join("；") || "无"}</div>
        <button class="btn-ghost" data-policy-id="${item.policy_id}">查看详情</button>
      `;
      list.appendChild(card);
    });

    list.querySelectorAll("button[data-policy-id]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const id = btn.getAttribute("data-policy-id");
        const detail = await api(`/policies/${id}`);
        state.topPolicyId = id;
        const p = detail.data;
        document.getElementById("policyDetail").innerHTML = `
          <h3 style="margin-bottom:8px">${p.title}</h3>
          <p class="muted">支持方式：${p.support_type}</p>
          <p class="muted">区域：${REGION_LABEL[p.region_code] || p.region_code} / 层级：${LEVEL_LABEL[p.level] || p.level}</p>
          <p class="muted">生效时间：${p.effective_from} ~ ${p.effective_to || "长期"}</p>
          <p class="muted">所需材料：${(p.required_materials || []).join("、") || "无"}</p>
          <p class="muted">更新时间：${p.updated_at || "-"}</p>
          ${policyOutlineHtml(p.outline_sections)}
          ${policySourceDetailHtml(p.source_url)}
        `;
      });
    });

    setOverview(data.summary);
  }

  async function runMatch() {
    if (!state.enterpriseId) throw new Error("请先保存企业信息");
    const task = await api("/policy-matches", {
      method: "POST",
      body: JSON.stringify({ enterprise_id: state.enterpriseId }),
    });
    state.taskId = task.data.task_id;

    const result = await api(`/policy-matches/${state.taskId}?view=full`);
    renderMatch(result.data);
  }

  function appendChat(role, content) {
    const box = document.getElementById("chatBox");
    const item = document.createElement("div");
    item.className = `chat-item ${role}`;
    item.textContent = content;
    box.appendChild(item);
    box.scrollTop = box.scrollHeight;
    return item;
  }

  function startAITyping() {
    const box = document.getElementById("chatBox");
    const item = document.createElement("div");
    item.className = "chat-item ai ai-typing";
    item.innerHTML = `
      <div class="typing-line">我在看你的问题和政策条件，请稍等…</div>
      <div class="typing-meta">
        <span class="typing-dots"><i></i><i></i><i></i></span>
        <span class="typing-elapsed">0s</span>
      </div>
    `;
    box.appendChild(item);
    box.scrollTop = box.scrollHeight;

    const elapsedEl = item.querySelector(".typing-elapsed");
    const startedAt = Date.now();
    const timer = setInterval(() => {
      const sec = Math.max(0, Math.floor((Date.now() - startedAt) / 1000));
      if (elapsedEl) elapsedEl.textContent = `${sec}s`;
    }, 500);
    return { item, timer };
  }

  function stopAITyping(indicator) {
    if (!indicator) return;
    clearInterval(indicator.timer);
    indicator.item.remove();
  }

  function renderQAInsights(data) {
    const status = document.getElementById("qaStatus");
    const handoffBtn = document.getElementById("qaHandoffBtn");
    handoffBtn.disabled = !data.recommend_handoff;
    if (data.recommend_handoff) {
      status.textContent = data.handoff_reason || "这次建议转人工复核。";
    } else if (data.clarification_needed) {
      status.textContent = "你继续补一句信息，助手会顺着聊下去。";
    } else {
      status.textContent = "需要人工复核时，助手会提示你转人工。";
    }
  }

  async function askAI() {
    if (!state.enterpriseId) throw new Error("请先保存企业信息");
    if (state.askingAI) return;
    const q = document.getElementById("question").value.trim();
    if (!q) return;

    state.askingAI = true;
    const askBtn = document.getElementById("askBtn");
    const questionEl = document.getElementById("question");
    askBtn.disabled = true;
    questionEl.disabled = true;

    appendChat("user", q);
    const typingIndicator = startAITyping();
    try {
      const resp = await api("/qa/policy", {
        method: "POST",
        body: JSON.stringify({
          enterprise_id: state.enterpriseId,
          question: q,
          context_policy_id: state.topPolicyId,
        }),
      });

      const data = resp.data;
      if (data.selected_policy_id) {
        state.topPolicyId = data.selected_policy_id;
      }
      state.lastQA = {
        question: q,
        answer: data.answer,
        handoff_reason: data.handoff_reason || null,
        context_policy_id: data.selected_policy_id || state.topPolicyId,
      };
      appendChat("ai", data.answer);
      renderQAInsights(data);
      questionEl.value = "";
    } finally {
      stopAITyping(typingIndicator);
      state.askingAI = false;
      askBtn.disabled = false;
      questionEl.disabled = false;
      questionEl.focus();
    }
  }

  async function handoffFromQA() {
    if (!state.enterpriseId) throw new Error("请先保存企业信息");
    if (!state.lastQA) throw new Error("请先发起一次 AI 问答");

    const callbackTime = document.getElementById("qaCallbackTime").value.trim();
    const resp = await api("/qa/handoff-ticket", {
      method: "POST",
      body: JSON.stringify({
        enterprise_id: state.enterpriseId,
        question: state.lastQA.question,
        answer: state.lastQA.answer,
        context_policy_id: state.lastQA.context_policy_id,
        handoff_reason: state.lastQA.handoff_reason,
        callback_time: callbackTime || null,
      }),
    });

    state.lastTicketId = resp.data.ticket_id;
    document.getElementById("sTicket").textContent = resp.data.status;
    document.getElementById("ticketMsg").textContent = `工单已创建：${resp.data.ticket_id}，状态：${resp.data.status}`;
    appendChat("ai", `已为你创建人工工单：${resp.data.ticket_id}。你可以在“工单中心”查看进度。`);
    switchView("ticket");
  }

  async function createTicket() {
    if (!state.enterpriseId) throw new Error("请先保存企业信息");
    const desc = document.getElementById("ticketDesc").value.trim();
    const callbackTime = document.getElementById("callbackTime").value.trim();

    const resp = await api("/service-tickets", {
      method: "POST",
      body: JSON.stringify({
        enterprise_id: state.enterpriseId,
        issue_type: "eligibility_consult",
        description: desc,
        contact_mobile: document.getElementById("contact_mobile").value.trim(),
        callback_time: callbackTime || null,
      }),
    });
    state.lastTicketId = resp.data.ticket_id;
    document.getElementById("ticketMsg").textContent = `工单已创建：${state.lastTicketId}，状态：${resp.data.status}`;
    document.getElementById("sTicket").textContent = resp.data.status;
  }

  async function queryTicket() {
    if (!state.lastTicketId) {
      document.getElementById("ticketMsg").textContent = "暂无工单，请先提交。";
      return;
    }
    const resp = await api(`/service-tickets/${state.lastTicketId}`);
    const data = resp.data;
    const latest = (data.logs || [])[data.logs.length - 1];
    document.getElementById("ticketMsg").textContent = `状态：${data.status}；最新记录：${latest ? latest.message : "-"}`;
    document.getElementById("sTicket").textContent = data.status;
  }

  function bindEvents() {
    document.querySelectorAll(".nav button[data-view]").forEach((btn) => {
      btn.addEventListener("click", () => switchView(btn.getAttribute("data-view")));
    });

    document.querySelectorAll("[data-jump-view]").forEach((btn) => {
      btn.addEventListener("click", () => switchView(btn.getAttribute("data-jump-view")));
    });

    document.getElementById("logoutBtn").addEventListener("click", () => {
      localStorage.removeItem("hqt_token");
      localStorage.removeItem("hqt_user");
      window.location.href = "/static/login.html";
    });

    document.getElementById("saveProfileBtn").addEventListener("click", async () => {
      try {
        await saveProfile(false);
      } catch (err) {
        document.getElementById("profileMsg").textContent = err.message || "保存失败";
      }
    });

    document.getElementById("saveAndMatchBtn").addEventListener("click", async () => {
      try {
        await saveProfile(true);
      } catch (err) {
        document.getElementById("profileMsg").textContent = err.message || "保存失败";
      }
    });

    document.getElementById("askBtn").addEventListener("click", async () => {
      try {
        await askAI();
      } catch (err) {
        appendChat("ai", `请求失败：${err.message || "未知错误"}`);
      }
    });

    document.getElementById("question").addEventListener("keydown", async (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        try {
          await askAI();
        } catch (err) {
          appendChat("ai", `请求失败：${err.message || "未知错误"}`);
        }
      }
    });

    document.getElementById("createTicketBtn").addEventListener("click", async () => {
      try {
        await createTicket();
      } catch (err) {
        document.getElementById("ticketMsg").textContent = err.message || "提交失败";
      }
    });

    document.getElementById("queryTicketBtn").addEventListener("click", async () => {
      try {
        await queryTicket();
      } catch (err) {
        document.getElementById("ticketMsg").textContent = err.message || "查询失败";
      }
    });

    document.getElementById("qaHandoffBtn").addEventListener("click", async () => {
      try {
        await handoffFromQA();
      } catch (err) {
        appendChat("ai", `转人工失败：${err.message || "未知错误"}`);
      }
    });

  }

  async function bootstrap() {
    await checkAuth();
    bindEvents();
  }

  bootstrap().catch(() => {
    localStorage.removeItem("hqt_token");
    localStorage.removeItem("hqt_user");
    window.location.href = "/static/login.html";
  });
})();
