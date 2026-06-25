# 云程智绘图（Cloud Trip Agent）

云程智绘图是一个面向国内旅行场景的智能行程规划系统。项目以 Vue 3 + TypeScript 前端、FastAPI 后端、SQLite、Redis、ChromaDB、本地攻略数据、高德地图、天气服务、Tavily 受限检索和 LangGraph 风格多 Agent 编排为核心，提供从旅行需求填写、候选行程生成、自然语言修改、版本管理、长期记忆到 PDF 导出的完整作品展示链路。

本项目是求职作品展示项目，不提供自动预订、自动支付、第三方网站登录、携程实时网页查询、12306 查询或多平台实时比价能力。

## 功能概览

- 用户名和密码注册登录，JWT 鉴权，密码哈希存储。
- 国内旅行需求填写：出发地、目的地、日期、人数、预算、偏好等。
- 默认生成两个候选方案：经济优先、均衡推荐；可扩展体验优先方案。
- 行程内容包含交通、住宿、景点、门票参考、餐饮、天气、地图路线和预算拆分。
- 高德地图增强：POI、地址、经纬度、路线距离、预计耗时。
- 天气查询与旅行提示。
- 本地攻略 RAG 检索，ChromaDB 持久化。
- Tavily 受限搜索工具，用于景点、餐饮、开放时间、公开攻略、旅行提示和临时注意事项。
- 统一数据来源标记：`demo`、`estimate`、`user_input`、`tavily`、`official_api`。
- 自然语言修改行程。
- 拖拽调整每日行程顺序。
- 行程保存、历史列表、详情查看、删除。
- 行程版本管理：查看、对比、恢复，恢复旧版本会生成新版本。
- 长期记忆：开关、查看、删除单条、清空全部。
- AI 旅行顾问多轮对话，围绕当前行程解释、查询、修改和确认操作。
- Agent 执行状态展示，不展示内部思维链。
- Markdown 和 PDF 导出。
- Docker Compose 本地运行：frontend、backend、redis。

## 不支持范围

第一版明确不支持：

- 自动预订型 Browser 自动化。
- Playwright 登录、下单、支付或绕过验证码。
- 携程实时库存、最终结算价或可预订结果查询。
- 第三方网站自动登录。
- 自动预订。
- 自动支付。
- 自动退票、改签和取消。
- 自驾路线规划。
- 12306 查询。
- 多平台实时比价。
- 多人协作。
- 管理员后台。
- 手机 App。
- 公网生产部署。

## 数据来源规则

航班、高铁、酒店、门票、景点、餐饮、天气和路线数据都应标记来源：

| 来源类型 | 说明 |
| --- | --- |
| `demo` | 本地演示数据 |
| `estimate` | 规则估算 |
| `user_input` | 用户录入 |
| `tavily` | Tavily 外部检索 |
| `official_api` | 正式 API |
| `browser_observed` | Browser 页面可见文本观察 |

注意：

- 本地演示数据、规则估算和 Tavily 摘要不能描述为实时价格、实时库存或可预订结果。
- Browser 页面观察只代表当前打开页面中的可见价格文本，不代表实时库存、可预订结果或最终结算价。
- Tavily 结果属于外部检索信息，写入行程前需要字段校验、去重和来源标记。
- 预算、版本号、权限、日期和状态机等关键逻辑由确定性 Python 代码处理，不交给大模型自由计算。

## 技术栈

| 模块 | 技术 |
| --- | --- |
| 前端 | Vue 3、TypeScript、Vite、Vue Router、Pinia、Ant Design Vue、Element Plus |
| 后端 | Python、FastAPI、Pydantic、SQLAlchemy |
| 数据库 | SQLite |
| 缓存 | Redis |
| 向量库 | ChromaDB |
| Agent 编排 | LangGraph 风格工作流 |
| 外部工具 | 高德地图、天气服务、Tavily 受限搜索 |
| 导出 | Markdown、ReportLab PDF |
| 部署 | Docker Compose、Nginx |

## 系统结构

```text
Vue 3 前端
  -> Nginx
  -> FastAPI
  -> 认证与业务 API
  -> LangGraph 风格工作流
  -> 专业 Agent
  -> 白名单工具层
  -> 高德 / 天气 / Tavily / RAG / 本地演示数据
  -> SQLite / Redis / ChromaDB
```

核心后端分层：

- `backend/app/api/routes/`：HTTP API 路由。
- `backend/app/api/dependencies.py`：认证依赖、当前用户解析。
- `backend/app/core/security.py`：密码哈希、JWT 创建与校验。
- `backend/app/models/`：Pydantic Schema 与 SQLAlchemy 模型。
- `backend/app/services/`：认证、行程、存储、版本、记忆、确认、AI 顾问、导出等业务服务。
- `backend/app/agents/`：行程生成 Agent 与工作流实现。
- `backend/app/agents/tools/`：受限工具，例如 Tavily 搜索工具。
- `backend/app/rag/`：ChromaDB、本地攻略检索和 rerank。
- `backend/data/`：本地攻略 Markdown 数据。
- `backend/tests/`：后端自动化测试。

