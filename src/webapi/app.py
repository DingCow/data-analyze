"""FastAPI Web 服务：把现有分析链路包装成最小 HTTP 接口。"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from src import db
from src.agent_runtime import get_runner


class ConversationMessage(BaseModel):
    """前端多轮对话中的单条消息。"""

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class AnalyzeRequest(BaseModel):
    """分析请求体。"""

    question: str
    history: list[ConversationMessage] = Field(default_factory=list)


class AnalyzeResponse(BaseModel):
    """统一分析响应。"""

    answer: str
    chart_config: dict[str, Any] | None
    raw_rows: list[dict[str, Any]]
    db_error: str | None


class SchemaResponse(BaseModel):
    """Schema 查询响应。"""

    model_config = ConfigDict(populate_by_name=True)

    schema_text: str = Field(alias="schema")
    db_error: str | None


class HealthResponse(BaseModel):
    """健康检查响应。"""

    status: str
    db_readable: bool
    db_error: str | None


def load_schema_with_error() -> tuple[str, str | None]:
    """读取 schema，同时把数据库异常转成接口层可返回的错误文本。"""
    try:
        return db.get_schema(), None
    except Exception as exc:  # pragma: no cover - 这里只负责把错误往上翻译
        return "", str(exc)


app = FastAPI(title="Data Analyze API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """检查服务和数据库是否可读。"""
    _, db_error = load_schema_with_error()
    return HealthResponse(
        status="ok",
        db_readable=db_error is None,
        db_error=db_error,
    )


@app.get("/api/schema", response_model=SchemaResponse)
def get_schema() -> SchemaResponse:
    """返回 schema 文本，供前端做状态确认。"""
    schema, db_error = load_schema_with_error()
    return SchemaResponse(schema_text=schema, db_error=db_error)


@app.post("/api/analyze", response_model=AnalyzeResponse)
def analyze(payload: AnalyzeRequest) -> AnalyzeResponse:
    """把自然语言问题交给既有 Router 链路。"""
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="question 不能为空")

    schema, db_error = load_schema_with_error()
    if db_error:
        return AnalyzeResponse(
            answer="",
            chart_config=None,
            raw_rows=[],
            db_error=db_error,
        )

    runner = get_runner("legacy")
    result = runner.run(
        schema,
        question,
        [message.model_dump() for message in payload.history],
    )

    return AnalyzeResponse(
        **result.as_api_payload(),
    )
