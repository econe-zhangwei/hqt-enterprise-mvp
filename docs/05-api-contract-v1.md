# 05 API Contract V1 - 接口契约（SSOT）

## 目的
定义企业端 MVP 前后端接口契约，作为联调唯一真相源（SSOT）。

## 适用范围
适用于企业端 Web H5 与后端服务之间的 V1 接口。

## 定义与术语
- SSOT：接口定义唯一有效来源。
- taskId：异步匹配任务标识。
- ticketId：工单唯一标识。
- authToken：登录态凭证。

## 主内容
### 1. 通用约定
1. Base URL：`/api/v1`
2. Content-Type：`application/json`
3. 时间格式：ISO8601
4. 分页参数：`page`、`page_size`
5. 鉴权：除健康检查与登录接口外，其余业务接口均需 `Authorization: Bearer <token>`

### 2. 错误码
| code | 含义 |
|---|---|
| 0 | 成功 |
| 40001 | 参数错误 |
| 40101 | 未登录或鉴权失败 |
| 40401 | 资源不存在 |
| 42901 | 请求过于频繁 |
| 50001 | 系统内部错误 |

### 3. 接口清单
#### 3.1 创建/更新企业画像
- `POST /enterprise-profiles`
- 请求：
```json
{
  "enterprise_name": "上海某科技有限公司",
  "uscc": "9131XXXXXXXXXXXXXX",
  "region_code": "SH-PD",
  "industry_code": "C39",
  "contact_name": "张三",
  "contact_mobile": "13800138000"
}
```
- 响应：
```json
{
  "code": 0,
  "data": { "enterprise_id": "ent_001" }
}
```

#### 3.2 创建匹配任务
- `POST /policy-matches`
- 请求：
```json
{ "enterprise_id": "ent_001" }
```
- 响应：
```json
{
  "code": 0,
  "data": { "task_id": "task_001", "status": "processing" }
}
```

#### 3.3 查询匹配结果
- `GET /policy-matches/{taskId}`
- 响应：
```json
{
  "code": 0,
  "data": {
    "status": "done",
    "summary": { "eligible_count": 2, "potential_count": 3 },
    "results": [
      {
        "policy_id": "SH-2026-0001",
        "eligibility": "eligible",
        "score": 88,
        "reasons": ["满足研发投入占比条件"],
        "missing_items": []
      }
    ]
  }
}
```

#### 3.4 获取政策详情
- `GET /policies/{policyId}`

#### 3.5 AI 问答
- `POST /qa/policy`
- 请求：
```json
{
  "enterprise_id": "ent_001",
  "question": "这条政策为什么不符合？",
  "context_policy_id": "SH-2026-0001"
}
```
- 响应：
```json
{
  "code": 0,
  "data": {
    "answer": "当前未识别到高新技术企业资质。",
    "citations": [
      { "title": "示例政策", "url": "https://example.gov.cn/policy/1" }
    ],
    "recommend_handoff": true,
    "confidence": 0.71,
    "risk_flags": ["insufficient_context"],
    "handoff_reason": "连续两次证据不足，建议转人工处理",
    "next_actions": ["先补充企业信息并执行政策匹配", "点击“一键转人工”生成顾问工单"],
    "evidence_snippets": ["政策：示例政策（city/SH-PD）"]
  }
}
```

#### 3.5.1 AI 一键转人工
- `POST /qa/handoff-ticket`
- 请求：
```json
{
  "enterprise_id": "ent_001",
  "question": "这条政策我还缺什么？",
  "answer": "当前主要缺口是高新技术企业资质。",
  "context_policy_id": "SH-2026-0001",
  "handoff_reason": "涉及缺口补齐细节，建议人工逐项确认"
}
```
- 响应：
```json
{
  "code": 0,
  "data": {
    "ticket_id": "ticket_001",
    "status": "pending",
    "issue_type": "qa_handoff",
    "contact_mobile": "13800138000"
  }
}
```

#### 3.5.2 政策知识库导入
- `POST /knowledge-base/import`
- 请求：
```json
{
  "source_type": "raw_text",
  "source_uri": "manual://policy-note-1",
  "title": "算力补贴政策摘要",
  "raw_text": "上海人工智能算力补贴通常围绕智算服务、算力券和模型训练资源采购展开。"
}
```
- 响应：
```json
{
  "code": 0,
  "data": {
    "id": "doc_001",
    "policy_id": null,
    "title": "算力补贴政策摘要",
    "source_type": "raw_text",
    "source_uri": "manual://policy-note-1",
    "source_domain": null,
    "ingest_status": "ready",
    "chunk_count": 2
  }
}
```

#### 3.5.3 政策知识库检索
- `POST /knowledge-base/search`
- 请求：
```json
{
  "query": "算力补贴 智算中心",
  "limit": 3
}
```
- 响应：
```json
{
  "code": 0,
  "data": [
    {
      "document_id": "doc_001",
      "policy_id": null,
      "title": "算力补贴政策摘要",
      "source_uri": "manual://policy-note-1",
      "source_type": "raw_text",
      "chunk_id": "chunk_001",
      "chunk_index": 0,
      "content": "上海人工智能算力补贴通常围绕智算服务、算力券和模型训练资源采购展开。",
      "score": 32
    }
  ]
}
```

#### 3.5.4 政策知识库文档列表
- `GET /knowledge-base/documents`
- Query：`page`、`page_size`

#### 3.5.5 政策知识库文档预览
- `GET /knowledge-base/documents/{documentId}/preview`
- 用途：打开网页/PDF 导入后的正文预览页，供前端“原文/资料解析”链接直接跳转查看。

#### 3.6 创建工单
- `POST /service-tickets`
- 请求：
```json
{
  "enterprise_id": "ent_001",
  "issue_type": "eligibility_consult",
  "description": "希望确认可争取政策的补充材料",
  "contact_mobile": "13800138000"
}
```

#### 3.7 查询工单
- `GET /service-tickets/{ticketId}`

#### 3.8 登录相关
- `POST /auth/password/login`（默认账号密码登录）
- `POST /auth/sms/send`（保留 mock）
- `POST /auth/sms/login`（保留 mock）
- `GET /auth/me`（校验当前 token）

### 4. 前后端责任边界
1. 前端：仅按本契约发起请求和解析响应。
2. 后端：保证返回结构稳定，新增字段不破坏兼容。
3. 变更流程：接口变更需先改本文件，再改实现。

## 验收标准
1. 联调过程以本文件为唯一依据，无口头字段。
2. 接口请求/响应示例可直接用于 mock。
3. 错误码覆盖常见异常场景。
4. 版本发布前已完成契约一致性校对。

## 变更记录
| 日期 | 版本 | 变更内容 | 变更人 |
|---|---|---|---|
| 2026-03-06 | v1.1 | 新增政策知识库导入、检索与文档列表接口 | Codex |
| 2026-03-04 | v1.0 | 首次创建 V1 接口契约 | Codex |
