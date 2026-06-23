# AGENTS.md

## Project Scope

1. 当前仓库 `cloud-trip-agent` 是唯一正式项目。
2. 项目以现有智旅云图代码为基础。
3. `agent-ctrip-reference` 仅作为 JWT、LangGraph、多 Agent 编排和人工确认机制的参考，不允许整体复制。

## Tavily Search API Rules

4. 第一版允许使用 Tavily Search API，但必须满足：
   - 只能通过后端封装的 Tavily 工具调用；
   - 不允许 Agent 自由访问任意网址；
   - 主要用于检索景点、餐饮、开放时间、旅游提示和公开攻略；
   - 搜索结果必须保存标题、来源网址、摘要和查询时间；
   - Tavily 结果属于外部检索信息，不能直接视为确定事实；
   - 写入行程前必须经过字段校验、去重和来源标记；
   - Tavily 调用失败时，应回退到高德 POI、本地知识库或演示数据；
   - Tavily API Key 只能保存在后端 `.env` 中；
   - 不得将 Tavily API Key 输出到日志、前端或模型上下文。
5. Tavily 搜索结果不得描述为携程实时价格、实时库存或可预订结果。

## Explicitly Out Of Scope For V1

6. 第一版明确不开发：
   - Browser 自动化；
   - Playwright 控制第三方网站；
   - 携程实时网页查询；
   - 自动登录第三方网站；
   - 自动预订；
   - 自动支付；
   - 退票、改签、取消订单；
   - 自驾；
   - 12306；
   - 多平台实时比价。

## Technology Constraints

7. 后端必须使用 Python 和 FastAPI。
8. 前端必须使用 Vue 3 和 TypeScript。
9. Agent 编排使用 LangGraph。
10. 所有模型调用统一封装，使用 ModelScope 配置，不在前端提供模型切换。

## Data Source And Fact Rules

11. 航班、高铁、酒店和门票数据必须标记来源：
    - 本地演示数据；
    - 规则估算；
    - 用户录入；
    - Tavily 外部检索；
    - 正式 API。
12. 不允许把演示数据或模型生成数据描述为实时价格。
13. 预算、日期、权限、版本号和状态机必须使用确定性 Python 代码，不交给大模型自由计算。

## Agent Tool Permissions

14. 不允许给 Agent 提供：
    - Shell；
    - PowerShell；
    - subprocess；
    - eval；
    - exec；
    - 任意 Python 执行；
    - 任意文件读写；
    - 任意网址直接访问；
    - Docker API。
15. Agent 访问外部信息时，只能调用经过白名单限制的后端工具，例如：
    - TavilySearchTool；
    - AmapPOITool；
    - WeatherTool；
    - LocalRAGTool；
    - RouteTool；
    - BudgetTool。

## Secrets And Generated Data

16. 不允许提交：
    - `.env`；
    - API Key；
    - 密码；
    - Token；
    - SQLite 运行数据；
    - Chroma 运行数据；
    - 导出的 PDF。

## Workflow Rules

17. 每次只完成一个小任务，不允许自动进入下一阶段。
18. 修改前必须先列出：
    - 当前行为；
    - 计划修改的文件；
    - 修改原因。
19. 每次修改必须补充必要测试。
20. 完成后必须汇报：
    - 修改文件；
    - 实现内容；
    - 执行命令；
    - 测试结果；
    - 已知问题；
    - 推荐下一步。
21. 不允许无关重构，不允许删除已有可运行功能。
22. 当前开发分支为 `develop`，不得直接修改 `main`。
23. 遇到需要扩大任务范围、修改数据模型或修改已冻结 API 的情况，必须先停止并请求确认。