核心前端分层：

- `frontend/src/router/`：路由。
- `frontend/src/stores/`：Pinia 状态，包括认证和 AI 顾问对话。
- `frontend/src/services/`：API 请求封装与 JWT 注入。
- `frontend/src/views/`：登录、注册、新建行程、结果、历史、长期记忆等页面。
- `frontend/src/components/`：地图、AI 顾问面板、聊天消息、确认卡片等组件。
- `frontend/src/types/`：TypeScript 类型定义。

## 主要业务流程

```text
注册登录
  -> 填写旅行表单
  -> 读取长期偏好
  -> 结构化旅行需求
  -> 生成任务计划
  -> 多 Agent 执行
  -> 高德、天气、RAG、Tavily 和本地数据查询
  -> 生成 2 至 3 个候选行程
  -> 校验预算、路线、时间和来源
  -> 用户选择或修改
  -> 保存版本
  -> AI 顾问解释、查询或局部修改
  -> 导出 Markdown / PDF
```

## AI 顾问能力

AI 旅行顾问围绕当前行程工作，不是通用聊天机器人。

支持意图：

- `modify_trip`：按用户要求局部修改当前行程，并生成新版本。
- `explain_plan`：解释当前方案安排逻辑。
- `query_trip`：查询当前行程预算、酒店、日期、来源等确定信息。
- `confirm_action`：确认恢复版本、保存长期偏好等高影响操作。
- `cancel_action`：取消待确认操作。
- `general_travel_question`：回答受限旅行问题，可使用 Tavily 或本地 RAG。
- `unsupported`：拒绝预订、支付、第三方登录等不支持事项。

AI 顾问不会获得 Shell、PowerShell、subprocess、eval、exec、任意文件读写、任意 URL 访问或 Docker API 权限。

## 环境变量

不要提交 `.env`、API Key、密码、Token、SQLite 运行数据、Chroma 运行数据或导出的 PDF。

### 后端

复制后端环境模板：

```bash
cp backend/.env.example backend/.env
```

关键变量：

```env
LLM_PROVIDER=openai_compatible
LLM_API_KEY=your_api_key_here
LLM_MODEL=qwen-max
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

JWT_SECRET_KEY=change_me_to_a_long_random_secret
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60

CHROMA_DB_DIR=db/chroma_db
CHROMA_COLLECTION_NAME=travel_guides
EMBEDDING_MODEL=text-embedding-v4
RERANK_MODEL=qwen3-rerank

REDIS_ENABLED=false
REDIS_URL=redis://127.0.0.1:6379/0

AMAP_API_KEY=your_amap_api_key
AMAP_BASE_URL=https://restapi.amap.com/v3
ENABLE_AMAP_ENRICHMENT=false

TAVILY_API_KEY=
TAVILY_API_URL=https://api.tavily.com/search
```

说明：

- `LLM_API_KEY`、`AMAP_API_KEY`、`TAVILY_API_KEY` 只能写入本地 `backend/.env`。
- `TAVILY_API_KEY` 可留空，系统会回退到高德、本地 RAG 或演示数据。
- `JWT_SECRET_KEY` 在正式使用时应替换为足够长的随机值。
- 不要把真实密钥写入 README、日志、前端代码或模型上下文。

### 前端

复制前端环境模板：

```bash
cp frontend/.env.example frontend/.env
```

关键变量：

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_AMAP_JS_KEY=
```

Docker 默认通过 Nginx 代理 API，通常不需要额外配置前端 API 地址。

## Docker 运行

首次运行：

```bash
docker compose up -d --build
```

查看状态：

```bash
docker compose ps
```

查看日志：

```bash
docker compose logs --tail=100 backend
docker compose logs --tail=100 frontend
docker compose logs --tail=100 redis
```

访问地址：

```text
前端：http://localhost
后端健康检查：http://localhost:8000/health
后端接口文档：http://localhost:8000/docs
```

停止服务：

```bash
docker compose stop
```

不要随意执行 `docker compose down -v`，该命令会删除数据卷。

## 本地开发

### 后端

```bash
cd backend
python -m pip install -r requirements.txt
python -m uvicorn app.api.main:app --reload --host 0.0.0.0 --port 8000
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

前端本地开发地址通常是：

```text
http://localhost:5173
```

## RAG 数据初始化

本地攻略文件位于：

```text
backend/data/
```

初始化 ChromaDB：

```bash
cd backend
python scripts/ingest_data.py
```

Docker 场景下，SQLite 与 ChromaDB 持久化在后端数据库卷中；镜像内攻略文件保留在 `/app/data`，不会被 `backend_data:/app/data` 遮挡。

## Browser 价格观察

