# 云程智绘图 V1.0 迁移盘点清单

## 0. 边界说明

- 正式项目唯一来源：`cloud-trip-agent`。
- 参考项目只读来源：`agent-ctrip-reference`。
- `agent-ctrip-reference` 只能作为 JWT、LangGraph、多 Agent 编排和人工确认机制的参考，不允许整体复制到 `cloud-trip-agent`。
- 本清单中的迁移含义均为在 `cloud-trip-agent` 内重新设计或小步实现；除明确说明外，不代表直接复制参考项目代码。

## 1. 两个项目现状对比

### 1.1 正式项目 cloud-trip-agent

前端结构：

- 前端入口是 `cloud-trip-agent/frontend/src/main.ts`，创建 Vue 应用并挂载 `cloud-trip-agent/frontend/src/App.vue`。
- 页面由 `cloud-trip-agent/frontend/src/App.vue` 使用本地状态在 `cloud-trip-agent/frontend/src/views/Home.vue`、`cloud-trip-agent/frontend/src/views/Result.vue`、`cloud-trip-agent/frontend/src/views/History.vue` 之间切换。
- API 封装集中在 `cloud-trip-agent/frontend/src/services/api.ts`，当前调用 `/trip/generate`、`/trip/edit`、`/trip/save`、`/trip`、`/weather/forecast`、`/export/*`。
- 类型定义集中在 `cloud-trip-agent/frontend/src/types/index.ts`。
- 地图展示组件是 `cloud-trip-agent/frontend/src/components/AmapTripMap.vue`。
- 前端构建入口和依赖声明在 `cloud-trip-agent/frontend/package.json`，容器入口在 `cloud-trip-agent/frontend/Dockerfile` 和 `cloud-trip-agent/frontend/nginx.conf`。

后端结构：

- FastAPI 入口是 `cloud-trip-agent/backend/app/api/main.py`，创建 `app` 并挂载 trip、weather、export 路由。
- 行程 API 在 `cloud-trip-agent/backend/app/api/routes/trip.py`。
- 天气 API 在 `cloud-trip-agent/backend/app/api/routes/weather.py`。
- 导出 API 在 `cloud-trip-agent/backend/app/api/routes/export.py`。
- 核心行程生成服务在 `cloud-trip-agent/backend/app/services/trip_service.py`。
- 行程持久化服务在 `cloud-trip-agent/backend/app/services/storage_service.py`。
- 地图服务在 `cloud-trip-agent/backend/app/services/map_service.py`。
- 天气服务在 `cloud-trip-agent/backend/app/services/weather_service.py`。
- PDF/导出服务在 `cloud-trip-agent/backend/app/services/export_service.py`。
- Redis 缓存封装在 `cloud-trip-agent/backend/app/services/cache_service.py`。

数据库结构：

- 数据库配置在 `cloud-trip-agent/backend/app/config.py`，当前使用 SQLite 文件 `cloud-trip-agent/backend/db/app.db`。
- SQLAlchemy 模型在 `cloud-trip-agent/backend/app/models/db_models.py`，当前核心表为 `TripRecord`。
- Pydantic 请求/响应模型在 `cloud-trip-agent/backend/app/models/schemas.py`。
- 数据库表初始化由 `cloud-trip-agent/backend/app/services/storage_service.py` 内部触发。
- 当前没有用户表、JWT 会话表、长期记忆表、行程版本表或 Agent 执行记录表。

Agent、RAG 和工具结构：

- 当前行程规划 Agent 在 `cloud-trip-agent/backend/app/agents/trip_planner_agent.py`，属于 LangChain 风格单 Agent，不是 LangGraph 状态机。
- RAG 工具入口在 `cloud-trip-agent/backend/app/agents/tools/rag_tool.py`。
- 向量库封装在 `cloud-trip-agent/backend/app/rag/vector_db.py`。
- 检索封装在 `cloud-trip-agent/backend/app/rag/retriever.py`。
- 当前没有 Supervisor Agent、Requirement Agent、Planner Agent、Transport Agent、Hotel Agent、POI Agent、Ticket Agent、Food Agent、Verification Agent、Replanner Agent 的独立文件。

启动入口：

- Docker 编排入口是 `cloud-trip-agent/docker-compose.yaml`。
- 后端镜像定义在 `cloud-trip-agent/backend/Dockerfile`。
- 前端镜像定义在 `cloud-trip-agent/frontend/Dockerfile`。
- 本地后端入口由 `cloud-trip-agent/backend/app/api/main.py` 提供。
- 本地前端入口由 `cloud-trip-agent/frontend/package.json` 中的 Vite 脚本提供。

### 1.2 参考项目 agent-ctrip-reference

前端结构：

- 前端入口是 `agent-ctrip-reference/ctrip_assistant_fronted/src/main.ts`。
- 路由定义在 `agent-ctrip-reference/ctrip_assistant_fronted/src/router/index.ts`。
- 登录页在 `agent-ctrip-reference/ctrip_assistant_fronted/src/views/auth/LoginView.vue`。
- 注册页在 `agent-ctrip-reference/ctrip_assistant_fronted/src/views/auth/RegisterView.vue`。
- 认证状态在 `agent-ctrip-reference/ctrip_assistant_fronted/src/stores/auth.ts`。
- 聊天和人工确认状态在 `agent-ctrip-reference/ctrip_assistant_fronted/src/stores/chat.ts`。
- HTTP 拦截器在 `agent-ctrip-reference/ctrip_assistant_fronted/src/services/http.ts`。
- 登录注册请求封装在 `agent-ctrip-reference/ctrip_assistant_fronted/src/services/auth.ts`。
- Graph 请求封装在 `agent-ctrip-reference/ctrip_assistant_fronted/src/services/graph.ts`。
- 人工确认 UI 在 `agent-ctrip-reference/ctrip_assistant_fronted/src/components/assistant/ActionConfirmCard.vue`。
- 确认文本识别在 `agent-ctrip-reference/ctrip_assistant_fronted/src/utils/graphTextParser.ts`。

