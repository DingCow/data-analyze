"""Agent runtime 统一入口。

这一层把 legacy 和当前 LangGraph 主线收敛到同一个运行接口，
方便入口层保持稳定。
"""

from src.agent_runtime.runners import LegacyWorkflowRunner, WorkflowRunner, get_runner
from src.agent_runtime.state import WorkflowResult

__all__ = [
    "LegacyWorkflowRunner",
    "WorkflowResult",
    "WorkflowRunner",
    "get_runner",
]
