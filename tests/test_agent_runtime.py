import unittest
from unittest.mock import patch

from src.agent_runtime import get_runner
from src.agent_runtime.nodes import (
    analyze_data_node,
    generate_chart_config_node,
    generate_markdown_report_node,
    generate_report_payload_node,
    prepare_analysis_input_node,
    repair_sql_node,
    retry_complex_sql_node,
)
from src.agent_runtime.runners import LangGraphWorkflowRunner


class TestAgentRuntime(unittest.TestCase):
    """验证 LangGraph runner 已注册到统一运行入口。"""

    def test_get_runner_returns_langgraph_runner(self):
        runner = get_runner("langgraph")

        self.assertIsInstance(runner, LangGraphWorkflowRunner)
        self.assertEqual(runner.name, "langgraph")


class TestLangGraphRunner(unittest.TestCase):
    """验证 LangGraph 版 router 编排自身的路径和输出契约。"""

    @patch("src.agent_runtime.nodes.report.extract_chart_config")
    @patch("src.agent_runtime.nodes.report.extract_markdown")
    @patch("src.agent_runtime.nodes.report.generate_report_payload")
    @patch("src.agent_runtime.nodes.report.build_report_input")
    @patch("src.agent_runtime.nodes.analysis.analyze_prepared")
    @patch("src.agent_runtime.nodes.analysis.build_analysis_input")
    @patch("src.agent_runtime.nodes.analysis.decompose")
    @patch("src.agent_runtime.nodes.sql.run")
    @patch("src.agent_runtime.nodes.router.classify")
    def test_langgraph_runner_uses_simple_sql_path(
        self,
        mock_classify,
        mock_sql_run,
        mock_decompose,
        mock_build_analysis_input,
        mock_analyze_prepared,
        mock_build_report_input,
        mock_generate_report_payload,
        mock_extract_markdown,
        mock_extract_chart_config,
    ):
        mock_classify.return_value = "simple"
        mock_sql_run.return_value = [{"value": 1}]

        result = LangGraphWorkflowRunner().run("fake schema", "查一条数据", [])

        mock_classify.assert_called_once_with("查一条数据")
        mock_sql_run.assert_called_once_with("fake schema", "查一条数据", [])
        mock_decompose.assert_not_called()
        mock_build_analysis_input.assert_not_called()
        mock_analyze_prepared.assert_not_called()
        mock_build_report_input.assert_not_called()
        mock_generate_report_payload.assert_not_called()
        mock_extract_markdown.assert_not_called()
        mock_extract_chart_config.assert_not_called()
        self.assertEqual(result.intent, "simple")
        self.assertEqual(result.answer, "")
        self.assertIsNone(result.chart_config)
        self.assertEqual(result.raw_rows, [{"value": 1}])
        self.assertEqual(result.trace, ["classify", "simple_sql", "finalize"])
        self.assertIsNone(result.error)
        self.assertEqual(
            result.debug,
            {
                "trace": ["classify", "simple_sql", "finalize"],
                "retry_count": 0,
                "error_node": None,
            },
        )

    @patch("src.agent_runtime.nodes.report.extract_chart_config")
    @patch("src.agent_runtime.nodes.report.extract_markdown")
    @patch("src.agent_runtime.nodes.report.generate_report_payload")
    @patch("src.agent_runtime.nodes.report.build_report_input")
    @patch("src.agent_runtime.nodes.analysis.analyze_prepared")
    @patch("src.agent_runtime.nodes.analysis.build_analysis_input")
    @patch("src.agent_runtime.nodes.sql.run")
    @patch("src.agent_runtime.nodes.analysis.decompose")
    @patch("src.agent_runtime.nodes.router.classify")
    def test_langgraph_runner_uses_complex_pipeline(
        self,
        mock_classify,
        mock_decompose,
        mock_sql_run,
        mock_build_analysis_input,
        mock_analyze_prepared,
        mock_build_report_input,
        mock_generate_report_payload,
        mock_extract_markdown,
        mock_extract_chart_config,
    ):
        mock_classify.return_value = "complex"
        mock_decompose.return_value = "最终查询目标：按月汇总收入"
        mock_sql_run.return_value = [{"月份": "2024-01", "收入": 100}]
        mock_build_analysis_input.return_value = "准备好的分析输入"
        mock_analyze_prepared.return_value = "收入整体上升"
        mock_build_report_input.return_value = "准备好的报告输入"
        mock_generate_report_payload.return_value = {
            "markdown": "## 结论\n收入整体上升",
            "chart": {"type": "line", "x": "月份", "y": ["收入"], "title": "收入趋势"},
        }
        mock_extract_markdown.return_value = "## 结论\n收入整体上升"
        mock_extract_chart_config.return_value = {
            "type": "line",
            "x": "月份",
            "y": ["收入"],
            "title": "收入趋势",
        }

        result = LangGraphWorkflowRunner().run("fake schema", "分析收入趋势", [])

        self.assertEqual(result.intent, "complex")
        self.assertEqual(result.answer, "## 结论\n收入整体上升")
        self.assertEqual(
            result.chart_config,
            {"type": "line", "x": "月份", "y": ["收入"], "title": "收入趋势"},
        )
        self.assertEqual(result.raw_rows, [{"月份": "2024-01", "收入": 100}])
        self.assertEqual(
            result.trace,
            [
                "classify",
                "decompose",
                "complex_sql",
                "prepare_analysis_input",
                "analyze_data",
                "generate_report_payload",
                "generate_markdown_report",
                "generate_chart_config",
                "finalize",
            ],
        )
        self.assertIsNone(result.error)
        self.assertEqual(result.debug["trace"], result.trace)
        self.assertEqual(result.debug["retry_count"], 0)
        self.assertIsNone(result.debug["error_node"])
        mock_classify.assert_called_once_with("分析收入趋势")
        mock_decompose.assert_called_once_with("fake schema", "分析收入趋势")
        mock_sql_run.assert_called_once()
        mock_build_analysis_input.assert_called_once_with(
            "分析收入趋势",
            [{"月份": "2024-01", "收入": 100}],
        )
        mock_analyze_prepared.assert_called_once_with("准备好的分析输入")
        mock_build_report_input.assert_called_once_with(
            "分析收入趋势",
            "收入整体上升",
            [{"月份": "2024-01", "收入": 100}],
        )
        mock_generate_report_payload.assert_called_once_with("准备好的报告输入")
        report_payload = {
            "markdown": "## 结论\n收入整体上升",
            "chart": {"type": "line", "x": "月份", "y": ["收入"], "title": "收入趋势"},
        }
        mock_extract_markdown.assert_called_once_with(report_payload)
        mock_extract_chart_config.assert_called_once_with(report_payload)

    @patch("src.agent_runtime.nodes.router.classify")
    def test_langgraph_runner_converts_node_exception_to_result_error(self, mock_classify):
        mock_classify.side_effect = RuntimeError("模拟异常")

        result = LangGraphWorkflowRunner().run("fake schema", "查一条数据", [])

        self.assertEqual(result.answer, "")
        self.assertIsNone(result.chart_config)
        self.assertEqual(result.raw_rows, [])
        self.assertEqual(result.trace, ["langgraph.error"])
        self.assertIn("模拟异常", result.error)
        self.assertEqual(
            result.debug,
            {
                "trace": ["langgraph.error"],
                "retry_count": 0,
                "error_node": "langgraph",
            },
        )

    @patch("src.agent_runtime.nodes.report.extract_chart_config")
    @patch("src.agent_runtime.nodes.report.extract_markdown")
    @patch("src.agent_runtime.nodes.report.generate_report_payload")
    @patch("src.agent_runtime.nodes.report.build_report_input")
    @patch("src.agent_runtime.nodes.analysis.analyze_prepared")
    @patch("src.agent_runtime.nodes.analysis.build_analysis_input")
    @patch("src.agent_runtime.nodes.analysis.decompose")
    @patch("src.agent_runtime.nodes.sql.run")
    @patch("src.agent_runtime.nodes.router.classify")
    def test_langgraph_routes_simple_sql_error_through_error_node(
        self,
        mock_classify,
        mock_sql_run,
        mock_decompose,
        mock_build_analysis_input,
        mock_analyze_prepared,
        mock_build_report_input,
        mock_generate_report_payload,
        mock_extract_markdown,
        mock_extract_chart_config,
    ):
        mock_classify.return_value = "simple"
        mock_sql_run.side_effect = RuntimeError("SQL 执行失败")

        result = LangGraphWorkflowRunner().run("fake schema", "查一条数据", [])

        mock_sql_run.assert_called_once_with("fake schema", "查一条数据", [])
        mock_decompose.assert_not_called()
        mock_build_analysis_input.assert_not_called()
        mock_analyze_prepared.assert_not_called()
        mock_build_report_input.assert_not_called()
        mock_generate_report_payload.assert_not_called()
        mock_extract_markdown.assert_not_called()
        mock_extract_chart_config.assert_not_called()
        self.assertEqual(result.intent, "simple")
        self.assertEqual(result.answer, "")
        self.assertIsNone(result.chart_config)
        self.assertEqual(result.raw_rows, [])
        self.assertEqual(result.trace, ["classify", "simple_sql", "error", "finalize"])
        self.assertEqual(result.error, "SQL 执行失败")
        self.assertEqual(result.debug["trace"], result.trace)
        self.assertEqual(result.debug["retry_count"], 0)
        self.assertEqual(result.debug["error_node"], "simple_sql")

    @patch("src.agent_runtime.nodes.report.extract_chart_config")
    @patch("src.agent_runtime.nodes.report.extract_markdown")
    @patch("src.agent_runtime.nodes.report.generate_report_payload")
    @patch("src.agent_runtime.nodes.report.build_report_input")
    @patch("src.agent_runtime.nodes.analysis.analyze_prepared")
    @patch("src.agent_runtime.nodes.analysis.build_analysis_input")
    @patch("src.agent_runtime.nodes.sql.run")
    @patch("src.agent_runtime.nodes.analysis.decompose")
    @patch("src.agent_runtime.nodes.router.classify")
    def test_langgraph_retries_complex_sql_error_and_continues_pipeline(
        self,
        mock_classify,
        mock_decompose,
        mock_sql_run,
        mock_build_analysis_input,
        mock_analyze_prepared,
        mock_build_report_input,
        mock_generate_report_payload,
        mock_extract_markdown,
        mock_extract_chart_config,
    ):
        mock_classify.return_value = "complex"
        mock_decompose.return_value = "最终查询目标：按月汇总收入"
        mock_sql_run.side_effect = [
            RuntimeError("SQL 执行失败"),
            [{"月份": "2024-01", "收入": 100}],
        ]
        mock_build_analysis_input.return_value = "准备好的分析输入"
        mock_analyze_prepared.return_value = "收入整体上升"
        mock_build_report_input.return_value = "准备好的报告输入"
        mock_generate_report_payload.return_value = {
            "markdown": "## 结论\n收入整体上升",
            "chart": {"type": "line", "x": "月份", "y": ["收入"], "title": "收入趋势"},
        }
        mock_extract_markdown.return_value = "## 结论\n收入整体上升"
        mock_extract_chart_config.return_value = {
            "type": "line",
            "x": "月份",
            "y": ["收入"],
            "title": "收入趋势",
        }

        result = LangGraphWorkflowRunner().run("fake schema", "分析收入趋势", [])

        mock_decompose.assert_called_once_with("fake schema", "分析收入趋势")
        self.assertEqual(mock_sql_run.call_count, 2)
        retry_question = mock_sql_run.call_args_list[1].args[1]
        self.assertIn("SQL 执行失败", retry_question)
        self.assertIn("最终查询目标：按月汇总收入", retry_question)
        mock_build_analysis_input.assert_called_once_with(
            "分析收入趋势",
            [{"月份": "2024-01", "收入": 100}],
        )
        mock_analyze_prepared.assert_called_once_with("准备好的分析输入")
        mock_build_report_input.assert_called_once_with(
            "分析收入趋势",
            "收入整体上升",
            [{"月份": "2024-01", "收入": 100}],
        )
        mock_generate_report_payload.assert_called_once_with("准备好的报告输入")
        report_payload = {
            "markdown": "## 结论\n收入整体上升",
            "chart": {"type": "line", "x": "月份", "y": ["收入"], "title": "收入趋势"},
        }
        mock_extract_markdown.assert_called_once_with(report_payload)
        mock_extract_chart_config.assert_called_once_with(report_payload)
        self.assertEqual(result.intent, "complex")
        self.assertEqual(result.answer, "## 结论\n收入整体上升")
        self.assertEqual(
            result.chart_config,
            {"type": "line", "x": "月份", "y": ["收入"], "title": "收入趋势"},
        )
        self.assertEqual(result.raw_rows, [{"月份": "2024-01", "收入": 100}])
        self.assertEqual(
            result.trace,
            [
                "classify",
                "decompose",
                "complex_sql",
                "repair_sql",
                "retry_complex_sql",
                "prepare_analysis_input",
                "analyze_data",
                "generate_report_payload",
                "generate_markdown_report",
                "generate_chart_config",
                "finalize",
            ],
        )
        self.assertIsNone(result.error)
        self.assertEqual(result.debug["trace"], result.trace)
        self.assertEqual(result.debug["retry_count"], 1)
        self.assertIsNone(result.debug["error_node"])

    @patch("src.agent_runtime.nodes.report.extract_chart_config")
    @patch("src.agent_runtime.nodes.report.extract_markdown")
    @patch("src.agent_runtime.nodes.report.generate_report_payload")
    @patch("src.agent_runtime.nodes.report.build_report_input")
    @patch("src.agent_runtime.nodes.analysis.analyze_prepared")
    @patch("src.agent_runtime.nodes.analysis.build_analysis_input")
    @patch("src.agent_runtime.nodes.sql.run")
    @patch("src.agent_runtime.nodes.analysis.decompose")
    @patch("src.agent_runtime.nodes.router.classify")
    def test_langgraph_routes_complex_sql_retry_error_through_error_node(
        self,
        mock_classify,
        mock_decompose,
        mock_sql_run,
        mock_build_analysis_input,
        mock_analyze_prepared,
        mock_build_report_input,
        mock_generate_report_payload,
        mock_extract_markdown,
        mock_extract_chart_config,
    ):
        mock_classify.return_value = "complex"
        mock_decompose.return_value = "最终查询目标：按月汇总收入"
        mock_sql_run.side_effect = [
            RuntimeError("SQL 第一次失败"),
            RuntimeError("SQL 第二次失败"),
        ]

        result = LangGraphWorkflowRunner().run("fake schema", "分析收入趋势", [])

        mock_decompose.assert_called_once_with("fake schema", "分析收入趋势")
        self.assertEqual(mock_sql_run.call_count, 2)
        mock_build_analysis_input.assert_not_called()
        mock_analyze_prepared.assert_not_called()
        mock_build_report_input.assert_not_called()
        mock_generate_report_payload.assert_not_called()
        mock_extract_markdown.assert_not_called()
        mock_extract_chart_config.assert_not_called()
        self.assertEqual(result.intent, "complex")
        self.assertEqual(result.answer, "")
        self.assertIsNone(result.chart_config)
        self.assertEqual(result.raw_rows, [])
        self.assertEqual(
            result.trace,
            [
                "classify",
                "decompose",
                "complex_sql",
                "repair_sql",
                "retry_complex_sql",
                "error",
                "finalize",
            ],
        )
        self.assertEqual(result.error, "SQL 第二次失败")
        self.assertEqual(result.debug["trace"], result.trace)
        self.assertEqual(result.debug["retry_count"], 1)
        self.assertEqual(result.debug["error_node"], "retry_complex_sql")


