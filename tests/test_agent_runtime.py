import unittest
from unittest.mock import patch

from src.agent_runtime import LegacyWorkflowRunner, get_runner


class TestAgentRuntime(unittest.TestCase):
    """验证新运行时边界不会改变 legacy 工作流契约。"""

    def test_get_runner_returns_legacy_runner(self):
        runner = get_runner("legacy")

        self.assertIsInstance(runner, LegacyWorkflowRunner)
        self.assertEqual(runner.name, "legacy")

    @patch("src.agent_runtime.runners.router.run")
    def test_legacy_runner_wraps_router_result(self, mock_router_run):
        mock_router_run.return_value = (
            "## 结论\n收入上升",
            {"type": "line", "x": "月份", "y": ["收入"], "title": "收入趋势"},
            [{"月份": "2024-01", "收入": 100}],
        )

        result = LegacyWorkflowRunner().run("fake schema", "分析收入趋势", [])

        self.assertEqual(result.answer, "## 结论\n收入上升")
        self.assertEqual(result.chart_config["type"], "line")
        self.assertEqual(result.raw_rows, [{"月份": "2024-01", "收入": 100}])
        self.assertEqual(result.trace, ["legacy.router"])
        self.assertIsNone(result.error)

    @patch("src.agent_runtime.runners.router.run")
    def test_legacy_runner_converts_exception_to_result_error(self, mock_router_run):
        mock_router_run.side_effect = RuntimeError("数据库不可读")

        result = LegacyWorkflowRunner().run("fake schema", "查数据", [])

        self.assertEqual(result.answer, "")
        self.assertIsNone(result.chart_config)
        self.assertEqual(result.raw_rows, [])
        self.assertEqual(result.trace, ["legacy.router"])
        self.assertEqual(result.error, "数据库不可读")


if __name__ == "__main__":
    unittest.main()