后端结构：

- FastAPI 入口是 `agent-ctrip-reference/ctrip_assistant_backend/main.py`，通过 `Server` 类初始化应用、路由、中间件和静态目录。
- 路由聚合在 `agent-ctrip-reference/ctrip_assistant_backend/api/routers.py`。
- 用户认证路由在 `agent-ctrip-reference/ctrip_assistant_backend/api/system_mgt/user_views.py`。
- 用户认证 Schema 在 `agent-ctrip-reference/ctrip_assistant_backend/api/system_mgt/user_schemas.py`。
- Graph 对话路由在 `agent-ctrip-reference/ctrip_assistant_backend/api/graph_api/graph_views.py`。
- Graph 请求/响应 Schema 在 `agent-ctrip-reference/ctrip_assistant_backend/api/graph_api/graph_schemas.py`。

数据库结构：

- 数据库连接和 `DBModelBase` 在 `agent-ctrip-reference/ctrip_assistant_backend/db/__init__.py`。
- 用户模型在 `agent-ctrip-reference/ctrip_assistant_backend/db/system_mgt/models.py`。
- 用户 DAO 在 `agent-ctrip-reference/ctrip_assistant_backend/db/system_mgt/user_dao.py`。
- 参考项目同时存在旅行示例数据库初始化逻辑，位置包括 `agent-ctrip-reference/ctrip_assistant_backend/tools/init_db.py` 和 `agent-ctrip-reference/ctrip_assistant_backend/graph_chat/finally_graph.py`。

JWT 注册登录相关文件：

- `agent-ctrip-reference/ctrip_assistant_backend/api/system_mgt/user_views.py` 实现 `/register/`、`/login/`、`/auth/` 等接口。
- `agent-ctrip-reference/ctrip_assistant_backend/api/system_mgt/user_schemas.py` 定义登录注册请求和响应模型。
- `agent-ctrip-reference/ctrip_assistant_backend/utils/password_hash.py` 使用 passlib bcrypt 做密码哈希和校验。
- `agent-ctrip-reference/ctrip_assistant_backend/utils/jwt_utils.py` 创建和校验 JWT。
- `agent-ctrip-reference/ctrip_assistant_backend/utils/middlewares.py` 校验请求头 `Authorization` 并写入 `request.state.username`。
- `agent-ctrip-reference/ctrip_assistant_backend/utils/docs_oauth2.py` 为 Swagger OAuth2 登录提供依赖。
- `agent-ctrip-reference/ctrip_assistant_backend/utils/dependencies.py` 提供数据库 Session 依赖。
- 前端登录注册调用在 `agent-ctrip-reference/ctrip_assistant_fronted/src/services/auth.ts`。
- 前端 token 存储和登录状态在 `agent-ctrip-reference/ctrip_assistant_fronted/src/stores/auth.ts`。
- 前端请求头注入在 `agent-ctrip-reference/ctrip_assistant_fronted/src/services/http.ts`。
- 前端路由守卫在 `agent-ctrip-reference/ctrip_assistant_fronted/src/router/index.ts`。

LangGraph 状态和工作流相关文件：

- LangGraph 状态定义在 `agent-ctrip-reference/ctrip_assistant_backend/graph_chat/state.py`。
- 跨 Agent 转交模型在 `agent-ctrip-reference/ctrip_assistant_backend/graph_chat/base_data_model.py`。
- 主助手 Runnable 在 `agent-ctrip-reference/ctrip_assistant_backend/graph_chat/assistant.py`。
- 专业 Agent Runnable 和工具分组在 `agent-ctrip-reference/ctrip_assistant_backend/graph_chat/agent_assistant.py`。
- 子图构建和路由函数在 `agent-ctrip-reference/ctrip_assistant_backend/graph_chat/build_child_graph.py`。
- 最终 Graph 编译在 `agent-ctrip-reference/ctrip_assistant_backend/graph_chat/finally_graph.py`。
- 入口节点封装在 `agent-ctrip-reference/ctrip_assistant_backend/graph_chat/entry_node.py`。
- 工具节点错误兜底在 `agent-ctrip-reference/ctrip_assistant_backend/tools/tools_handler.py`。

Supervisor、专业 Agent 和任务路由相关文件：

- 参考项目没有名为 Supervisor Agent 的独立文件，但 `agent-ctrip-reference/ctrip_assistant_backend/graph_chat/assistant.py` 中的 primary assistant 承担主控和任务分发角色。
- `agent-ctrip-reference/ctrip_assistant_backend/graph_chat/base_data_model.py` 中的 `ToFlightBookingAssistant`、`ToBookCarRental`、`ToHotelBookingAssistant`、`ToBookExcursion` 是任务转交模型。
- `agent-ctrip-reference/ctrip_assistant_backend/graph_chat/build_child_graph.py` 中的 `route_update_flight`、`route_book_car_rental`、`route_book_hotel`、`route_book_excursion` 是专业子图路由函数。
- `agent-ctrip-reference/ctrip_assistant_backend/graph_chat/finally_graph.py` 中的 `route_primary_assistant` 和 `route_to_workflow` 是主图路由函数。

