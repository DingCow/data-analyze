# LangGraph 架构说明

本文档面向两类读者：

1. 后续接手本项目的开发者
2. 后续继续改造本项目的 agent

它记录当前 `codex/langgraph-architecture` 分支的 LangGraph 迁移结果、关键边界和验证方式。

## 迁移目标

这个项目原本已经在 `main` 分支完成了一个可运行的 legacy 版本。

本分支的目标不是继续堆功能，而是把原来集中在 router / workflow 函数里的控制流，逐步迁移成更接近主流 Agent 架构的 LangGraph DAG。

核心变化：

```text
原来：
一个较大的 router 函数
  ↓
内部通过 if/else / try/except 串起 SQL、Analysis、Report

现在：
LangGraph StateGraph
  ↓
节点负责做事
边负责决定下一步
state 负责传递中间字段
```

## 分支与 baseline

| 项 | 说明 |
|---|---|
| legacy baseline | `main` 分支 |
| baseline tag | `baseline-simple-agent` |
| LangGraph 分支 | `codex/langgraph-architecture` |
| 当前默认 runner | `langgraph` |

当前分支里，CLI 和 Web API 都默认使用 LangGraph runner：

```text
main.py
  ↓
get_runner("langgraph")

src/webapi/app.py
  ↓
get_runner("langgraph")
```

`main` 分支继续作为 legacy baseline，不需要在本分支里继续维护 legacy 对照测试。

## 入口结构

统一运行入口在：

```text
src/agent_runtime/runners.py
```

主要对象：

| 对象 | 作用 |
|---|---|
| `WorkflowResult` | CLI / Web API 共同依赖的统一返回结构 |
| `WorkflowRunner` | runner 协议 |
| `LegacyWorkflowRunner` | legacy router 的适配器 |
| `LangGraphWorkflowRunner` | LangGraph workflow 的适配器 |
| `get_runner()` | 根据名称返回 runner |

这层的意义是：

```text
入口稳定
  ↓
内部实现可以从 legacy 切到 langgraph
  ↓
CLI / Web 不直接依赖某个具体编排方式
```

## 当前 DAG

### Simple 路径

```text
classify
  ↓
simple_sql
  ├→ 成功 → finalize
  └→ 失败 → error → finalize
```

说明：

- simple 问题只查数，不生成报告
- simple SQL 失败时进入 `error` 节点
- simple SQL 当前没有额外的 repair / retry 节点，避免为了对称而增加复杂度

### Complex 成功路径

```text
classify
  ↓
decompose
  ↓
complex_sql
  ↓
prepare_analysis_input
  ↓
analyze_data
  ↓
generate_report_payload
  ↓
generate_markdown_report
  ↓
generate_chart_config
  ↓
finalize
```

说明：

- `decompose` 负责把复杂问题拆成 SQL 查询规划
- `complex_sql` 根据原始问题和拆解结果取数
- `prepare_analysis_input` 把 `raw_rows` 组织成模型输入
- `analyze_data` 生成分析结论
- report 被拆成报告对象生成、Markdown 提取、图表配置提取三个节点

### Complex SQL 重试路径

```text
complex_sql
  └→ 失败
       ↓
    repair_sql
       ↓
    retry_complex_sql
       ├→ 成功 → prepare_analysis_input
       └→ 失败 → error → finalize
```

说明：

- 当前只对 complex SQL 做图级重试
- 重试最多一次
- `repair_sql` 不引入新的 LLM 修复器，只把原始问题、拆解任务和错误信息重新组织成更明确的重试问题
- simple SQL 不做图级重试

## 节点职责

节点定义在：

```text
src/agent_runtime/nodes.py
```

| 节点 | 职责 |
|---|---|
| `classify` | 判断问题是 `simple` 还是 `complex` |
| `simple_sql` | simple 路径直接查询数据 |
| `decompose` | complex 路径先拆解查询任务 |
| `complex_sql` | 根据拆解结果查询数据 |
| `repair_sql` | complex SQL 失败后准备重试问题 |
| `retry_complex_sql` | complex SQL 图级重试一次 |
| `prepare_analysis_input` | 把 `raw_rows` 转成后置分析输入 |
| `analyze_data` | 调用分析模型生成 `analysis_text` |
| `generate_report_payload` | 生成包含 Markdown 和 chart 的报告对象 |
| `generate_markdown_report` | 提取最终 Markdown 报告到 `answer` |
| `generate_chart_config` | 提取图表配置到 `chart_config` |
| `error` | 错误收口，保留错误信息并阻止继续分析 / 报告 |
| `finalize` | 统一结束节点 |

## State 字段

LangGraph state 定义在：

```text
src/agent_runtime/state.py
```

常用字段：

| 字段 | 含义 |
|---|---|
| `schema` | 数据库结构 |
| `question` | 用户问题 |
| `history` | 多轮对话历史 |
| `intent` | `simple` 或 `complex` |
| `subtasks` | complex 问题拆解后的查询规划 |
| `raw_rows` | SQL 查询结果 |
| `retry_question` | complex SQL 重试问题 |
| `analysis_input` | 后置分析模型输入 |
| `analysis_text` | 分析结论 |
| `report_payload` | Report Agent 生成的原始报告对象 |
| `answer` | 最终 Markdown 报告 |
| `chart_config` | 图表配置 |
| `error` | 错误信息 |
| `error_node` | 失败节点 |
| `retry_count` | 当前 workflow 图级重试次数 |
| `trace` | 节点执行路径 |

