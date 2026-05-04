import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.agent_runtime import WorkflowResult
from src.webapi.app import app


class TestApi(unittest.TestCase):
    """验证 FastAPI 薄包装层。"""

    def setUp(self):
        self.client = TestClient(app)

    @patch("src.webapi.app.load_schema_with_error")
    def test_health_returns_ok_when_db_is_readable(self, mock_load_schema):
        mock_load_schema.return_value = ("schema text", None)

        response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "ok", "db_readable": True, "db_error": None},
        )

    @patch("src.webapi.app.load_schema_with_error")
    def test_schema_returns_db_error_when_schema_load_fails(self, mock_load_schema):
        mock_load_schema.return_value = ("", "sqlite unavailable")

        response = self.client.get("/api/schema")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"schema": "", "db_error": "sqlite unavailable"},
        )

    @patch("src.webapi.app.get_runner")
    @patch("src.webapi.app.load_schema_with_error")
    def test_analyze_proxies_runner_result(self, mock_load_schema, mock_get_runner):
        class FakeRunner:
            def run(self, schema, question, history):
                return WorkflowResult(
                    answer="## 核心判断\n订单量下滑更明显。",
                    chart_config={"type": "bar", "x": "城市", "y": ["订单量"], "title": "对比"},
                    raw_rows=[{"城市": "中山", "订单量": 23822}],
                )

        mock_load_schema.return_value = ("schema text", None)
        fake_runner = FakeRunner()
        mock_get_runner.return_value = fake_runner
        with patch.object(fake_runner, "run", wraps=fake_runner.run) as mock_runner_run:
            response = self.client.post(
                "/api/analyze",
                json={
                    "question": "上个季度哪些城市的收入动能下滑最明显？",
                    "history": [{"role": "user", "content": "上一轮问题"}],
                },
            )

            mock_runner_run.assert_called_once_with(
                "schema text",
                "上个季度哪些城市的收入动能下滑最明显？",
                [{"role": "user", "content": "上一轮问题"}],
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "answer": "## 核心判断\n订单量下滑更明显。",
                "chart_config": {"type": "bar", "x": "城市", "y": ["订单量"], "title": "对比"},
                "raw_rows": [{"城市": "中山", "订单量": 23822}],
                "db_error": None,
                "debug": {
                    "trace": [],
                    "retry_count": 0,
                    "error_node": None,
                },
            },
        )
        mock_get_runner.assert_called_once_with("langgraph")

    def test_analyze_rejects_blank_question(self):
        response = self.client.post(
            "/api/analyze",
            json={"question": "   ", "history": []},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("question 不能为空", response.text)

    @patch("src.webapi.app.load_schema_with_error")
    def test_analyze_returns_db_error_when_schema_unavailable(self, mock_load_schema):
        mock_load_schema.return_value = ("", "sqlite unavailable")

        response = self.client.post(
            "/api/analyze",
            json={"question": "分析一下收入下滑", "history": []},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["db_error"], "sqlite unavailable")


if __name__ == "__main__":
    unittest.main()
