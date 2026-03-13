# 惠企通企业端 MVP

企业端闭环：登录 -> 企业信息维护 -> 政策匹配 -> AI问答 -> 转人工工单。

## 1. 本地启动（SQLite 快速模式）
```bash
DATABASE_URL=sqlite:///./test.db python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

打开：
- 登录页: `http://127.0.0.1:8000/`
- 工作台: `http://127.0.0.1:8000/app`
- API 文档: `http://127.0.0.1:8000/docs`

默认登录账号（开发环境）：
- 用户名：`enterprise`
- 密码：`123456`

## 2. 本地启动（Docker + PostgreSQL）
```bash
COMPOSE_PROJECT_NAME=hqt docker compose up --build
```

## 3. GLM 配置（不使用 OpenAI）
在 `.env` 中配置：
```env
LLM_PROVIDER=glm
LLM_API_KEY=你的GLM_API_Key
LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4
LLM_MODEL=glm-4-flash
LLM_TIMEOUT_SECONDS=30
```
说明：
1. 项目已按 GLM 的 OpenAI 兼容 Chat Completions 接口接入。
2. 若未配置 `LLM_API_KEY`，系统会自动回退本地规则回答，不影响流程联调。
3. 不要把真实密钥写进 `.env.example` 或提交到仓库。

## 4. 运行测试
```bash
pytest
```

## 5. Render 试用版部署
这个仓库已经补齐了 `render.yaml` 和多阶段 `Dockerfile`，可以直接作为 Render Web Service 部署。

说明：
1. 试用版默认使用 `sqlite:///./data/hqt.db`，不依赖额外数据库服务。
2. 这适合快速体验流程，但免费实例重建或重新部署后，本地数据可能会丢失。
3. 如果需要长期稳定存储，再把 `DATABASE_URL` 改成外部 PostgreSQL 即可。
4. 若不配置 `LLM_API_KEY`，系统会自动回退本地规则回答，不影响基本试用。

本地先检查前端产物：
```bash
cd frontend && npm ci && npm run build
```

部署到 Render：
1. 把仓库推到 GitHub。
2. 在 Render 里选择 `New +` -> `Blueprint`。
3. 选择这个仓库，Render 会读取根目录下的 `render.yaml`。
4. 等待镜像构建完成后，访问 Render 分配的域名即可。

## 6. 当前实现说明
1. UI 已拆分为登录页 + 多视图工作台，不再是单一页面。
2. 业务接口默认要求登录态（Bearer token）。
3. 登录支持默认账号密码；短信通道仍保留 mock 接口。
4. 工单状态流转校验：`pending -> processing -> resolved -> closed`。
5. AI 问答具备 guardrails：高风险问题拒绝确定性结论、连续证据不足触发转人工；配置 GLM Key 后可调用大模型增强回答。
6. 政策数据当前为内置样例，后续可扩展采集与审核发布流程。
