"""LangGraph 版 router 编排。"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from src.agent_runtime.nodes import (
    analyze_data_node,
    classify_node,
    complex_sql_node,
    decompose_node,
    error_node,
    finalize_node,
    generate_chart_config_node,
    generate_markdown_report_node,
    generate_report_payload_node,
    prepare_analysis_input_node,
    route_after_complex_sql,
    route_after_retry_complex_sql,
    route_after_simple_sql,
    route_by_intent,
    repair_sql_node,
    retry_complex_sql_node,
    simple_sql_node,
)
from src.agent_runtime.state import AgentGraphState, WorkflowResult

_ROUTER_GRAPH = None


def build_router_graph():
    """把原 router.run 的 if/else 流程表达成状态图。"""
    builder = StateGraph(AgentGraphState)

    builder.add_node("classify", classify_node)
    builder.add_node("simple_sql", simple_sql_node)
    builder.add_node("decompose", decompose_node)
    builder.add_node("complex_sql", complex_sql_node)
    builder.add_node("repair_sql", repair_sql_node)
    builder.add_node("retry_complex_sql", retry_complex_sql_node)
    builder.add_node("prepare_analysis_input", prepare_analysis_input_node)
    builder.add_node("analyze_data", analyze_data_node)
    builder.add_node("generate_report_payload", generate_report_payload_node)
    builder.add_node("generate_markdown_report", generate_markdown_report_node)
    builder.add_node("generate_chart_config", generate_chart_config_node)
    builder.add_node("error", error_node)
    builder.add_node("finalize", finalize_node)

    builder.add_edge(START, "classify")
    builder.add_conditional_edges(
        "classify",
        route_by_intent,
        {
            "simple": "simple_sql",
            "complex": "decompose",
        },
    )
    builder.add_conditional_edges(
        "simple_sql",
        route_after_simple_sql,
        {
            "error": "error",
            "finalize": "finalize",
        },
    )
    builder.add_edge("decompose", "complex_sql")
    builder.add_conditional_edges(
        "complex_sql",
        route_after_complex_sql,
        {
            "repair_sql": "repair_sql",
            "prepare_analysis_input": "prepare_analysis_input",
        },
    )
    builder.add_edge("repair_sql", "retry_complex_sql")
    builder.add_conditional_edges(
        "retry_complex_sql",
        route_after_retry_complex_sql,
        {
            "error": "error",
            "prepare_analysis_input": "prepare_analysis_input",
        },
    )
    builder.add_edge("prepare_analysis_input", "analyze_data")
    builder.add_edge("analyze_data", "generate_report_payload")
    builder.add_edge("generate_report_payload", "generate_markdown_report")
    builder.add_edge("generate_markdown_report", "generate_chart_config")
    builder.add_edge("generate_chart_config", "finalize")
    builder.add_edge("error", "finalize")
    builder.add_edge("finalize", END)

    return builder.compile()


def get_router_graph():
    """复用已编译的 LangGraph 图，避免每次请求重复构建静态 DAG。"""
    global _ROUTER_GRAPH
    if _ROUTER_GRAPH is None:
        _ROUTER_GRAPH = build_router_graph()
    return _ROUTER_GRAPH


def run_router_graph(schema: str, question: str, history: list[dict]) -> WorkflowResult:
    """运行 LangGraph router，并转换成统一 WorkflowResult。"""
    graph = get_router_graph()
    final_state = graph.invoke(
        {
            "schema": schema,
            "question": question,
            "history": history,
            "trace": [],
            "retry_count": 0,
        }
    )
    trace = final_state.get("trace", [])
    retry_count = final_state.get("retry_count", 0)
    error_node = final_state.get("error_node")

    return WorkflowResult(
        answer=final_state.get("answer", ""),
        chart_config=final_state.get("chart_config"),
        raw_rows=final_state.get("raw_rows", []),
        intent=final_state.get("intent"),
        trace=trace,
        error=final_state.get("error"),
        debug={
            "trace": trace,
            "retry_count": retry_count,
            "error_node": error_node,
        },
    )
