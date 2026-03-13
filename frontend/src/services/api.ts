export interface LoginSession {
  token: string;
  token_type: string;
  expires_at: string;
  subject: string;
  login_type: string;
}

export interface EnterpriseProfilePayload {
  enterprise_name: string;
  uscc: string;
  region_code: string;
  industry_code: string;
  contact_name: string;
  contact_mobile: string;
  employee_scale: string;
  revenue_range: string;
  rd_ratio: number;
  ip_count: number;
  qualification_tags: string[];
}

export interface EnterpriseProfileData extends EnterpriseProfilePayload {
  id: string;
}

export interface MatchResult {
  policy_id: string;
  policy_title: string;
  source_url: string;
  eligibility: 'eligible' | 'potential' | string;
  score: number;
  reasons: string[];
  missing_items: string[];
  next_action: string;
}

export interface MatchSummary {
  eligible_count: number;
  potential_count: number;
}

export interface MatchData {
  status?: string;
  summary: MatchSummary;
  results: MatchResult[];
}

export interface PolicyDetail {
  id?: string;
  title: string;
  region_code: string;
  level: string;
  source_url: string;
  effective_from: string;
  effective_to: string | null;
  required_materials: string[];
  support_type: string | null;
  updated_at: string | null;
  outline_sections: Array<{ title: string; items: string[] }>;
}

export interface QAResponse {
  answer: string;
  recommend_handoff: boolean;
  confidence: number;
  risk_flags: string[];
  handoff_reason: string | null;
  next_actions: string[];
  evidence_snippets: string[];
  intent: string | null;
  selected_policy_id: string | null;
  selected_policy_title: string | null;
  clarification_needed: boolean;
}

export interface TicketData {
  ticket_id?: string;
  id?: string;
  status: string;
  logs: Array<{ at?: string; message: string }>;
}

interface ApiEnvelope<T> {
  code: number;
  message: string;
  data: T;
}

class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

const API_BASE = '/api/v1';

function getToken() {
  return localStorage.getItem('hqt_token') || '';
}

async function request<T>(path: string, init: RequestInit = {}, auth = true): Promise<T> {
  const headers = new Headers(init.headers || {});
  const isForm = init.body instanceof FormData;

  if (!isForm && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  if (auth) {
    const token = getToken();
    if (token) {
      headers.set('Authorization', `Bearer ${token}`);
    }
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
  });

  const payload = (await response.json().catch(() => null)) as ApiEnvelope<T> | { detail?: string } | null;

  if (!response.ok) {
    const message =
      (payload && 'detail' in payload && payload.detail) ||
      (payload && 'message' in payload && payload.message) ||
      '请求失败';
    throw new ApiError(message, response.status);
  }

  if (!payload || !('data' in payload)) {
    throw new ApiError('响应格式错误', response.status);
  }

  return payload.data;
}

export { ApiError };

export const api = {
  login(username: string, password: string) {
    return request<LoginSession>(
      '/auth/password/login',
      {
        method: 'POST',
        body: JSON.stringify({ username, password }),
      },
      false,
    );
  },

  getMe() {
    return request<{ subject: string; login_type: string }>('/auth/me');
  },

  saveProfile(data: EnterpriseProfilePayload) {
    return request<{ enterprise_id: string }>('/enterprise-profiles', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  getEnterpriseProfile(enterpriseId: string) {
    return request<EnterpriseProfileData>(`/enterprise-profiles/${enterpriseId}`);
  },

  runMatch(enterpriseId: string) {
    return request<{ task_id: string; status: string }>('/policy-matches', {
      method: 'POST',
      body: JSON.stringify({ enterprise_id: enterpriseId }),
    });
  },

  getMatchResults(taskId: string) {
    return request<MatchData>(`/policy-matches/${taskId}?view=full`);
  },

  getPolicyDetail(policyId: string) {
    return request<PolicyDetail>(`/policies/${policyId}`);
  },

  askAI(payload: { enterprise_id: string; question: string; context_policy_id: string | null }) {
    return request<QAResponse>('/qa/policy', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  handoffTicket(payload: {
    enterprise_id: string;
    question: string;
    answer: string;
    context_policy_id: string | null;
    handoff_reason: string | null;
    callback_time?: string | null;
  }) {
    return request<{ ticket_id: string; status: string }>('/qa/handoff-ticket', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  createTicket(payload: {
    enterprise_id: string;
    issue_type: string;
    description: string;
    contact_mobile: string;
    callback_time?: string | null;
  }) {
    return request<{ ticket_id: string; status: string }>('/service-tickets', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  queryTicket(ticketId: string) {
    return request<TicketData>(`/service-tickets/${ticketId}`);
  },
};
