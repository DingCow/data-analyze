"""LangGraph 节点函数。

这一层只负责把现有 workflow 的步骤包装成 graph node，暂时不改任何
SQL / Analysis / Report 内部逻辑。
"""

from __future__ import annotations

from typing import Literal

from src.agent_runtime.state import AgentGraphState
from src.workflow import analysis, report, router, sql


def _append_trace(state: AgentGraphState, node_name: str) -> list[str]:
    """记录图执行路径，方便后续对比 legacy 和 langgraph。"""
    return [*state.get("trace", []), node_name]


def classify_node(state: AgentGraphState) -> AgentGraphState:
    """对应 router.run 的第一步：判断 simple / complex。"""
    intent = router.classify(state["question"])
    return {
        "intent": intent,
        "trace": _append_trace(state, "classify"),
    }


def route_by_intent(state: AgentGraphState) -> Literal["simple", "complex"]:
    """根据分类结果决定下一条边。"""
    return "complex" if state.get("intent") == "complex" else "simple"


def simple_sql_node(state: AgentGraphState) -> AgentGraphState:
    """simple 路径：只查数，不生成报告。"""
    try:
        raw_rows = sql.run(state["schema"], state["question"], state.get("history", []))
    except Exception as exc:
        return {
            "answer": "",
            "chart_config": None,
            "raw_rows": [],
            "error": str(exc),
            "error_node": "simple_sql",
            "trace": _append_trace(state, "simple_sql"),
        }

    return {
        "answer": "",
        "chart_config": None,
        "raw_rows": raw_rows,
        "trace": _append_trace(state, "simple_sql"),
    }


def decompose_node(state: AgentGraphState) -> AgentGraphState:
    """complex 路径第一步：把业务问题拆成查询任务。"""
    subtasks = analysis.decompose(state["schema"], state["question"])
    return {
        "subtasks": subtasks,
        "trace": _append_trace(state, "decompose"),
    }


def complex_sql_node(state: AgentGraphState) -> AgentGraphState:
    """complex 路径第二步：按拆解结果查询数据。"""
    guided_question = f"用户原始问题：{state['question']}\n\n需要查询的内容：\n{state['subtasks']}"
    try:
        raw_rows = sql.run(state["schema"], guided_question, state.get("history", []))
    except Exception as exc:
        return {
            "raw_rows": [],
            "error": str(exc),
            "error_node": "complex_sql",
            "trace": _append_trace(state, "complex_sql"),
        }

    return {
        "raw_rows": raw_rows,
        "error": None,
        "error_node": None,
        "trace": _append_trace(state, "complex_sql"),
    }


def repair_sql_node(state: AgentGraphState) -> AgentGraphState:
    """complex SQL 失败后的重试准备节点。

    这里先不引入新的 LLM 修复器，只把失败原因、原始问题和拆解任务重新组织成
    更明确的查询指令。这样能先学习图级恢复流程，不把改动扩大到 SQL Agent 内部。
    """
    retry_question = (
        f"用户原始问题：{state['question']}\n\n"
        f"上一次 SQL 查询失败，错误信息：{state.get('error', '')}\n\n"
        f"请根据错误信息修正查询思路，并完成以下查询任务：\n{state.get('subtasks', '')}"
    )
    return {
        "retry_question": retry_question,
        "trace": _append_trace(state, "repair_sql"),
    }


def retry_complex_sql_node(state: AgentGraphState) -> AgentGraphState:
    """complex SQL 图级重试节点，目前只重试一次。"""
    try:
        raw_rows = sql.run(state["schema"], state["retry_question"], state.get("history", []))
    except Exception as exc:
        return {
            "raw_rows": [],
            "error": str(exc),
            "error_node": "retry_complex_sql",
            "retry_count": state.get("retry_count", 0) + 1,
            "trace": _append_trace(state, "retry_complex_sql"),
        }

    return {
        "raw_rows": raw_rows,
        "error": None,
        "error_node": None,
        "retry_count": state.get("retry_count", 0) + 1,
        "trace": _append_trace(state, "retry_complex_sql"),
    }


def prepare_analysis_input_node(state: AgentGraphState) -> AgentGraphState:
    """把查询结果整理成后置分析模型的输入。"""
    analysis_input = analysis.build_analysis_input(state["question"], state.get("raw_rows", []))
    return {
        "analysis_input": analysis_input,
        "trace": _append_trace(state, "prepare_analysis_input"),
    }


def analyze_data_node(state: AgentGraphState) -> AgentGraphState:
    """基于已经准备好的输入执行后置分析。"""
    conclusion = analysis.analyze_prepared(state["analysis_input"])
    return {
        "analysis_text": conclusion,
        "trace": _append_trace(state, "analyze_data"),
    }


def generate_report_payload_node(state: AgentGraphState) -> AgentGraphState:
    """生成包含 Markdown 和图表配置的报告对象。"""
    report_input = report.build_report_input(
        state["question"],
        state.get("analysis_text", ""),
        state.get("raw_rows", []),
    )
    payload = report.generate_report_payload(report_input)
    return {
        "report_payload": payload,
        "trace": _append_trace(state, "generate_report_payload"),
    }


def generate_markdown_report_node(state: AgentGraphState) -> AgentGraphState:
    """从报告对象中提取 Markdown 报告。"""
    markdown = report.extract_markdown(state.get("report_payload", {}))
    return {
        "answer": markdown,
        "trace": _append_trace(state, "generate_markdown_report"),
    }


def generate_chart_config_node(state: AgentGraphState) -> AgentGraphState:
    """从报告对象中提取图表配置。"""
    chart_config = report.extract_chart_config(state.get("report_payload", {}))
    return {
        "chart_config": chart_config,
        "trace": _append_trace(state, "generate_chart_config"),
    }


def route_after_simple_sql(state: AgentGraphState) -> Literal["error", "finalize"]:
    """SQL 节点失败时进入错误收口，否则结束 simple 路径。"""
    return "error" if state.get("error") else "finalize"


def route_after_complex_sql(state: AgentGraphState) -> Literal["repair_sql", "prepare_analysis_input"]:
    """complex SQL 失败时先进入图级修复节点，而不是直接收口。"""
    return "repair_sql" if state.get("error") else "prepare_analysis_input"


def route_after_retry_complex_sql(state: AgentGraphState) -> Literal["error", "prepare_analysis_input"]:
    """重试仍失败才进入错误收口；重试成功则回到分析链路。"""
    return "error" if state.get("error") else "prepare_analysis_input"


def error_node(state: AgentGraphState) -> AgentGraphState:
    """图内部错误收口节点，先保留错误信息，后续可扩展修复或重试。"""
    return {
        "answer": "",
        "chart_config": None,
        "raw_rows": state.get("raw_rows", []),
        "trace": _append_trace(state, "error"),
    }


def finalize_node(state: AgentGraphState) -> AgentGraphState:
    """统一收口节点，后续可以在这里补错误收敛或结果标准化。"""
    return {
        "trace": _append_trace(state, "finalize"),
    }