人工确认和中断机制相关文件：

- 后端中断点配置在 `agent-ctrip-reference/ctrip_assistant_backend/graph_chat/finally_graph.py` 的 `interrupt_before`。
- 后端确认恢复逻辑在 `agent-ctrip-reference/ctrip_assistant_backend/api/graph_api/graph_views.py`，当 `user_input` 为 `y` 时继续执行图。
- 前端确认卡片在 `agent-ctrip-reference/ctrip_assistant_fronted/src/components/assistant/ActionConfirmCard.vue`。
- 前端确认请求在 `agent-ctrip-reference/ctrip_assistant_fronted/src/stores/chat.ts` 的 `confirmAction()`。
- 前端确认文本判断在 `agent-ctrip-reference/ctrip_assistant_fronted/src/utils/graphTextParser.ts`。

参考项目启动入口：

- 后端入口是 `agent-ctrip-reference/ctrip_assistant_backend/main.py`。
- 前端入口是 `agent-ctrip-reference/ctrip_assistant_fronted/src/main.ts`。
- 参考项目后端依赖集中在 `agent-ctrip-reference/ctrip_assistant_backend/requirements.txt`。
- 参考项目前端依赖集中在 `agent-ctrip-reference/ctrip_assistant_fronted/package.json`。

## 2. 可迁移能力清单

以下能力可以迁移为重新实现，不建议逐文件复制。

### 2.1 JWT 用户注册登录

- 可参考 `agent-ctrip-reference/ctrip_assistant_backend/api/system_mgt/user_views.py` 的注册、登录、重复用户名判断和 token 返回流程。
- 可参考 `agent-ctrip-reference/ctrip_assistant_backend/utils/password_hash.py` 的密码哈希与校验思想。
- 可参考 `agent-ctrip-reference/ctrip_assistant_backend/utils/jwt_utils.py` 的 JWT 过期时间和 subject 设计。
- 可参考 `agent-ctrip-reference/ctrip_assistant_fronted/src/stores/auth.ts` 的 token 存储和登录状态维护方式。
- 可参考 `agent-ctrip-reference/ctrip_assistant_fronted/src/services/http.ts` 的请求头注入方式。
- 正式项目应在 `cloud-trip-agent/backend/app/api/routes/` 下新增认证路由，在 `cloud-trip-agent/backend/app/models/` 下新增用户模型，在 `cloud-trip-agent/frontend/src/services/` 和 `cloud-trip-agent/frontend/src/views/` 下重新实现登录注册页面。
- 正式项目产品范围只允许用户名和密码，因此不能迁移 `agent-ctrip-reference/ctrip_assistant_backend/db/system_mgt/models.py` 中的 `phone`、`email`、`real_name`、`icon` 作为第一版必填字段。

### 2.2 LangGraph 状态机和多 Agent 编排

- 可参考 `agent-ctrip-reference/ctrip_assistant_backend/graph_chat/state.py` 的 `State`、消息追加和 `dialog_state` 栈。
- 可参考 `agent-ctrip-reference/ctrip_assistant_backend/graph_chat/base_data_model.py` 的“主控 Agent 通过结构化模型转交专业 Agent”的模式。
- 可参考 `agent-ctrip-reference/ctrip_assistant_backend/graph_chat/build_child_graph.py` 的子图构建、路由函数、工具节点兜底和返回主图模式。
- 可参考 `agent-ctrip-reference/ctrip_assistant_backend/graph_chat/finally_graph.py` 的 `StateGraph` 编译、checkpoint 和中断配置模式。
- 正式项目应在 `cloud-trip-agent/backend/app/agents/` 下重新组织 Supervisor、Requirement、Planner、Transport、Hotel、POI、Ticket、Food、Weather、Verification、Replanner 等 Agent。
- 正式项目的行程生成应继续从 `cloud-trip-agent/backend/app/api/routes/trip.py` 进入，并逐步把 `cloud-trip-agent/backend/app/services/trip_service.py` 内的单 Agent 调用替换为 LangGraph 工作流。

### 2.3 人工确认和中断恢复

- 可参考 `agent-ctrip-reference/ctrip_assistant_backend/graph_chat/finally_graph.py` 的 `interrupt_before` 思路。
- 可参考 `agent-ctrip-reference/ctrip_assistant_backend/api/graph_api/graph_views.py` 的“检测 graph state next 后返回确认提示”的模式。
- 可参考 `agent-ctrip-reference/ctrip_assistant_fronted/src/components/assistant/ActionConfirmCard.vue` 的确认卡片交互。
- 可参考 `agent-ctrip-reference/ctrip_assistant_fronted/src/stores/chat.ts` 的 confirm/revise/cancel 状态处理。
- 正式项目应把人工确认限制在行程生成、局部重规划、预算超限确认、来源不确定确认等允许范围内，不能用于自动预订、支付、退改签。

### 2.4 工具白名单和错误兜底

- 可参考 `agent-ctrip-reference/ctrip_assistant_backend/tools/tools_handler.py` 的 ToolNode fallback 思路。
- 可参考 `agent-ctrip-reference/ctrip_assistant_backend/graph_chat/agent_assistant.py` 的 safe tools 与 sensitive tools 分组思想，但正式项目第一版不允许迁移 sensitive booking tools。
- 正式项目应把 Tavily、高德、天气、本地 RAG、路线、预算工具实现为白名单工具，建议位置在 `cloud-trip-agent/backend/app/agents/tools/` 或 `cloud-trip-agent/backend/app/services/`。
- 正式项目已有 `cloud-trip-agent/backend/app/agents/tools/rag_tool.py`、`cloud-trip-agent/backend/app/services/map_service.py`、`cloud-trip-agent/backend/app/services/weather_service.py`、`cloud-trip-agent/backend/app/services/cache_service.py`，应优先扩展这些现有边界。