class TestLangGraphNodes(unittest.TestCase):
    """验证新增 LangGraph 节点自己的输入输出契约。"""

    def test_repair_sql_node_builds_retry_question(self):
        state = {
            "question": "分析收入趋势",
            "subtasks": "最终查询目标：按月汇总收入",
            "error": "no such column: revenue",
            "trace": ["classify", "decompose", "complex_sql"],
        }

        result = repair_sql_node(state)

        self.assertIn("分析收入趋势", result["retry_question"])
        self.assertIn("最终查询目标：按月汇总收入", result["retry_question"])
        self.assertIn("no such column: revenue", result["retry_question"])
        self.assertEqual(
            result["trace"],
            ["classify", "decompose", "complex_sql", "repair_sql"],
        )

    @patch("src.agent_runtime.nodes.sql.run")
    def test_retry_complex_sql_node_returns_rows_and_clears_error(self, mock_sql_run):
        mock_sql_run.return_value = [{"月份": "2024-01", "收入": 100}]
        state = {
            "schema": "fake schema",
            "retry_question": "修正后的查询任务",
            "history": [],
            "error": "SQL 第一次失败",
            "trace": ["classify", "decompose", "complex_sql", "repair_sql"],
        }

        result = retry_complex_sql_node(state)

        mock_sql_run.assert_called_once_with("fake schema", "修正后的查询任务", [])
        self.assertEqual(result["raw_rows"], [{"月份": "2024-01", "收入": 100}])
        self.assertIsNone(result["error"])
        self.assertIsNone(result["error_node"])
        self.assertEqual(result["retry_count"], 1)
        self.assertEqual(
            result["trace"],
            ["classify", "decompose", "complex_sql", "repair_sql", "retry_complex_sql"],
        )

    @patch("src.agent_runtime.nodes.sql.run")
    def test_retry_complex_sql_node_records_retry_error(self, mock_sql_run):
        mock_sql_run.side_effect = RuntimeError("SQL 第二次失败")
        state = {
            "schema": "fake schema",
            "retry_question": "修正后的查询任务",
            "history": [],
            "error": "SQL 第一次失败",
            "trace": ["classify", "decompose", "complex_sql", "repair_sql"],
        }

        result = retry_complex_sql_node(state)

        mock_sql_run.assert_called_once_with("fake schema", "修正后的查询任务", [])
        self.assertEqual(result["raw_rows"], [])
        self.assertEqual(result["error"], "SQL 第二次失败")
        self.assertEqual(result["error_node"], "retry_complex_sql")
        self.assertEqual(result["retry_count"], 1)
        self.assertEqual(
            result["trace"],
            ["classify", "decompose", "complex_sql", "repair_sql", "retry_complex_sql"],
        )

    @patch("src.agent_runtime.nodes.analysis.build_analysis_input")
    def test_prepare_analysis_input_node_builds_input(self, mock_build_analysis_input):
        mock_build_analysis_input.return_value = "准备好的分析输入"
        state = {
            "question": "分析收入趋势",
            "raw_rows": [{"月份": "2024-01", "收入": 100}],
            "trace": ["classify", "decompose", "complex_sql"],
        }

        result = prepare_analysis_input_node(state)

        mock_build_analysis_input.assert_called_once_with(
            "分析收入趋势",
            [{"月份": "2024-01", "收入": 100}],
        )
        self.assertEqual(result["analysis_input"], "准备好的分析输入")
        self.assertEqual(
            result["trace"],
            ["classify", "decompose", "complex_sql", "prepare_analysis_input"],
        )

    @patch("src.agent_runtime.nodes.analysis.analyze_prepared")
    def test_analyze_data_node_returns_analysis_text(self, mock_analyze_prepared):
        mock_analyze_prepared.return_value = "收入整体上升"
        state = {
            "analysis_input": "准备好的分析输入",
            "trace": ["classify", "decompose", "complex_sql", "prepare_analysis_input"],
        }

        result = analyze_data_node(state)

        mock_analyze_prepared.assert_called_once_with("准备好的分析输入")
        self.assertEqual(result["analysis_text"], "收入整体上升")
        self.assertEqual(
            result["trace"],
            [
                "classify",
                "decompose",
                "complex_sql",
                "prepare_analysis_input",
                "analyze_data",
            ],
        )

    @patch("src.agent_runtime.nodes.report.generate_report_payload")
    @patch("src.agent_runtime.nodes.report.build_report_input")
    def test_generate_report_payload_node_builds_payload(
        self,
        mock_build_report_input,
        mock_generate_report_payload,
    ):
        payload = {
            "markdown": "## 结论\n收入整体上升",
            "chart": {"type": "line", "x": "月份", "y": ["收入"], "title": "收入趋势"},
        }
        mock_build_report_input.return_value = "准备好的报告输入"
        mock_generate_report_payload.return_value = payload
        state = {
            "question": "分析收入趋势",
            "analysis_text": "收入整体上升",
            "raw_rows": [{"月份": "2024-01", "收入": 100}],
            "trace": ["classify", "decompose", "complex_sql", "prepare_analysis_input", "analyze_data"],
        }

        result = generate_report_payload_node(state)

        mock_build_report_input.assert_called_once_with(
            "分析收入趋势",
            "收入整体上升",
            [{"月份": "2024-01", "收入": 100}],
        )
        mock_generate_report_payload.assert_called_once_with("准备好的报告输入")
        self.assertEqual(result["report_payload"], payload)
        self.assertEqual(
            result["trace"],
            [
                "classify",
                "decompose",
                "complex_sql",
                "prepare_analysis_input",
                "analyze_data",
                "generate_report_payload",
            ],
        )

    @patch("src.agent_runtime.nodes.report.extract_markdown")
    def test_generate_markdown_report_node_extracts_answer(self, mock_extract_markdown):
        mock_extract_markdown.return_value = "## 结论\n收入整体上升"
        payload = {
            "markdown": "## 结论\n收入整体上升",
            "chart": {"type": "line", "x": "月份", "y": ["收入"], "title": "收入趋势"},
        }
        state = {
            "report_payload": payload,
            "trace": ["classify", "decompose", "complex_sql", "generate_report_payload"],
        }

        result = generate_markdown_report_node(state)

        mock_extract_markdown.assert_called_once_with(payload)
        self.assertEqual(result["answer"], "## 结论\n收入整体上升")
        self.assertEqual(
            result["trace"],
            [
                "classify",
                "decompose",
                "complex_sql",
                "generate_report_payload",
                "generate_markdown_report",
            ],
        )

    @patch("src.agent_runtime.nodes.report.extract_chart_config")
    def test_generate_chart_config_node_extracts_chart_config(self, mock_extract_chart_config):
        chart_config = {"type": "line", "x": "月份", "y": ["收入"], "title": "收入趋势"}
        payload = {
            "markdown": "## 结论\n收入整体上升",
            "chart": chart_config,
        }
        mock_extract_chart_config.return_value = chart_config
        state = {
            "report_payload": payload,
            "trace": [
                "classify",
                "decompose",
                "complex_sql",
                "generate_report_payload",
                "generate_markdown_report",
            ],
        }

        result = generate_chart_config_node(state)

        mock_extract_chart_config.assert_called_once_with(payload)
        self.assertEqual(result["chart_config"], chart_config)
        self.assertEqual(
            result["trace"],
            [
                "classify",
                "decompose",
                "complex_sql",
                "generate_report_payload",
                "generate_markdown_report",
                "generate_chart_config",
            ],
        )


if __name__ == "__main__":
    unittest.main()