Browser 价格观察默认关闭。启用后，用户可在新建行程页填写起始城市、目的地和出行日期，后端会使用 Playwright 自动打开携程火车、机票、度假和首页入口，尝试填入城市日期并点击搜索，再读取当前页面可见文本并抽取价格。用户也可以额外填写公开网页 URL 作为补充观察来源。结果会以 `browser_observed` 来源写入行程来源记录，并在可识别时回填酒店、交通或门票的参考价格。

`backend/.env` 示例：

```env
BROWSER_ENABLED=true
BROWSER_HEADLESS=true
BROWSER_ALLOWED_DOMAINS=*
BROWSER_TIMEOUT_SECONDS=30
BROWSER_MAX_URLS=4
BROWSER_MAX_PRICE_ITEMS=8
BROWSER_HUMAN_WAIT_SECONDS=60
```

边界说明：该能力不自动登录第三方网站、不绕过验证码、不点击预订或支付；页面观察价格不代表实时库存、可预订结果或最终结算价。本地调试时可设置 `BROWSER_HEADLESS=false`，遇到登录或验证码时浏览器窗口会等待 `BROWSER_HUMAN_WAIT_SECONDS`，由用户手动处理后继续读取页面；Docker 默认 headless，只会返回需要人工处理的状态并保留估算价格。

## 核心 API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/health` | 健康检查 |
| `POST` | `/auth/register` | 用户注册 |
| `POST` | `/auth/login` | 用户登录 |
| `GET` | `/auth/me` | 当前用户 |
| `POST` | `/trip/generate` | 生成行程 |
| `POST` | `/trip/edit` | 自然语言修改行程 |
| `POST` | `/trip/save` | 保存行程并生成版本 |
| `GET` | `/trip` | 历史行程列表 |
| `GET` | `/trip/{trip_id}` | 行程详情 |
| `DELETE` | `/trip/{trip_id}` | 删除行程 |
| `GET` | `/trip/{trip_id}/versions` | 版本列表 |
| `GET` | `/trip/{trip_id}/versions/{version_number}` | 版本详情 |
| `GET` | `/trip/{trip_id}/versions/compare` | 对比版本 |
| `POST` | `/trip/{trip_id}/versions/{version_number}/restore` | 恢复版本 |
| `GET` | `/memory` | 查看长期记忆 |
| `PATCH` | `/memory/settings` | 开关长期记忆 |
| `DELETE` | `/memory/{memory_id}` | 删除单条记忆 |
| `DELETE` | `/memory` | 清空记忆 |
| `POST` | `/assistant/message` | AI 顾问多轮对话 |
| `GET` | `/assistant/trips/{trip_id}/messages` | 查询当前行程对话历史 |
| `DELETE` | `/assistant/trips/{trip_id}/messages` | 清空当前行程对话 |
| `GET` | `/weather/forecast` | 天气查询 |
| `GET` | `/export/{trip_id}/markdown` | 导出 Markdown |
| `GET` | `/export/{trip_id}/pdf` | 导出 PDF |

## 测试

后端测试：

```bash
cd backend
python -m pytest tests -q
```

前端构建：

```bash
cd frontend
npm run build
```

空白检查：

```bash
git diff --check
```

## 页面说明

- 登录注册页：用户名和密码注册登录。
- 工作台 / 新建行程页：填写旅行需求并生成候选行程。
- 当前结果页：展示旅行计划、预算、地图、天气、候选方案、每日行程和 AI 顾问。
- 数据来源页：单独展示当前行程的数据来源记录。
- Agent 状态页：单独展示当前行程相关 Agent 与工具执行状态。
- 历史行程页：查看和打开已保存行程。
- 版本管理：查看、对比、恢复行程版本。
- 长期记忆管理页：开关、查看和删除用户偏好。

## 安全与隐私

- 密码必须哈希存储，不保存明文密码。
- JWT 密钥只从环境变量读取；本地未配置时可使用进程临时密钥，但不会输出密钥内容。
- 前端不得传入 `user_id` 作为可信身份，后端从 JWT 解析当前用户。
- 行程、版本、记忆和对话记录都绑定当前用户。
- 日志不得输出密码、密码哈希、完整 JWT、API Key 或 Token。
- Agent 只能调用白名单工具，不允许任意执行系统命令或访问任意网址。
- `.env`、数据库、Chroma 运行数据、导出文件和依赖目录均应保持未提交状态。

## 推荐演示流程

1. 启动 Docker 服务。
2. 打开 `http://localhost`。
3. 注册并登录。
4. 创建国内旅行需求。
5. 生成 2 个候选方案。
6. 查看当前结果、数据来源和 Agent 状态。
7. 使用 AI 顾问提问，例如“解释一下这个行程为什么这样安排”。
8. 让 AI 顾问进行局部修改，例如“第二天安排得轻松一点”。
9. 保存行程并查看版本。
10. 打开长期记忆，确认保存一条稳定偏好。
11. 导出 Markdown 或 PDF。

## 许可证

本项目用于学习、作品展示和技术交流。若接入第三方 API，请遵守对应服务条款，并妥善保管密钥。