### 2.5 前端认证和 Agent 执行展示

- 可参考 `agent-ctrip-reference/ctrip_assistant_fronted/src/router/index.ts` 的路由守卫模式。
- 可参考 `agent-ctrip-reference/ctrip_assistant_fronted/src/stores/chat.ts` 的会话状态设计。
- 可参考 `agent-ctrip-reference/ctrip_assistant_fronted/src/components/assistant/ActionConfirmCard.vue` 的人工确认交互。
- 正式项目当前无 Vue Router 和 Pinia，入口在 `cloud-trip-agent/frontend/src/App.vue`，迁移时需要先决定是否引入路由和状态管理，不能直接替换现有 App 结构。

## 3. 禁止迁移内容

以下功能不允许迁移到 `cloud-trip-agent` 第一版。

- Browser 自动化：参考项目未发现正式 Browser 自动化入口；即使后续发现，也不得迁移到 `cloud-trip-agent`。
- Playwright：参考项目未发现必须迁移的 Playwright 入口；不得新增 Playwright 控制第三方网站。
- 自动预订：不得迁移 `agent-ctrip-reference/ctrip_assistant_backend/tools/hotels_tools.py` 中的 hotel booking 工具，不得迁移 `agent-ctrip-reference/ctrip_assistant_backend/tools/trip_tools.py` 中的 excursion booking 工具。
- 自动支付：参考项目未发现独立支付文件；不得新增自动支付流程。
- 退改签：不得迁移 `agent-ctrip-reference/ctrip_assistant_backend/tools/flights_tools.py` 中的 update/cancel ticket 工具，不得迁移 `agent-ctrip-reference/ctrip_assistant_backend/tools/hotels_tools.py` 中的 update/cancel booking 工具。
- 自驾：不得迁移 `agent-ctrip-reference/ctrip_assistant_backend/tools/car_tools.py` 中的 car rental search/book/update/cancel 相关能力。
- 12306：参考项目未发现 12306 专用文件；不得新增 12306 查询、登录、下单或抢票。
- 携程实时网页查询：不得把 `agent-ctrip-reference/ctrip_assistant_backend/graph_chat/assistant.py`、`agent-ctrip-reference/ctrip_assistant_backend/tools/flights_tools.py`、`agent-ctrip-reference/ctrip_assistant_backend/tools/hotels_tools.py` 的搜索结果描述为携程实时价格、实时库存或可预订结果。
- 自动登录第三方网站：不得迁移或新增任何第三方网站登录流程。
- 多平台实时比价：不得把 Tavily、模型生成内容、本地演示数据或规则估算包装成实时比价结果。

## 4. 文件级迁移映射

