"""不同 Agent 工作流实现的统一运行入口。"""

from __future__ import annotations

from typing import Protocol

from src.agent_runtime.state import WorkflowResult
from src.workflow import router


class WorkflowRunner(Protocol):
    """统一 runner 协议。

    可以把它理解成数据开发里的“统一产出表结构”：上游怎么实现可以变，
    但下游 CLI / Web 读取的字段必须稳定。
    """

    name: str

    def run(self, schema: str, question: str, history: list[dict]) -> WorkflowResult:
        """执行一次自然语言分析工作流。"""


class LegacyWorkflowRunner:
    """适配当前手搓 workflow 的 runner。"""

    name = "legacy"

    def run(self, schema: str, question: str, history: list[dict]) -> WorkflowResult:
        trace = ["legacy.router"]
        try:
            answer, chart_config, raw_rows = router.run(schema, question, history)
        except Exception as exc:
            return WorkflowResult(
                answer="",
                chart_config=None,
                raw_rows=[],
                trace=trace,
                error=str(exc),
            )

        return WorkflowResult(
            answer=answer,
            chart_config=chart_config,
            raw_rows=raw_rows,
            trace=trace,
        )


class LangGraphWorkflowRunner:
    """用 LangGraph 表达 router 编排的 runner。"""

    name = "langgraph"

    def run(self, schema: str, question: str, history: list[dict]) -> WorkflowResult:
        from src.agent_runtime.graph import run_router_graph

        try:
            return run_router_graph(schema, question, history)
        except Exception as exc:
            trace = ["langgraph.error"]
            return WorkflowResult(
                answer="",
                chart_config=None,
                raw_rows=[],
                trace=trace,
                error=str(exc),
                debug={
                    "trace": trace,
                    "retry_count": 0,
                    "error_node": "langgraph",
                },
            )


def get_runner(name: str = "legacy") -> WorkflowRunner:
    """按名称返回 runner。

    main 分支默认使用 langgraph，legacy 保留为历史实现适配。
    """
    normalized = name.strip().lower()
    if normalized == "legacy":
        return LegacyWorkflowRunner()
    if normalized == "langgraph":
        return LangGraphWorkflowRunner()
    raise ValueError(f"未知 runner：{name}")
