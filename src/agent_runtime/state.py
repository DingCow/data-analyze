"""Agent 运行时共享数据结构。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TypedDict


@dataclass
class WorkflowResult:
    """统一工作流返回对象。

    legacy runner 和当前 LangGraph runner 都适配成这个结构，避免
    CLI 和 Web 直接依赖某个具体编排实现。
    """

    answer: str
    chart_config: dict[str, Any] | None
    raw_rows: list[dict[str, Any]]
    intent: str | None = None
    trace: list[str] = field(default_factory=list)
    error: str | None = None
    debug: dict[str, Any] = field(default_factory=dict)

    def as_api_payload(self) -> dict[str, Any]:
        """转换成当前 FastAPI 响应需要的字段。"""
        debug = self.debug or {
            "trace": self.trace,
            "retry_count": 0,
            "error_node": None,
        }
        return {
            "answer": self.answer,
            "chart_config": self.chart_config,
            "raw_rows": self.raw_rows,
            "db_error": self.error,
            "debug": debug,
        }


class AgentGraphState(TypedDict, total=False):
    """LangGraph 在节点之间传递的共享状态。

    可以把它理解成原来 router.run 里的局部变量集合，只是现在显式放进
    state，方便节点之间按字段交接数据。
    """

    schema: str
    question: str
    history: list[dict]
    intent: str
    subtasks: str
    retry_question: str
    raw_rows: list[dict[str, Any]]
    analysis_input: str
    analysis_text: str
    report_payload: dict[str, Any]
    answer: str
    chart_config: dict[str, Any] | None
    error: str | None
    error_node: str | None
    retry_count: int
    trace: list[str]