| 能力 | 参考文件 | 正式项目目标文件 | 处理方式 |
| --- | --- | --- | --- |
| 用户注册登录路由 | `agent-ctrip-reference/ctrip_assistant_backend/api/system_mgt/user_views.py` | `cloud-trip-agent/backend/app/api/routes/auth.py` | 重新实现用户名密码注册登录，只保留流程思想 |
| 用户认证 Schema | `agent-ctrip-reference/ctrip_assistant_backend/api/system_mgt/user_schemas.py` | `cloud-trip-agent/backend/app/models/schemas.py` 或 `cloud-trip-agent/backend/app/models/auth_schemas.py` | 重新定义，删除手机号、邮箱、角色等第一版外字段 |
| 用户数据模型 | `agent-ctrip-reference/ctrip_assistant_backend/db/system_mgt/models.py` | `cloud-trip-agent/backend/app/models/db_models.py` | 重新实现 `User`，与 `TripRecord` 建立用户隔离关系 |
| 用户 DAO | `agent-ctrip-reference/ctrip_assistant_backend/db/system_mgt/user_dao.py` | `cloud-trip-agent/backend/app/services/auth_service.py` | 参考查询和创建流程，适配正式项目 Session |
| 密码哈希 | `agent-ctrip-reference/ctrip_assistant_backend/utils/password_hash.py` | `cloud-trip-agent/backend/app/services/auth_service.py` 或 `cloud-trip-agent/backend/app/core/security.py` | 可按思想重新实现 bcrypt 哈希 |
| JWT 工具 | `agent-ctrip-reference/ctrip_assistant_backend/utils/jwt_utils.py` | `cloud-trip-agent/backend/app/core/security.py` | 重新实现 token 创建和校验，使用正式项目配置 |
| 认证中间件 | `agent-ctrip-reference/ctrip_assistant_backend/utils/middlewares.py` | `cloud-trip-agent/backend/app/api/dependencies.py` 或 `cloud-trip-agent/backend/app/core/security.py` | 推荐依赖注入式鉴权，不直接复制全局中间件 |
| 前端登录状态 | `agent-ctrip-reference/ctrip_assistant_fronted/src/stores/auth.ts` | `cloud-trip-agent/frontend/src/services/api.ts`、`cloud-trip-agent/frontend/src/types/index.ts`、未来 `cloud-trip-agent/frontend/src/stores/auth.ts` | 若引入状态管理则重新实现；当前项目无 Pinia |
| 前端登录注册页 | `agent-ctrip-reference/ctrip_assistant_fronted/src/views/auth/LoginView.vue`、`agent-ctrip-reference/ctrip_assistant_fronted/src/views/auth/RegisterView.vue` | `cloud-trip-agent/frontend/src/views/Login.vue`、`cloud-trip-agent/frontend/src/views/Register.vue` | 参考交互，不复制 UI |
| LangGraph 状态 | `agent-ctrip-reference/ctrip_assistant_backend/graph_chat/state.py` | `cloud-trip-agent/backend/app/agents/state.py` | 重新定义旅行规划专用 State |
| Agent 转交模型 | `agent-ctrip-reference/ctrip_assistant_backend/graph_chat/base_data_model.py` | `cloud-trip-agent/backend/app/agents/schemas.py` | 只迁移结构化转交模式，不迁移 booking/car 模型 |
| Supervisor Agent | `agent-ctrip-reference/ctrip_assistant_backend/graph_chat/assistant.py` | `cloud-trip-agent/backend/app/agents/supervisor.py` | 重新实现旅行规划主控 |
| 专业 Agent | `agent-ctrip-reference/ctrip_assistant_backend/graph_chat/agent_assistant.py` | `cloud-trip-agent/backend/app/agents/transport_agent.py`、`hotel_agent.py`、`poi_agent.py`、`food_agent.py`、`weather_agent.py` | 仅参考分工方式，禁止迁移敏感 booking tools |
| 子图路由 | `agent-ctrip-reference/ctrip_assistant_backend/graph_chat/build_child_graph.py` | `cloud-trip-agent/backend/app/agents/workflow.py` | 重新实现 LangGraph 节点和路由 |
| 图编译和中断 | `agent-ctrip-reference/ctrip_assistant_backend/graph_chat/finally_graph.py` | `cloud-trip-agent/backend/app/agents/workflow.py` | 参考 `interrupt_before`，不得迁移自动 DB 初始化 |
| 工具兜底 | `agent-ctrip-reference/ctrip_assistant_backend/tools/tools_handler.py` | `cloud-trip-agent/backend/app/agents/tools/common.py` | 重新实现工具异常兜底 |
| Tavily 工具 | `agent-ctrip-reference/ctrip_assistant_backend/graph_chat/llm_tavily.py` | `cloud-trip-agent/backend/app/agents/tools/tavily_tool.py` | 重新实现后端白名单工具，保存标题、URL、摘要、查询时间和来源类型 |
| 航班搜索 | `agent-ctrip-reference/ctrip_assistant_backend/tools/flights_tools.py` | `cloud-trip-agent/backend/app/services/transport_service.py` | 只参考演示数据查询形态，禁止 update/cancel |
| 酒店搜索 | `agent-ctrip-reference/ctrip_assistant_backend/tools/hotels_tools.py` | `cloud-trip-agent/backend/app/services/hotel_service.py` | 只参考搜索，禁止 book/update/cancel |
| 景点搜索 | `agent-ctrip-reference/ctrip_assistant_backend/tools/trip_tools.py` | `cloud-trip-agent/backend/app/services/poi_service.py` | 只参考公开信息推荐，不迁移 booking/update/cancel |
| RAG 检索 | `agent-ctrip-reference/ctrip_assistant_backend/tools/retriever_advanced.py` | `cloud-trip-agent/backend/app/rag/retriever.py`、`cloud-trip-agent/backend/app/agents/tools/rag_tool.py` | 优先扩展正式项目已有 RAG |
| Graph API | `agent-ctrip-reference/ctrip_assistant_backend/api/graph_api/graph_views.py` | `cloud-trip-agent/backend/app/api/routes/trip.py` 或未来 `agent.py` | 不直接引入 `/api/graph/`，避免与现有行程 API 冲突 |
| 人工确认前端 | `agent-ctrip-reference/ctrip_assistant_fronted/src/components/assistant/ActionConfirmCard.vue` | `cloud-trip-agent/frontend/src/components/AgentConfirmCard.vue` | 重新实现行程确认交互 |

## 5. 数据模型冲突

用户模型冲突：

- 参考项目用户模型 `agent-ctrip-reference/ctrip_assistant_backend/db/system_mgt/models.py` 包含 `username`、`password`、`phone`、`email`、`real_name`、`icon`。
- 正式项目当前模型 `cloud-trip-agent/backend/app/models/db_models.py` 只有 `TripRecord`，没有用户隔离字段。
- 产品需求要求第一版只使用用户名和密码，因此正式项目不能照搬参考项目的手机号、邮箱、真实姓名、头像字段作为认证范围。
- 迁移时应新增正式项目用户模型，并为 `cloud-trip-agent/backend/app/models/db_models.py` 中的行程记录增加用户归属设计，但该设计会影响现有 `TripRecord` 保存和查询流程，需要单独确认后实施。

行程模型冲突：

- 正式项目行程持久化集中在 `cloud-trip-agent/backend/app/models/db_models.py` 的 `TripRecord.itinerary_json`。
- 正式项目请求/响应结构在 `cloud-trip-agent/backend/app/models/schemas.py`，服务调用在 `cloud-trip-agent/backend/app/services/trip_service.py`。
- 参考项目旅行数据大量依赖工具函数和示例数据库，涉及 `agent-ctrip-reference/ctrip_assistant_backend/tools/flights_tools.py`、`hotels_tools.py`、`trip_tools.py`、`car_tools.py`。
- 参考项目的工具数据模型服务于航班改签、酒店预订、租车、景点预订等流程，与正式项目“只生成和保存行程、不预订不支付”的范围冲突。

Agent 状态冲突：

