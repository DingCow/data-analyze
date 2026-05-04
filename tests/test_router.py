import unittest
from unittest.mock import patch

import main
from rich.table import Table
from src import llm
from src.workflow import analysis
from src.workflow import report
from src.workflow import router
from src.workflow import sql


class TestRouter(unittest.TestCase):
    """验证路由编排是否按预期调用各 Agent。"""

    @patch("src.workflow.router.sql.run")
    @patch("src.workflow.router.classify")
    def test_simple_question_uses_sql_path_only(self, mock_classify, mock_sql_run):
        mock_classify.return_value = "simple"
        mock_sql_run.return_value = [{"value": 1}]

        answer, chart_config, raw_rows = router.run("fake schema", "查一条数据", [])

        self.assertEqual(answer, "")
        self.assertIsNone(chart_config)
        self.assertEqual(raw_rows, [{"value": 1}])
        mock_sql_run.assert_called_once_with("fake schema", "查一条数据", [])

    @patch("src.workflow.router.report.run")
    @patch("src.workflow.router.analysis.analyze")
    @patch("src.workflow.router.sql.run")
    @patch("src.workflow.router.analysis.decompose")
    @patch("src.workflow.router.classify")
    def test_complex_question_uses_full_pipeline(
        self,
        mock_classify,
        mock_decompose,
        mock_sql_run,
        mock_analyze,
        mock_report_run,
    ):
        mock_classify.return_value = "complex"
        mock_decompose.return_value = "最终查询目标：按月汇总收入"
        mock_sql_run.return_value = [{"月份": "2024-01", "收入": 100}]
        mock_analyze.return_value = ("收入整体上升", [{"月份": "2024-01", "收入": 100}])
        mock_report_run.return_value = (
            "## 结论\n收入整体上升",
            {"type": "line", "x": "月份", "y": ["收入"], "title": "收入趋势"},
        )

        answer, chart_config, raw_rows = router.run("fake schema", "分析收入趋势", [])

        self.assertEqual(answer, "## 结论\n收入整体上升")
        self.assertEqual(chart_config["type"], "line")
        self.assertEqual(raw_rows, [{"月份": "2024-01", "收入": 100}])
        mock_decompose.assert_called_once_with("fake schema", "分析收入趋势")
        mock_sql_run.assert_called_once()
        mock_analyze.assert_called_once_with("分析收入趋势", [{"月份": "2024-01", "收入": 100}])
        mock_report_run.assert_called_once_with(
            "分析收入趋势",
            "收入整体上升",
            [{"月份": "2024-01", "收入": 100}],
        )


if __name__ == "__main__":
    unittest.main()


class TestCliRendering(unittest.TestCase):
    """验证 CLI 在 simple 路径下也会展示查询结果。"""

    def test_render_result_falls_back_to_raw_rows_when_answer_is_empty(self):
        with patch.object(main.console, "print") as mock_print:
            main.render_result("", [{"value": 1}, {"value": 2}])

        self.assertEqual(mock_print.call_count, 1)
        self.assertIsInstance(mock_print.call_args.args[0], Table)


class TestSqlAgent(unittest.TestCase):
    """验证 SQL Agent 不会把旧中间结果误当成最终结果。"""

    @patch("src.workflow.sql.execute_tool_with_data")
    @patch("src.workflow.sql.client.chat.completions.create")
    def test_run_returns_empty_when_final_query_result_is_empty(
        self,
        mock_create,
        mock_execute_tool,
    ):
        class FakeToolFunction:
            def __init__(self, name, arguments):
                self.name = name
                self.arguments = arguments

        class FakeToolCall:
            def __init__(self, call_id, name, arguments):
                self.id = call_id
                self.function = FakeToolFunction(name, arguments)

        class FakeMessage:
            def __init__(self, content=None, tool_calls=None):
                self.content = content
                self.tool_calls = tool_calls or []

        class FakeChoice:
            def __init__(self, finish_reason, message):
                self.finish_reason = finish_reason
                self.message = message

        class FakeResponse:
            def __init__(self, choice):
                self.choices = [choice]

        mock_create.side_effect = [
            FakeResponse(
                FakeChoice(
                    "tool_calls",
                    FakeMessage(
                        tool_calls=[FakeToolCall("call_1", "run_sql", '{"sql":"SELECT 1"}')]
                    ),
                )
            ),
            FakeResponse(
                FakeChoice(
                    "tool_calls",
                    FakeMessage(
                        tool_calls=[FakeToolCall("call_2", "run_sql", '{"sql":"SELECT 2"}')]
                    ),
                )
            ),
            FakeResponse(FakeChoice("stop", FakeMessage(content="查询完成"))),
        ]

        mock_execute_tool.side_effect = [
            ("中间查询结果", [{"value": 1}]),
            ("查询结果为空（0行）", []),
        ]

        result = sql.run("fake schema", "测试问题", [])

        self.assertEqual(result, [])
        self.assertEqual(mock_create.call_args_list[0].kwargs["model"], llm.FAST_MODEL)
        self.assertEqual(mock_create.call_args_list[0].kwargs["extra_body"], llm.NON_THINKING_EXTRA_BODY)


class TestModelConfiguration(unittest.TestCase):
    """验证各 Agent 已切换到 DeepSeek 新模型配置。"""

    @patch("src.workflow.router.client.chat.completions.create")
    def test_router_uses_fast_model_without_thinking(self, mock_create):
        class FakeMessage:
            content = "simple"

        class FakeChoice:
            message = FakeMessage()

        class FakeResponse:
            choices = [FakeChoice()]

        mock_create.return_value = FakeResponse()

        self.assertEqual(router.classify("查一下订单数"), "simple")
        self.assertEqual(mock_create.call_args.kwargs["model"], llm.FAST_MODEL)
        self.assertEqual(mock_create.call_args.kwargs["extra_body"], llm.NON_THINKING_EXTRA_BODY)

    @patch("src.workflow.analysis.client.chat.completions.create")
    def test_analysis_uses_reasoning_model_with_thinking(self, mock_create):
        class FakeMessage:
            content = "最终查询目标：按城市汇总收入"

        class FakeChoice:
            message = FakeMessage()

        class FakeResponse:
            choices = [FakeChoice()]

        mock_create.return_value = FakeResponse()

        result = analysis.decompose("fake schema", "分析收入变化")

        self.assertIn("最终查询目标", result)
        self.assertEqual(mock_create.call_args.kwargs["model"], llm.REASONING_MODEL)
        self.assertEqual(mock_create.call_args.kwargs["extra_body"], llm.THINKING_EXTRA_BODY)
        self.assertEqual(mock_create.call_args.kwargs["reasoning_effort"], llm.THINKING_REASONING_EFFORT)
        self.assertNotIn("temperature", mock_create.call_args.kwargs)

    @patch("src.workflow.report.client.chat.completions.create")
    def test_report_uses_fast_model_without_thinking(self, mock_create):
        class FakeMessage:
            content = '{"markdown":"## 结论\\n收入下降","chart":null}'

        class FakeChoice:
            message = FakeMessage()

        class FakeResponse:
            choices = [FakeChoice()]

        mock_create.return_value = FakeResponse()

        markdown, chart_config = report.run("分析收入", "收入下降", [{"城市": "中山", "收入": 100}])

        self.assertIn("收入下降", markdown)
        self.assertIsNone(chart_config)
        self.assertEqual(mock_create.call_args.kwargs["model"], llm.FAST_MODEL)
        self.assertEqual(mock_create.call_args.kwargs["extra_body"], llm.NON_THINKING_EXTRA_BODY)

