# 云程智绘图（Cloud Trip Agent）

云程智绘图是一个面向国内旅行场景的智能行程规划系统。项目以 Vue 3 + TypeScript 前端、FastAPI 后端、SQLite、Redis、ChromaDB、本地攻略数据、高德地图、天气服务、Tavily 受限检索、LangGraph 风格多 Agent 编排和 LLM 多 Agent 委派对话为核心，提供从旅行需求填写、候选行程生成、自然语言修改、版本管理、长期记忆到 PDF 导出的完整展示链路。


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

```bash
# 后端
cd backend
python -m pip install -r requirements.txt
python -m uvicorn app.api.main:app --reload --host 0.0.0.0 --port 8000

# 前端
cd frontend
npm install
npm run dev
```

前端本地开发地址通常是 `http://localhost:5173`。

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

## Edge 浏览器辅助浏览

在结果页点击航班、高铁、酒店或度假按钮，后端会启动本地 MS Edge 浏览器并导航到携程对应页面，自动传入目的地和日期参数。浏览器作为独立进程运行，不受后端生命周期影响，用户手动查看价格后自行关闭窗口。

- 浏览器窗口由用户手动关闭。
- 不做自动抓取、不提取 DOM 价格、不自动登录。
- 价格请以页面实际显示为准，仅供出行参考。

`backend/.env` 可选配置：

```env
BROWSER_CHANNEL=msedge
MSEDGE_PATH=C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe
BROWSER_TIMEOUT_SECONDS=30
```


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


## 推荐演示流程

1. 启动前后端服务（Docker 或本地开发）。
2. 打开前端页面，注册并登录。
3. 创建国内旅行需求，填写目的地、日期、预算等。
4. 生成行程，查看预算明细、景点地图、天气信息。
5. 使用 AI 顾问进行多轮对话：查询预算、解释方案、修改行程。
6. 切换候选方案（经济优先 / 均衡推荐）。
7. 点击 Edge 辅助浏览按钮，查看携程实时参考价格。
8. 保存行程，查看版本历史。
9. 恢复历史版本，确认数据正确。
10. 导出 Markdown 或 PDF。