- 参考项目状态在 `agent-ctrip-reference/ctrip_assistant_backend/graph_chat/state.py` 中以 `messages`、`user_info`、`dialog_state` 为核心。
- 正式项目当前没有 LangGraph 状态模型，行程生成主要由 `cloud-trip-agent/backend/app/agents/trip_planner_agent.py` 和 `cloud-trip-agent/backend/app/services/trip_service.py` 串联。
- 正式项目需要新增旅行任务计划、候选方案、预算校验、来源标记、重规划次数、版本号等字段，不能直接使用参考项目的 `State`。

数据来源标记缺失：

- 正式项目 `cloud-trip-agent/backend/app/models/schemas.py` 和 `cloud-trip-agent/backend/app/models/db_models.py` 当前没有统一的数据来源枚举。
- 参考项目 `agent-ctrip-reference/ctrip_assistant_backend/tools/flights_tools.py`、`hotels_tools.py`、`trip_tools.py` 返回结果没有满足正式项目要求的“本地演示数据、规则估算、用户录入、Tavily 外部检索、正式 API”来源标记。
- Tavily 相关参考文件 `agent-ctrip-reference/ctrip_assistant_backend/graph_chat/llm_tavily.py` 未保存标题、来源网址、摘要、查询时间和数据来源类型，不能直接迁移。

版本与长期记忆缺失：

- 正式项目当前 `cloud-trip-agent/backend/app/models/db_models.py` 没有行程版本表和长期记忆表。
- 参考项目的 `agent-ctrip-reference/ctrip_assistant_backend/graph_chat/finally_graph.py` 使用 `MemorySaver` 做图 checkpoint，不等同于正式项目需要的用户可查看、可删除的长期记忆。

## 6. API 冲突

正式项目现有 API：

- `cloud-trip-agent/backend/app/api/routes/trip.py` 提供 `GET /trip`、`POST /trip/generate`、`POST /trip/edit`、`POST /trip/save`、`GET /trip/{trip_id}`、`DELETE /trip/{trip_id}`。
- `cloud-trip-agent/backend/app/api/routes/weather.py` 提供天气查询。
- `cloud-trip-agent/backend/app/api/routes/export.py` 提供导出接口。
- 前端调用集中在 `cloud-trip-agent/frontend/src/services/api.ts`。

参考项目 API：

- `agent-ctrip-reference/ctrip_assistant_backend/api/system_mgt/user_views.py` 在 `/api` 前缀下提供 `/register/`、`/login/`、`/auth/`、`/users/getUsers/`、`/users/{pk}/`。
- `agent-ctrip-reference/ctrip_assistant_backend/api/graph_api/graph_views.py` 在 `/api` 前缀下提供 `/graph/`。
- 前端请求封装在 `agent-ctrip-reference/ctrip_assistant_fronted/src/services/auth.ts` 和 `agent-ctrip-reference/ctrip_assistant_fronted/src/services/graph.ts`。

冲突判断：

- 正式项目目前没有 `/api` 统一前缀，参考项目使用 `/api` 前缀；直接复制会导致前端代理和路径风格不一致。
- 正式项目已有 `/trip/generate` 作为行程生成入口，参考项目 `/api/graph/` 是聊天式入口；直接引入会造成“表单生成行程”和“聊天驱动 Graph”两个入口并存，任务边界不清。
- 参考项目 `/users/*` 包含用户列表、更新、删除等管理能力，不在正式项目第一版页面范围内，不能迁移为公开 API。
- 参考项目 `/login/` 和 `/register/` 的末尾斜杠风格与正式项目当前 `/trip/generate` 风格不同，正式项目应统一 API 风格后再实现。
- 正式项目 `cloud-trip-agent/frontend/src/services/api.ts` 当前没有 token 注入逻辑；如果新增鉴权，必须同步保护 `cloud-trip-agent/backend/app/api/routes/trip.py`、`export.py` 等受保护接口。

## 7. 推荐迁移顺序

### 阶段 1：认证基础

- 目标文件：`cloud-trip-agent/backend/app/api/routes/auth.py`、`cloud-trip-agent/backend/app/models/db_models.py`、`cloud-trip-agent/backend/app/models/schemas.py`、`cloud-trip-agent/backend/app/api/main.py`、`cloud-trip-agent/frontend/src/services/api.ts`。
- 参考文件：`agent-ctrip-reference/ctrip_assistant_backend/api/system_mgt/user_views.py`、`agent-ctrip-reference/ctrip_assistant_backend/utils/password_hash.py`、`agent-ctrip-reference/ctrip_assistant_backend/utils/jwt_utils.py`、`agent-ctrip-reference/ctrip_assistant_fronted/src/services/http.ts`。
- 实施原则：只做用户名、密码、哈希、JWT、受保护行程接口，不做手机号、邮箱、用户管理后台。

### 阶段 2：用户数据隔离

- 目标文件：`cloud-trip-agent/backend/app/models/db_models.py`、`cloud-trip-agent/backend/app/services/storage_service.py`、`cloud-trip-agent/backend/app/api/routes/trip.py`。
- 参考文件：`agent-ctrip-reference/ctrip_assistant_backend/utils/dependencies.py`、`agent-ctrip-reference/ctrip_assistant_backend/utils/middlewares.py`。
- 实施原则：让 `TripRecord` 与当前用户绑定，未登录用户访问受保护行程接口返回未认证错误。

### 阶段 3：LangGraph 骨架

