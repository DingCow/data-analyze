# LangChain → LangGraph 渐进式改造与同步学习计划（历史记录）

> 当前 `main` 分支已经完成 LangGraph 主线迁移，并由 `legacy` 分支保留旧架构 baseline。
> 本文保留为学习过程记录，不再代表当前待执行计划。

## 🧾 简要总结

本计划把项目定位为一次“**流程型 Agent 系统升级**”，不是简单替换框架。实施策略采用**双轨并行**：保留现有手搓版本作为基线，同时新增框架版工作流，先在 **CLI** 跑通，再接回 **Web**。学习路径按 **LangChain 基础组件 → LangChain 顺序链路 → LangGraph 状态图工作流** 递进，同时同步产出**学习笔记**和**简历/面试话术**。

默认目标是最终形成三套可对照资产：

- 现有手搓版流程
- LangChain 版顺序工作流
- LangGraph 版状态图工作流

## 🧱 关键实现设计

### 1. 保留现有版本，新增框架版运行层

实施时不直接推翻现有 `src/workflow`，而是在旁边新增一层框架化运行时，建议结构如下：

- `src/workflow/`：保留为 legacy 基线
- `src/agent_runtime/`：新增框架版运行层
- `src/agent_runtime/models.py`：封装 DeepSeek + LangChain 模型接入
- `src/agent_runtime/tools.py`：封装 `run_sql` 为 LangChain Tool
- `src/agent_runtime/prompts.py`：集中管理 Router / SQL / Analysis / Report prompts
- `src/agent_runtime/chains.py`：实现 LangChain 顺序链路
- `src/agent_runtime/state.py`：定义 LangGraph 的共享状态
- `src/agent_runtime/graph.py`：实现 LangGraph 工作流图
- `src/agent_runtime/runners.py`：统一 runner 接口，屏蔽 legacy / langchain / langgraph 差异

### 2. 明确统一接口，避免 CLI/Web 绑死具体框架

新增统一结果对象与运行接口，作为后续 CLI / Web 的公共边界。

推荐接口：

- `WorkflowResult`
  - `answer: str`
  - `chart_config: dict | None`
  - `raw_rows: list[dict]`
  - `intent: str | None`
  - `trace: list[str]`
  - `error: str | None`
- `WorkflowRunner`
  - `run(question: str, history: list[dict], schema: str) -> WorkflowResult`

默认策略：

- legacy runner 适配当前 `router.run(...)`
- langchain runner 先只实现顺序链路
- langgraph runner 实现最终目标工作流图
- CLI 第一阶段支持 `--runner legacy|langchain|langgraph`
- Web 第二阶段再接入 runner 选择，默认仍走 `legacy`

### 3. 学习与改造按四阶段递进

#### Phase 0：基线整理与依赖标准化

目标：先把当前项目变成一个适合后续学习和演进的 Python 工程。

实现决策：

- 新增最小 `pyproject.toml`
- 明确当前依赖、测试命令、启动命令
- 在文档中补一页“当前手搓架构说明”
- 记录一份“手搓版 vs 框架版”对照表，作为后续学习主线

学习产物：

- `docs/learning/01-current-architecture.md`
- 内容聚焦：当前系统的输入、节点、输出、局限

#### Phase 1：LangChain 基础组件接入

目标：先学会 LangChain 的基础抽象，不急着上图。

实现决策：

- 保持 DeepSeek + OpenAI 兼容接口不变
- 用 LangChain 封装模型调用，而不是重写业务逻辑
- 把 `run_sql` 封成标准 Tool
- 把现有 prompts 收敛到统一 prompt 模块
- 在 CLI 中新增一个最小 LangChain 演示入口，优先打通 simple 查询路径

这一阶段重点学习：

- Chat model 封装
- PromptTemplate / ChatPromptTemplate
- Tool 抽象
- Runnable 串联方式
- 输入输出如何标准化

学习产物：

- `docs/learning/02-langchain-basics.md`
- 一页“LangChain 在本项目里解决了什么，没解决什么”
- 一版简历表述草稿：强调“基于 LangChain 统一模型、Prompt、Tool 接口”

#### Phase 2：用 LangChain 重建顺序复杂链路

目标：在不上 LangGraph 前，先体验“框架化但仍然顺序”的版本。

实现决策：

- 用 LangChain 顺序串联 `classify -> decompose -> sql -> analyze -> report`
- 复杂路径先不强调状态图，只强调可复用组件
- 保留 simple / complex 分流逻辑
- 保留现有输出契约，不改 CLI / Web 展示格式
- 在 CLI 中完成 `legacy` vs `langchain` 的结果对比

这一阶段重点学习：

- 为什么 LangChain 适合做“组件层”
- 为什么复杂条件流转开始变得别扭
- 为什么下一步需要 LangGraph

学习产物：

- `docs/learning/03-langchain-pipeline.md`
- 一页“LangChain 顺序链路的优点与瓶颈”
- 一版面试话术：能说明为什么不止停留在 LangChain

#### Phase 3：LangGraph 工作流图重构

