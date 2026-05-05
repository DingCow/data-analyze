import test from "node:test";
import assert from "node:assert/strict";

import {
  buildAssistantPreview,
  buildDisplayReportMarkdown,
  buildJudgmentBreakdown,
  summarizeAnswer,
} from "./ui";

test("空字符串时返回默认标题和摘要", () => {
  const result = summarizeAnswer("");

  assert.equal(result.title, "这轮分析完成后，会先给出一个核心判断。");
  assert.equal(result.summary, "随后继续向下展开证据图表、明细表格以及下一步追问。");
});

test("会跳过中文章节标题并提取真正结论", () => {
  const result = summarizeAnswer("## 核心判断\n表现较弱的城市主要是被订单流失拖累。\n下一步需要检查活跃度。");

  assert.equal(result.title, "表现较弱的城市主要是被订单流失拖累。");
  assert.equal(result.summary, "下一步需要检查活跃度。");
});

test("摘要会过滤 Markdown 表格和编号段落", () => {
  const result = summarizeAnswer(`## 核心判断

2023年深圳地区充电业务呈现爆发式增长，核心指标均实现数倍提升。

1. 业务规模高速扩张

| 指标 | 1月 | 12月 | 增长倍数 |
|------|------|------|----------|
| 订单总数 | 2,183 | 18,417 | 8.4倍 |

4月为第一个增长爆发点，5月订单数翻倍。`);

  assert.equal(result.title, "2023年深圳地区充电业务呈现爆发式增长，核心指标均实现数倍提升。");
  assert.equal(result.summary, "4月为第一个增长爆发点，5月订单数翻倍。");
  assert.equal(result.summary.includes("|"), false);
});

test("会跳过英文章节标题并提取真正结论", () => {
  const result = summarizeAnswer("## Core judgment\nOrder loss is the main driver.\nCheck activity next.");

  assert.equal(result.title, "Order loss is the main driver.");
  assert.equal(result.summary, "Check activity next.");
});

test("只有正文时直接把首句作为标题", () => {
  const result = summarizeAnswer("订单量下滑最明显的是中山。\n珠海次之。");

  assert.equal(result.title, "订单量下滑最明显的是中山。");
  assert.equal(result.summary, "珠海次之。");
});

test("只有章节标题时回退到章节标题本身", () => {
  const result = summarizeAnswer("## 核心判断");

  assert.equal(result.title, "核心判断");
  assert.equal(result.summary, "下方会继续展开完整的证据链路。");
});

test("判断拆解在空结果时返回可展示的默认行", () => {
  const result = buildJudgmentBreakdown(null, summarizeAnswer(""));

  assert.deepEqual(result, [
    { label: "主要信号", value: "等待分析结果" },
    { label: "关键依据", value: "需要先取得证据" },
    { label: "下一步", value: "输入问题后继续展开" },
  ]);
});

test("判断拆解会基于结果标题和首行对象生成工作台摘要", () => {
  const result = buildJudgmentBreakdown(
    {
      answer: "## 核心判断\n中山主要被订单流失拖累。",
      chart_config: { type: "bar", x: "城市", y: ["订单量"], title: "城市对比" },
      raw_rows: [{ 城市: "中山", 订单量: 23822 }],
      db_error: null,
    },
    summarizeAnswer("## 核心判断\n中山主要被订单流失拖累。"),
  );

  assert.equal(result[0].value, "中山主要被订单流失拖累。");
  assert.equal(result[1].label, "关键依据");
  assert.equal(result[1].value, "已生成图表，并保留 1 行明细");
  assert.equal(result[2].value, "围绕 中山 等重点对象 继续下钻");
});

test("助手预览只保留短摘要，不暴露完整报告", () => {
  const preview = buildAssistantPreview({
    answer: `## 核心判断

深圳增长明显。

| 指标 | 1月 | 12月 |
|------|------|------|
| 订单 | 1 | 10 |

后续还有非常长非常长非常长非常长非常长非常长非常长非常长非常长非常长的分析。`,
    chart_config: null,
    raw_rows: [{ 城市: "深圳" }],
    db_error: null,
  });

  assert.match(preview, /^已完成查询、分析和报告整理：深圳增长明显。/);
  assert.equal(preview.includes("|"), false);
  assert.ok(preview.length <= 90);
});

test("展示完整报告时只移除开头泛化标题", () => {
  const markdown = buildDisplayReportMarkdown(`## 核心判断

表现较弱的城市主要被订单流失拖累。

### 关键依据

- 中山下滑最明显。`);

  assert.equal(markdown.startsWith("## 核心判断"), false);
  assert.equal(markdown.includes("### 关键依据"), true);
});

test("展示完整报告时保留有业务含义的开头标题", () => {
  const markdown = buildDisplayReportMarkdown(`## 深圳充电业务复盘

订单和充电量均有增长。`);

  assert.equal(markdown.startsWith("## 深圳充电业务复盘"), true);
});