- 目标文件：`cloud-trip-agent/backend/app/agents/state.py`、`cloud-trip-agent/backend/app/agents/workflow.py`、`cloud-trip-agent/backend/app/agents/supervisor.py`、`cloud-trip-agent/backend/app/services/trip_service.py`。
- 参考文件：`agent-ctrip-reference/ctrip_assistant_backend/graph_chat/state.py`、`base_data_model.py`、`assistant.py`、`build_child_graph.py`、`finally_graph.py`。
- 实施原则：先替换为能生成现有等价结果的最小 LangGraph，再逐步拆专业 Agent。

### 阶段 4：工具白名单和来源标记

- 目标文件：`cloud-trip-agent/backend/app/agents/tools/rag_tool.py`、`cloud-trip-agent/backend/app/services/map_service.py`、`cloud-trip-agent/backend/app/services/weather_service.py`、未来 `cloud-trip-agent/backend/app/agents/tools/tavily_tool.py`。
- 参考文件：`agent-ctrip-reference/ctrip_assistant_backend/tools/tools_handler.py`、`agent-ctrip-reference/ctrip_assistant_backend/graph_chat/llm_tavily.py`。
- 实施原则：Tavily 只能作为后端封装工具，保存标题、来源网址、摘要、查询时间、数据来源类型，并在失败时回退到高德、本地知识库或演示数据。

### 阶段 5：专业 Agent 拆分

- 目标文件：`cloud-trip-agent/backend/app/agents/transport_agent.py`、`hotel_agent.py`、`poi_agent.py`、`food_agent.py`、`weather_agent.py`、`verification_agent.py`、`replanner_agent.py`。
- 参考文件：`agent-ctrip-reference/ctrip_assistant_backend/graph_chat/agent_assistant.py`、`build_child_graph.py`。
- 实施原则：只迁移“职责拆分和路由”思想，不迁移预订、支付、退改签、自驾和携程实时网页查询。

### 阶段 6：人工确认和局部重规划

- 目标文件：`cloud-trip-agent/backend/app/agents/workflow.py`、`cloud-trip-agent/backend/app/api/routes/trip.py`、`cloud-trip-agent/frontend/src/components/AgentConfirmCard.vue`、`cloud-trip-agent/frontend/src/views/Result.vue`。
- 参考文件：`agent-ctrip-reference/ctrip_assistant_backend/api/graph_api/graph_views.py`、`agent-ctrip-reference/ctrip_assistant_fronted/src/components/assistant/ActionConfirmCard.vue`、`agent-ctrip-reference/ctrip_assistant_fronted/src/stores/chat.ts`。
- 实施原则：确认点只用于预算超限、来源不确定、局部重规划和保存版本，不用于第三方交易。

### 阶段 7：版本、长期记忆和导出串联

- 目标文件：`cloud-trip-agent/backend/app/models/db_models.py`、`cloud-trip-agent/backend/app/services/storage_service.py`、`cloud-trip-agent/backend/app/services/export_service.py`、`cloud-trip-agent/backend/app/api/routes/export.py`、`cloud-trip-agent/frontend/src/views/History.vue`。
- 参考文件：`agent-ctrip-reference/ctrip_assistant_backend/graph_chat/finally_graph.py` 的 checkpoint 思想。
- 实施原则：长期记忆必须是用户可开关、可查看、可删除的数据，不等同于 LangGraph 内部 checkpoint。

## 8. 每个阶段的回滚点

阶段 1 回滚点：

- 回滚目标：认证功能不影响现有匿名行程生成。
- 可回滚文件：`cloud-trip-agent/backend/app/api/routes/auth.py`、`cloud-trip-agent/backend/app/api/main.py`、`cloud-trip-agent/backend/app/models/db_models.py`、`cloud-trip-agent/backend/app/models/schemas.py`、`cloud-trip-agent/frontend/src/services/api.ts`。
- 验证方式：回到只通过 `cloud-trip-agent/backend/app/api/routes/trip.py` 调用 `/trip/generate` 的状态。

阶段 2 回滚点：

- 回滚目标：用户隔离失败时恢复 `TripRecord` 原有保存和列表查询。
- 可回滚文件：`cloud-trip-agent/backend/app/models/db_models.py`、`cloud-trip-agent/backend/app/services/storage_service.py`、`cloud-trip-agent/backend/app/api/routes/trip.py`。
- 验证方式：`cloud-trip-agent/frontend/src/views/History.vue` 能继续展示历史行程。

阶段 3 回滚点：

- 回滚目标：LangGraph 骨架失败时恢复 `cloud-trip-agent/backend/app/agents/trip_planner_agent.py` 的现有单 Agent 生成流程。
- 可回滚文件：`cloud-trip-agent/backend/app/services/trip_service.py`、`cloud-trip-agent/backend/app/agents/state.py`、`cloud-trip-agent/backend/app/agents/workflow.py`、`cloud-trip-agent/backend/app/agents/supervisor.py`。
- 验证方式：`cloud-trip-agent/backend/app/api/routes/trip.py` 的 `/trip/generate` 返回结构仍符合 `cloud-trip-agent/backend/app/models/schemas.py`。

阶段 4 回滚点：

- 回滚目标：Tavily 或工具白名单失败时恢复高德、本地 RAG 和演示数据。
- 可回滚文件：`cloud-trip-agent/backend/app/agents/tools/tavily_tool.py`、`cloud-trip-agent/backend/app/agents/tools/rag_tool.py`、`cloud-trip-agent/backend/app/services/map_service.py`、`cloud-trip-agent/backend/app/services/weather_service.py`。
- 验证方式：Tavily API Key 为空时，`cloud-trip-agent/backend/app/services/trip_service.py` 仍能生成候选行程。

阶段 5 回滚点：

