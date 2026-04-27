"""Agent 运行时共享数据结构。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class WorkflowResult:
    """统一工作流返回对象。

    现阶段 legacy runner 会适配成这个结构；后续 LangChain / LangGraph
    也必须返回同样字段，避免 CLI 和 Web 直接依赖某个具体框架。
    """

    answer: str
    chart_config: dict[str, Any] | None
    raw_rows: list[dict[str, Any]]
    intent: str | None = None
    trace: list[str] = field(default_factory=list)
    error: str | None = None

    def as_api_payload(self) -> dict[str, Any]:
        """转换成当前 FastAPI 响应需要的字段。"""
        return {
            "answer": self.answer,
            "chart_config": self.chart_config,
            "raw_rows": self.raw_rows,
            "db_error": self.error,
        }