## API Debug Metadata

`WorkflowResult` 会把运行元数据放进 `debug`：

```json
{
  "debug": {
    "trace": ["classify", "decompose", "complex_sql"],
    "retry_count": 1,
    "error_node": null
  }
}
```

用途：

| 字段 | 说明 |
|---|---|
| `debug.trace` | 本次运行经过哪些节点 |
| `debug.retry_count` | 图级重试次数 |
| `debug.error_node` | 如果失败，最后失败在哪个节点 |

注意：

- UI 当前不展示 debug
- debug 主要用于后端排查、学习复盘和架构展示
- 不要为了展示 debug 而顺手改前端 UI

## 与 workflow 模块的关系

当前迁移尽量保留原有 `src/workflow` 模块能力，只把内部职责拆成更清晰的函数，供 LangGraph 节点调用。

### Analysis

文件：

```text
src/workflow/analysis.py
```

保留兼容入口：

```text
analyze(question, raw_rows)
```

新增拆分函数：

| 函数 | 作用 |
|---|---|
| `format_raw_rows` | 把结构化数据转文字表格 |
| `build_analysis_input` | 构造后置分析模型输入 |
| `analyze_prepared` | 调用推理模型生成分析结论 |

LangGraph 使用：

```text
build_analysis_input
  ↓
analyze_prepared
```

### Report

文件：

```text
src/workflow/report.py
```

保留兼容入口：

```text
run(question, analysis, raw_rows)
```

新增拆分函数：

| 函数 | 作用 |
|---|---|
| `build_report_input` | 构造报告模型输入 |
| `generate_report_payload` | 生成包含 Markdown 和 chart 的报告对象 |
| `extract_markdown` | 提取 Markdown |
| `extract_chart_config` | 提取图表配置 |

LangGraph 使用：

```text
build_report_input
  ↓
generate_report_payload
  ↓
extract_markdown
  ↓
extract_chart_config
```

## 测试策略

主要测试文件：

```text
tests/test_agent_runtime.py
tests/test_api.py
```

测试覆盖：

| 测试层级 | 覆盖内容 |
|---|---|
| runner 注册 | `get_runner("langgraph")` 返回 LangGraph runner |
| simple 路径 | `classify -> simple_sql -> finalize` |
| simple 错误 | `classify -> simple_sql -> error -> finalize` |
| complex 成功 | 完整 complex DAG 路径 |
| complex 重试成功 | `complex_sql -> repair_sql -> retry_complex_sql -> prepare_analysis_input` |
| complex 重试失败 | `retry_complex_sql -> error -> finalize` |
| 节点级测试 | repair / retry / analysis / report 相关节点输入输出 |
| API 测试 | Web API 默认调用 LangGraph runner，并返回 debug |

验证命令：

```bash
.venv/bin/python -m unittest tests.test_agent_runtime tests.test_api -v
.venv/bin/python -m compileall src tests/test_agent_runtime.py tests/test_api.py main.py
```

当前最近一次验证结果：

```text
Ran 20 tests ... OK
compileall passed
```

## 当前明确不做的事

| 不做 | 原因 |
|---|---|
| 不改 SQLite 路径 | 项目硬约束，必须使用 `/Users/owenlau/SqliteDB.db` |
| 不改 `.env` / `DEEPSEEK_API_KEY` | 项目硬约束 |
| 不把 simple SQL 也做 retry | 收益不明显，容易为了对称而增加复杂度 |
| 不改 UI 展示 debug | debug 主要给后端排查和学习复盘，不干扰普通用户 |
| 不做配置化 runner | 当前已经用 `main` / graph 分支区分 legacy 和 LangGraph |
| 不继续拆业务节点 | 基础节点迁移已经完成，继续拆容易过度设计 |

## 后续建议

优先级从高到低：

1. 提交当前 LangGraph 分支，形成架构迁移检查点
2. 根据需要补充 README 中的架构说明入口链接
3. 后续如果要展示 debug，再单独设计开发者面板，不要混入当前迁移收尾
4. 如果继续演进，可以考虑 SQL 生成 / SQL 执行的更细拆分，但这会明显扩大复杂度

## 给后续 Agent 的注意事项

继续本分支工作时，请遵守：

1. 先读 `docs/langgraph_migration_checklist.md` 和本文档，不要重新从零推断迁移状态
2. 不要把 `main` 分支的 legacy 逻辑回迁到本分支做重复对照
3. 不要擅自修改数据库路径、模型环境变量或 DeepSeek 配置
4. 不要为了“更像 LangGraph”继续无目的拆节点
5. 修改 graph 路径时，必须同步更新 trace 断言测试
6. 修改 API 返回结构时，必须同步更新 `tests/test_api.py`
7. 如果新增节点，必须说明它解决的真实问题，不接受只为了命名对称而新增节点

这份文档是当前 LangGraph 迁移阶段的接力说明。