- 回滚目标：专业 Agent 拆分失败时恢复阶段 3 的最小 LangGraph 或原单 Agent 流程。
- 可回滚文件：`cloud-trip-agent/backend/app/agents/transport_agent.py`、`hotel_agent.py`、`poi_agent.py`、`food_agent.py`、`weather_agent.py`、`verification_agent.py`、`replanner_agent.py`、`workflow.py`。
- 验证方式：`cloud-trip-agent/frontend/src/views/Result.vue` 能继续展示 2 至 3 个候选行程。

阶段 6 回滚点：

- 回滚目标：人工确认失败时恢复无中断的自动生成和保存。
- 可回滚文件：`cloud-trip-agent/backend/app/agents/workflow.py`、`cloud-trip-agent/backend/app/api/routes/trip.py`、`cloud-trip-agent/frontend/src/components/AgentConfirmCard.vue`、`cloud-trip-agent/frontend/src/views/Result.vue`。
- 验证方式：用户不进行确认操作时，行程生成不被阻塞在不可恢复状态。

阶段 7 回滚点：

- 回滚目标：版本或长期记忆失败时保留现有行程保存和 PDF 导出。
- 可回滚文件：`cloud-trip-agent/backend/app/models/db_models.py`、`cloud-trip-agent/backend/app/services/storage_service.py`、`cloud-trip-agent/backend/app/services/export_service.py`、`cloud-trip-agent/backend/app/api/routes/export.py`、`cloud-trip-agent/frontend/src/views/History.vue`。
- 验证方式：`cloud-trip-agent/backend/app/api/routes/export.py` 的导出能力仍可读取已保存行程。

## 9. 主要技术风险

认证与数据隔离风险：

- `cloud-trip-agent/backend/app/models/db_models.py` 当前只有 `TripRecord`，新增用户隔离会影响 `cloud-trip-agent/backend/app/services/storage_service.py` 的保存、列表、查询、删除逻辑。
- `cloud-trip-agent/frontend/src/services/api.ts` 当前没有 token 注入，新增认证会影响全部受保护接口调用。
- 参考项目 `agent-ctrip-reference/ctrip_assistant_backend/api/system_mgt/user_views.py` 包含用户管理能力，若直接迁移会扩大正式项目范围。

LangGraph 改造风险：

- `cloud-trip-agent/backend/app/services/trip_service.py` 当前围绕单 Agent 和服务函数组织，直接替换为 LangGraph 可能改变 `/trip/generate` 响应结构。
- 参考项目 `agent-ctrip-reference/ctrip_assistant_backend/graph_chat/finally_graph.py` 会初始化示例数据库并更新日期，这种副作用不能迁移到正式项目启动链路。
- 参考项目 `agent-ctrip-reference/ctrip_assistant_backend/graph_chat/base_data_model.py` 和 `agent_assistant.py` 的任务类型包含 booking、car rental、cancel/update 等正式项目禁止功能，复用时容易误带越界能力。

工具和数据来源风险：

- `agent-ctrip-reference/ctrip_assistant_backend/graph_chat/llm_tavily.py` 直接初始化 Tavily 工具，但没有满足正式项目的数据落库和来源标记要求。
- `cloud-trip-agent/backend/app/services/map_service.py`、`weather_service.py`、`cloud-trip-agent/backend/app/rag/retriever.py` 已有能力边界，新增 Tavily 时必须避免让 Agent 任意访问网址。
- `cloud-trip-agent/backend/app/models/schemas.py` 当前缺少数据来源枚举，若不先统一来源字段，航班、高铁、酒店、门票和 Tavily 摘要容易被前端误展示为实时数据。

API 演进风险：

- `agent-ctrip-reference/ctrip_assistant_backend/api/graph_api/graph_views.py` 的 `/api/graph/` 是聊天式接口，正式项目 `cloud-trip-agent/backend/app/api/routes/trip.py` 是表单式行程接口，二者并行可能让前端流程分裂。
- `cloud-trip-agent/frontend/src/App.vue` 当前没有 Vue Router；若直接迁移 `agent-ctrip-reference/ctrip_assistant_fronted/src/router/index.ts`，会改变正式项目页面组织方式。
- `agent-ctrip-reference/ctrip_assistant_fronted/src/stores/auth.ts` 和 `chat.ts` 使用 Pinia；正式项目 `cloud-trip-agent/frontend/package.json` 当前是否引入状态管理需要单独评估，不能直接套用 store。

Docker 和启动风险：

- 正式项目 Docker 编排在 `cloud-trip-agent/docker-compose.yaml`，后端入口在 `cloud-trip-agent/backend/Dockerfile`，前端入口在 `cloud-trip-agent/frontend/Dockerfile`。
- 参考项目启动入口 `agent-ctrip-reference/ctrip_assistant_backend/main.py` 和 `agent-ctrip-reference/ctrip_assistant_fronted/package.json` 不应合并进正式项目 Docker 启动链路。
- 若迁移引入新的 Python 依赖，例如 JWT、passlib、LangGraph 或 Tavily SDK，必须单独评估 `cloud-trip-agent/backend/requirements.txt`，不能在同一阶段混入业务改造。

范围失控风险：

- 参考项目 `agent-ctrip-reference/ctrip_assistant_backend/tools/flights_tools.py`、`hotels_tools.py`、`car_tools.py`、`trip_tools.py` 包含大量交易后动作，正式项目第一版明确不支持自动预订、自动支付、退改签、自驾和携程实时网页查询。
- 正式项目应保持 `cloud-trip-agent` 为唯一正式项目，不允许把 `agent-ctrip-reference` 作为第二套运行系统接入。
