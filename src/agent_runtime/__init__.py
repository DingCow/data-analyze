"""Agent runtime 统一入口。

这一层先不替代现有 workflow，而是把 legacy / LangChain / LangGraph
都收敛到同一个运行接口，方便后续逐步迁移。
"""

from src.agent_runtime.runners import LegacyWorkflowRunner, WorkflowRunner, get_runner
from src.agent_runtime.state import WorkflowResult

__all__ = [
    "LegacyWorkflowRunner",
    "WorkflowResult",
    "WorkflowRunner",
    "get_runner",
]
