import { Message, ResultPayload } from "./types";

export type AnswerSummary = {
  title: string;
  summary: string;
};

export type JudgmentBreakdownItem = {
  label: string;
  value: string;
};

const MAX_SUMMARY_LENGTH = 118;
const MAX_PREVIEW_LENGTH = 86;
const GENERIC_REPORT_HEADINGS = new Set(
  [
  "核心判断",
  "结果概览",
  "分析结论",
  "结论",
  "Core judgment",
  ].map((heading) => heading.toLowerCase()),
);

function compactText(text: string): string {
  return text.replace(/\s+/g, " ").trim();
}

function truncateText(text: string, maxLength: number): string {
  const compacted = compactText(text);
  if (compacted.length <= maxLength) {
    return compacted;
  }
  return `${compacted.slice(0, maxLength).replace(/[，,。；;：:\s]+$/u, "")}…`;
}

function isMarkdownTableLine(line: string): boolean {
  const trimmed = line.trim();
  if (!trimmed.includes("|")) {
    return false;
  }
  if (/^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?$/u.test(trimmed)) {
    return true;
  }
  return trimmed.split("|").filter((part) => part.trim()).length >= 3;
}

function isSectionHeadingLine(line: string): boolean {
  return /^#{1,6}\s+/u.test(line) || /^\d+[.、]\s*\S+/u.test(line);
}

function extractReadableLines(answer: string): string[] {
  return answer
    .replace(/```[\s\S]*?```/g, "")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .filter((line) => !isMarkdownTableLine(line))
    .filter((line) => !/^[-*_]{3,}$/u.test(line))
    .filter((line) => !isSectionHeadingLine(line))
    .map((line) =>
      line
        .replace(/^[-*]\s+/u, "")
        .replace(/^#+\s*/u, "")
        .replace(/`([^`]+)`/g, "$1")
        .replace(/\*\*([^*]+)\*\*/g, "$1")
        .trim(),
    )
    .filter(Boolean);
}

export function stripMarkdown(text: string): string {
  return text
    .replace(/```[\s\S]*?```/g, "")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/^#+\s*/gm, "")
    .replace(/^[-*]\s*/gm, "")
    .replace(/\n{2,}/g, "\n")
    .trim();
}

export function buildDisplayReportMarkdown(answer: string): string {
  const lines = answer.replace(/\r\n/g, "\n").split("\n");
  const firstContentIndex = lines.findIndex((line) => line.trim());
  if (firstContentIndex === -1) {
    return "";
  }

  const firstContent = lines[firstContentIndex].trim();
  const headingMatch = firstContent.match(/^#{1,6}\s+(.+)$/u);
  if (!headingMatch) {
    return answer.trim();
  }

  const headingText = headingMatch[1]
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/[：:。.\s]+$/u, "")
    .trim()
    .toLowerCase();
  if (!GENERIC_REPORT_HEADINGS.has(headingText)) {
    return answer.trim();
  }

  return [...lines.slice(0, firstContentIndex), ...lines.slice(firstContentIndex + 1)].join("\n").trim();
}

export function summarizeAnswer(answer: string): AnswerSummary {
  const readableLines = extractReadableLines(answer);
  const fallback = stripMarkdown(answer);
  if (!readableLines.length && !fallback) {
    return {
      title: "这轮分析完成后，会先给出一个核心判断。",
      summary: "随后继续向下展开证据图表、明细表格以及下一步追问。",
    };
  }

  const headingPattern = /^(核心判断|Core judgment)$/i;
  const contentLines = headingPattern.test(readableLines[0] ?? "") ? readableLines.slice(1) : readableLines;
  const title = truncateText(contentLines[0] ?? fallback, 72);
  const summary =
    truncateText(contentLines.slice(1).join(" ").trim(), MAX_SUMMARY_LENGTH) ||
    "下方会继续展开完整的证据链路。";
  return { title, summary };
}

export function buildJudgmentBreakdown(
  result: ResultPayload | null,
  answerParts: AnswerSummary,
): JudgmentBreakdownItem[] {
  if (!result?.answer && !result?.raw_rows.length) {
    return [
      { label: "主要信号", value: "等待分析结果" },
      { label: "关键依据", value: "需要先取得证据" },
      { label: "下一步", value: "输入问题后继续展开" },
    ];
  }

  const hasChart = Boolean(result.chart_config?.type);
  const firstRow = result.raw_rows[0];
  const firstColumn = firstRow ? Object.keys(firstRow)[0] : "";
  const firstValue = firstColumn ? String(firstRow[firstColumn]) : "";
  const focusTarget = firstValue ? `${firstValue} 等重点对象` : "重点对象";

  return [
    { label: "主要信号", value: answerParts.title },
    {
      label: "关键依据",
      value: hasChart
        ? `已生成图表，并保留 ${result.raw_rows.length} 行明细`
        : `已保留 ${result.raw_rows.length} 行明细用于核对`,
    },
    { label: "下一步", value: `围绕 ${focusTarget} 继续下钻` },
  ];
}

export function buildAssistantPreview(result: ResultPayload): string {
  if (result.answer) {
    const { title } = summarizeAnswer(result.answer);
    return truncateText(`已完成查询、分析和报告整理：${title}`, MAX_PREVIEW_LENGTH);
  }
  if (!result.raw_rows.length) {
    return "这一轮没有查到可展示的数据。";
  }
  return `已准备好 ${result.raw_rows.length} 行结构化数据，可继续核对明细。`;
}

export function buildProcessItems(messages: Message[], latestResult: ResultPayload | null) {
  const lastUser = [...messages].reverse().find((message) => message.role === "user");
  const lastAssistant = [...messages].reverse().find((message) => message.role === "assistant");
  const rowCount = latestResult?.raw_rows.length ?? 0;

  return [
    {
      meta: "问题 01 · 用户",
      body: lastUser?.content ?? "请先输入一个业务问题，工作台会围绕这个问题组织结果。",
      tone: "primary",
    },
    {
      meta: "步骤 02 · 助手",
      body:
        lastAssistant ? truncateText(lastAssistant.content, MAX_PREVIEW_LENGTH) :
        "系统会把问题翻译成查询与分析链路，再把结果组织成可阅读的结论与证据。",
      tone: "secondary",
    },
    {
      meta: "步骤 03 · 证据",
      body:
        rowCount > 0
          ? `当前已准备好 ${rowCount} 行数据供对比，页面会同时给出图表和表格。`
          : "如果本轮没有取到结果，页面会明确标出空结果或数据库异常。",
      tone: "secondary",
    },
  ];
}

export function buildFollowUps(result: ResultPayload | null): string[] {
  if (!result?.raw_rows.length) {
    return [
      "哪些城市在区县或时段维度上也出现了最明显的订单下滑？",
      "和上一季度相比，哪些变化主要来自销量，哪些主要来自价格？",
      "如果只聚焦表现最差的几个城市，下一步应该先从哪里开始排查？",
    ];
  }

  const firstRow = result.raw_rows[0];
  const firstKey = Object.keys(firstRow)[0];
  const firstValue = firstKey ? String(firstRow[firstKey]) : "这些重点城市";

  return [
    `围绕 ${firstValue} 继续下钻时，应该优先看哪些区域、时段或站点？`,
    "如果把订单量、活跃度与价格变化拆开看，真正拖累收入的是哪一项？",
    "下一轮分析最值得补充哪张宽表，才能更快判断是需求问题还是供给问题？",
  ];
}
