"use client";

import { CSSProperties, FormEvent, useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { PlotChart } from "../components/plot-chart";
import { analyzeQuestion, fetchSchemaStatus } from "../lib/api";
import { previewBoard, previewPayload } from "../lib/fixtures";
import {
  buildAssistantPreview,
  buildDisplayReportMarkdown,
  buildFollowUps,
  buildJudgmentBreakdown,
  buildProcessItems,
  summarizeAnswer,
} from "../lib/ui";
import { Message, ResultPayload, SchemaStatus } from "../lib/types";

const EMPTY_STATUS: SchemaStatus = {
  status: "loading",
  detail: "",
};

export default function Page() {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [latestResult, setLatestResult] = useState<ResultPayload | null>(null);
  const [schemaStatus, setSchemaStatus] = useState<SchemaStatus>(EMPTY_STATUS);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;

    async function refreshStatus() {
      const nextStatus = await fetchSchemaStatus();
      if (active) {
        setSchemaStatus(nextStatus);
        if (nextStatus.status === "online") {
          setError("");
        }
      }
    }

    refreshStatus();
    const timer = window.setInterval(() => {
      if (active) {
        refreshStatus();
      }
    }, 8000);

    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  const answerParts = useMemo(() => summarizeAnswer(latestResult?.answer ?? ""), [latestResult?.answer]);
  const displayReportMarkdown = useMemo(
    () => buildDisplayReportMarkdown(latestResult?.answer ?? ""),
    [latestResult?.answer],
  );
  const processItems = useMemo(() => buildProcessItems(messages, latestResult), [messages, latestResult]);
  const followUps = useMemo(() => buildFollowUps(latestResult), [latestResult]);
  const judgmentRows = useMemo(
    () => buildJudgmentBreakdown(latestResult, answerParts),
    [answerParts, latestResult],
  );
  const tableColumns = useMemo(
    () => (latestResult?.raw_rows[0] ? Object.keys(latestResult.raw_rows[0]) : []),
    [latestResult?.raw_rows],
  );
  const evidenceTableStyle = useMemo(() => {
    const columnCount = tableColumns.length || 3;
    const rowCount = latestResult?.raw_rows.length ?? 0;
    const fitWidth = Math.min(1020, Math.max(580, columnCount * 170 + 120));
    const rowPadding =
      rowCount <= 4 ? "11px 14px" :
      rowCount <= 8 ? "9px 12px" :
      "8px 10px";

    return {
      "--table-fit-width": `${fitWidth}px`,
      "--table-row-padding": rowPadding,
    } as CSSProperties;
  }, [latestResult?.raw_rows.length, tableColumns.length]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const trimmed = question.trim();
    if (!trimmed || loading) {
      return;
    }

    setLoading(true);
    setError("");

    const nextHistory = [...messages];
    try {
      const nextStatus = await fetchSchemaStatus();
      setSchemaStatus(nextStatus);
      if (nextStatus.status === "offline") {
        setError(nextStatus.detail || "数据源暂时不可用，请稍后再试。");
        return;
      }

      const result = await analyzeQuestion(trimmed, nextHistory);
      if (result.db_error) {
        setSchemaStatus({ status: "offline", detail: result.db_error });
        setError(result.db_error);
        setLatestResult(result);
        return;
      }

      const assistantPreview = buildAssistantPreview(result);
      setMessages([
        ...nextHistory,
        { role: "user", content: trimmed },
        { role: "assistant", content: assistantPreview },
      ]);
      setLatestResult(result);
      setQuestion("");
      setSchemaStatus({ status: "online", detail: "" });
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "分析请求失败");
    } finally {
      setLoading(false);
    }
  }

  function handlePreview() {
    setMessages(previewPayload.messages);
    setLatestResult(previewPayload.latest_result);
    setError("");
  }

  const statusText =
    schemaStatus.status === "loading"
      ? "正在检查数据源"
      : schemaStatus.status === "online"
        ? "数据源在线"
        : "数据源离线";

  return (
    <main className="page-shell">
      <section className="page">
        <header className="topbar">
          <div className="topbar-copy">
            <p className="eyebrow">+ 分析工作台</p>
            <h1>数据分析助手</h1>
            <p className="lede">
              从一个业务问题开始，快速得到结论、证据和下一步追问。
            </p>
          </div>
          <div className={`status-pill ${schemaStatus.status === "offline" ? "is-offline" : ""}`}>
            <span className="status-dot" />
            <span>{statusText}</span>
          </div>
        </header>

        <section className="input-panel">
          <div className="divider" />
          <form className="composer" onSubmit={handleSubmit}>
            <div className="composer-field">
              <span className="composer-badge">{latestResult ? "继续追问" : "就绪"}</span>
              <input
                aria-label="分析问题"
                className="composer-input"
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                placeholder={
                  latestResult
                    ? "继续追问：例如哪些表现较弱的城市，同时也出现了最明显的订单下滑？"
                    : "从一个业务判断开始：例如上个季度哪些城市的收入动能下滑最明显？"
                }
              />
            </div>
            <button className="primary-button" disabled={loading} type="submit">
              {loading ? "分析中..." : "开始分析"}
            </button>
            <button className="secondary-button" onClick={handlePreview} type="button">
              查看示例
            </button>
          </form>
          {(error || schemaStatus.detail) && (
            <p className="error-text">{error || schemaStatus.detail}</p>
          )}
        </section>

        {!latestResult && (
          <>
          <section className="empty-board">
            <div className="empty-copy">
              <p className="eyebrow">+ 开始分析</p>
              <h2>提出一个业务问题，系统会整理成一份可继续追问的分析页。</h2>
              <p>
                适合排查收入、订单、城市、渠道、时段等变化原因。
              </p>
              <div className="example-list" aria-label="可直接尝试的问题">
                {followUps.map((questionText) => (
                  <button key={questionText} onClick={() => setQuestion(questionText)} type="button">
                    {questionText}
                  </button>
                ))}
              </div>
            </div>
            <aside className="preview-grid" aria-label="结果结构">
              <p className="side-title">结果结构</p>
              {previewBoard.map((item) => (
                <article className="preview-metric" key={item.label}>
                  <span>{item.label}</span>
                  <strong>{item.value}</strong>
                </article>
              ))}
            </aside>
          </section>
          <p className="schema-strip">数据源 SQLite · 字段已读取 · 可开始分析</p>
          </>
        )}

        {latestResult && (
          <>
            <section className="hero-card">
              <p className="eyebrow">+ 结果概览</p>
              <h2>{answerParts.title}</h2>
              <p className="hero-summary">{answerParts.summary}</p>
              <div className="hero-metrics">
                <div>
                  <span>模式</span>
                  <strong>{latestResult.answer ? "多步分析" : "直接查询"}</strong>
                </div>
                <div>
                  <span>行数</span>
                  <strong>{latestResult.raw_rows.length}</strong>
                </div>
                <div>
                  <span>图形</span>
                  <strong>{latestResult.chart_config?.type ? "1 张图" : "未生成"}</strong>
                </div>
              </div>
            </section>

            <section className="two-column">
              <article className="panel-card">
                <p className="eyebrow">+ 分析过程</p>
                <div className="process-list">
                  {processItems.map((item) => (
                    <div className="process-item" key={item.meta}>
                      <p className="process-meta">{item.meta}</p>
                      <p className={`process-body ${item.tone}`}>{item.body}</p>
                    </div>
                  ))}
                </div>
              </article>
              <article className="panel-card">
                <p className="eyebrow">+ 判断拆解</p>
                <div className="judgment-list">
                  {judgmentRows.map((item) => (
                    <div className="judgment-row" key={item.label}>
                      <span>{item.label}</span>
                      <strong>{item.value}</strong>
                    </div>
                  ))}
                </div>
              </article>
            </section>

            <section className="evidence-grid">
              <article className="panel-card evidence-card evidence-combined">
                <div className="evidence-head">
                  <div>
                    <p className="eyebrow">+ 证据视图</p>
                    <h3 className="panel-title">{latestResult.chart_config?.title ?? "结构化结果视图"}</h3>
                  </div>
                  <div className="evidence-stats">
                    <span>{latestResult.chart_config?.type ? "图表 + 明细" : "明细表"}</span>
                    <strong>{latestResult.raw_rows.length} 行</strong>
                  </div>
                </div>
                <div className="chart-shell">
                  <PlotChart chartConfig={latestResult.chart_config} rows={latestResult.raw_rows} />
                  {!latestResult.chart_config?.type && (
                    <div className="empty-plot">这轮结果不适合直接画图，保留下方表格做明细确认。</div>
                  )}
                </div>
                <div className="table-shell compact-table" style={evidenceTableStyle}>
                  {latestResult.raw_rows.length > 0 ? (
                    <table>
                      <thead>
                        <tr>
                          {tableColumns.map((column) => (
                            <th key={column}>{column}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {latestResult.raw_rows.map((row, index) => (
                          <tr key={`${index}-${Object.values(row).join("-")}`}>
                            {tableColumns.map((column, columnIndex) => (
                              <td className={columnIndex > 0 ? "numeric-cell" : ""} key={column}>
                                {row[column] ?? ""}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : (
                    <div className="empty-plot">本轮没有查到结构化结果。</div>
                  )}
                </div>
                {latestResult.answer && (
                  <details className="report-details">
                    <summary>查看完整报告</summary>
                    <div className="markdown-body">
                      <ReactMarkdown
                        components={{
                          table: ({ children, node: _node, ...props }) => (
                            <div className="markdown-table-scroll">
                              <table {...props}>{children}</table>
                            </div>
                          ),
                        }}
                        remarkPlugins={[remarkGfm]}
                      >
                        {displayReportMarkdown}
                      </ReactMarkdown>
                    </div>
                  </details>
                )}
              </article>
            </section>

            <section className="follow-up-card">
              <p className="eyebrow">+ 下一步问题</p>
              <div className="follow-up-grid">
                {followUps.map((questionText) => (
                  <button
                    className="follow-up-item"
                    key={questionText}
                    onClick={() => setQuestion(questionText)}
                    type="button"
                  >
                    {questionText}
                  </button>
                ))}
              </div>
            </section>
          </>
        )}
      </section>
    </main>
  );
}