目标：把现有流程真正升级成主流 workflow 式 Agent 系统。

实现决策：

- 定义统一共享状态，至少包含：
  - `question`
  - `history`
  - `schema`
  - `intent`
  - `subtasks`
  - `raw_rows`
  - `analysis_text`
  - `chart_config`
  - `answer`
  - `error`
  - `trace`
- 节点明确映射为：
  - `classify_node`
  - `decompose_node`
  - `sql_node`
  - `analyze_node`
  - `report_node`
- 条件边：
  - `simple -> sql -> finalize`
  - `complex -> decompose -> sql -> analyze -> report -> finalize`
- 明确错误处理：
  - 任一节点异常写入 `error`
  - `finalize` 统一转成 `WorkflowResult`
- 先保证 CLI 下可选择 `langgraph` runner 运行全链路

这一阶段重点学习：

- state 是什么
- node / edge 是什么
- 条件路由如何表达
- 为什么你的项目本质更适合 graph 而不是交互式 multi-agent

学习产物：

- `docs/learning/04-langgraph-workflow.md`
- 一页“为什么本项目是流程型 Agent，不是交互式 multi-agent”
- 一版简历核心表述：强调“基于 LangGraph 设计状态驱动分析工作流”

#### Phase 4：Web 接回 + 项目包装完成

目标：把学习成果接回产品入口，并完成求职表达闭环。

实现决策：

- `src/webapi/app.py` 通过 runner 抽象接入框架版，不直接依赖具体实现
- Web 当前默认使用 `main` 分支的 LangGraph runner；旧架构由 `legacy` 分支保留
- 页面只展示用户必要信息，不暴露过多框架内部术语
- 文档中补齐：
  - 架构演进说明
  - runner 对比
  - 适合简历的项目描述
  - 常见面试问答

学习产物：

- `docs/learning/05-architecture-evolution.md`
- `docs/learning/06-resume-and-interview.md`

## 🔌 重要接口与外部行为变化

本次改造建议显式引入以下“新公共边界”：

- CLI 新增参数：`--runner legacy|langchain|langgraph`
- Web 新增可选运行模式切换，默认 `legacy`
- 新增 `WorkflowRunner` 抽象作为运行时统一入口
- 新增 `WorkflowResult` 作为统一返回结构
- 现有数据库路径、`.env`、`DEEPSEEK_API_KEY`、`os.getenv()` 读取方式全部保持不变
- 不引入向量库、RAG、长期记忆、外部任务队列
- 不把项目改造成交互式 multi-agent 聊天系统

## 🧪 测试与验收计划

### 自动化测试

至少补齐这几类测试：

- legacy runner 适配后行为不变
- langchain runner 的 simple 路径输出契约正确
- langchain runner 的 complex 顺序链路调用顺序正确
- langgraph runner 的 conditional routing 正确
- graph 状态在 simple / complex 路径下字段完整
- 节点异常时 `WorkflowResult.error` 正确落地
- CLI `--runner` 参数正确切换运行时
- Web 接入 runner 后，legacy 默认行为不回归

### 手工验收

每个 runner 至少跑以下场景：

- 最简单查数：`users_info 表前 5 行数据是什么？`
- 聚合统计：`users_info 一共有多少条记录？`
- 时间趋势：`2024 年各月充电收入趋势如何？`
- 空结果：`2026 年各月充电收入趋势如何？`
- 排行分析：`2024 年哪个城市的充电收入最高？请给出前 10 名并简单总结。`

验收要求：

- `legacy` 作为基线
- `langchain` 至少完成 CLI 下 simple 和 complex 路径
- `langgraph` 在 CLI 下完整通过 5 条场景
- Web 接回后至少完成上述 3 条核心场景：简单查数、趋势分析、空结果

## 📚 同步学习与求职包装安排

每一阶段都必须同步产出三类内容，不允许只写代码：

- 学习笔记：解释这一阶段新抽象是什么、解决了什么问题
- 对照笔记：手搓版 vs 框架版差异
- 简历/面试话术：用业务语言讲“我为什么这样设计”

最终项目包装口径统一为：

- 这是一个面向数据分析问答的流程型 Agent 系统
- 初版手搓完成 Router / SQL / Analysis / Report 四段式链路
- 后续基于 LangChain 统一模型、Prompt、Tool 抽象
- 再基于 LangGraph 重构为状态驱动工作流图
- 支持 simple / complex 条件路由、只读 SQL 工具调用和报告生成
- 保留 CLI / Web 双入口，便于验证与演示

## ⚙️ 默认假设

- 迁移目标是“学习主流框架 + 强化项目表达”，不是追求功能扩张
- 先 CLI 后 Web，不一次性双入口同步重构
- 先建立框架版并行实现，不删除 legacy 实现
- prompt 语义初期尽量保持一致，先改编排，不先改业务口径
- 采用 `pyproject.toml` 作为依赖入口，兼顾现代 Python 工程表达和后续维护
- LangChain 作为组件层，LangGraph 作为最终编排层
- 项目最终定位仍是“流程型 Agent 工作流”，不扩展为真正的对话式 multi-agent 系统
