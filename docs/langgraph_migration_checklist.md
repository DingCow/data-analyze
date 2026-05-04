# LangGraph 架构迁移清单

这个清单用于记录 `codex/langgraph-architecture` 分支上的架构迁移进度。

目标不是一次性重写项目，而是像数仓链路迁移一样：

```text
保留 legacy baseline
  ↓
搭建新 DAG 骨架
  ↓
逐个节点迁移
  ↓
逐层补测试
  ↓
阶段性总结
```

## 当前进度

| 状态 | 阶段 | 改造点 | 说明 | 验证方式 |
|---|---|---|---|---|
| [x] | 0 | baseline tag + graph 分支 | `main` 保留 legacy，graph 分支承载新架构 | baseline tag + 分支已创建 |
| [x] | 1 | runner 统一入口 | 用 `get_runner("legacy/langgraph")` 包住不同实现 | `tests.test_agent_runtime` |
| [x] | 2 | router 改成 LangGraph DAG | `classify -> simple / complex` 从 if/else 变成图 | simple / complex 路径测试 |
| [x] | 3 | LangGraph 编排测试 | 验证路径、state 传递、`WorkflowResult` 输出 | `tests.test_agent_runtime` |
| [x] | 4 | 默认入口切到 LangGraph | CLI / Web 当前默认走 `get_runner("langgraph")` | `tests.test_api` |
| [x] | 5 | SQL 错误分支节点化 | SQL 失败进入 `error -> finalize` | SQL error 路径测试 |
| [x] | 6 | complex SQL 图级恢复 | `complex_sql -> repair_sql -> retry_complex_sql` | 重试成功 / 重试失败路径测试 |
| [x] | 7 | 新增节点单元测试 | 单独验证 `repair_sql_node` / `retry_complex_sql_node` | 节点级测试已通过 |
| [x] | 8 | Analysis 节点改造 | 已拆成 `prepare_analysis_input -> analyze_data` | 编排测试 + 节点级测试已通过 |
| [x] | 9 | Report 节点改造 | 已拆成 `generate_report_payload -> generate_markdown_report -> generate_chart_config` | 编排测试 + 节点级测试已通过 |
| [x] | 10 | 可观测性增强 | API 返回 `debug.trace` / `debug.retry_count` / `debug.error_node` | 编排测试 + API 测试已通过 |
| [-] | 11 | 配置化 runner | 当前用 `main` / graph 分支区分 legacy 和 LangGraph，暂不需要配置切换 | 暂缓 |
| [x] | 12 | 阶段性架构文档 | 已新增 `docs/langgraph_architecture.md`，供开发者和后续 agent 接力 | 文档已完成 |

## 下一步

当前迁移阶段已完成：

```text
当前：
基础节点拆分、最小可观测性和阶段性架构文档已经完成

下一步建议：
先不要继续扩展新功能。
建议提交当前分支，形成 LangGraph 架构迁移检查点。
```

## 常用查看方式

在项目根目录执行：

```bash
sed -n '1,220p' docs/langgraph_migration_checklist.md
```

只看未完成项：

```bash
rg "\[ \]" docs/langgraph_migration_checklist.md
```

只看已完成项：

```bash
rg "\[x\]" docs/langgraph_migration_checklist.md
```

## 常用验证命令

```bash
.venv/bin/python -m unittest tests.test_agent_runtime tests.test_api -v
.venv/bin/python -m compileall src tests/test_agent_runtime.py tests/test_api.py main.py
```
