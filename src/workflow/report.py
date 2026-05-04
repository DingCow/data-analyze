"""
src/workflow/report.py —— Report Agent
职责：
  1. 接收 Analysis Agent 的推理结论，整理成清晰的 Markdown 报告
  2. 根据原始数据的列结构，决定画什么图表，输出图表配置 JSON
  不做任何新的推理或数据查询，只负责格式化和图表决策。
  使用 deepseek-v4-flash，并关闭思考模式（格式化输出不需要推理能力）。
"""

import json
from typing import Optional
from src.llm import FAST_MODEL, NON_THINKING_EXTRA_BODY, client, debug

# Report Agent 的系统提示词
SYSTEM_PROMPT = """你是一个专业的报告撰写助手。

你会收到：
1. 用户的原始问题
2. 数据分析结论
3. 原始数据的列名列表（用于决定图表配置）

你的输出必须是一个 JSON 对象，格式如下：
{
  "markdown": "完整的 Markdown 报告内容",
  "chart": {
    "type": "line" 或 "bar" 或 null,
    "x": "用作 x 轴的列名",
    "y": ["用作 y 轴的列名1", "列名2"],
    "title": "图表标题"
  }
}

Markdown 报告要求：
- 用 ## 分节，结构清晰
- 关键数据用**加粗**突出
- 适合用表格的地方用 Markdown 表格呈现
- 结尾给出简短的结论或建议
- 语言简洁专业

图表配置要求：
- 如果数据有时间/日期列（列名含"月""年""日""date""time""month"）+ 数值列 → type 选 "line"
- 如果数据有分类列 + 数值列，适合对比 → type 选 "bar"
- 如果数据不适合画图（如单行数据、纯文字） → type 为 null，其余字段也为 null
- x、y 只能使用原始数据列名列表中存在的列名

只输出 JSON，不要任何其他文字。"""


def build_report_input(question: str, analysis: str, raw_rows: list[dict]) -> str:
    """把报告生成需要的上下文整理成模型输入。"""
    # 从原始数据中提取列名列表，告诉模型有哪些列可以用
    columns = list(raw_rows[0].keys()) if raw_rows else []
    columns_str = "、".join(columns) if columns else "无数据"

    return f"""用户问题：{question}

数据分析结论：
{analysis}

原始数据的列名列表：{columns_str}

请按要求输出 JSON。"""


def generate_report_payload(user_message: str) -> dict:
    """调用 Report Agent 生成包含 Markdown 和图表配置的原始报告对象。"""
    debug("[Report Agent] 开始格式化报告")

    response = client.chat.completions.create(
        model=FAST_MODEL,   # 格式化输出用轻量模型，速度快
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0,
        max_tokens=4096,
        # 强制模型输出 JSON 格式，避免输出多余文字
        response_format={"type": "json_object"},
        extra_body=NON_THINKING_EXTRA_BODY,
    )

    raw = response.choices[0].message.content

    # 解析模型输出的 JSON
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        # 万一模型没有严格输出 JSON，直接把原始内容作为 markdown，不画图
        payload = {"markdown": raw, "chart": None}

    return payload


def extract_markdown(payload: dict) -> str:
    """从报告对象中提取 Markdown 报告。"""
    return payload.get("markdown", "")


def extract_chart_config(payload: dict) -> Optional[dict]:
    """从报告对象中提取图表配置，并统一处理不画图的情况。"""
    chart_config = payload.get("chart", None)
    # 如果 chart.type 为 null，统一转成 None
    if chart_config and chart_config.get("type") is None:
        return None
    return chart_config


def run(question: str, analysis: str, raw_rows: list[dict]) -> tuple[str, Optional[dict]]:
    """
    Report Agent 主函数：格式化报告 + 输出图表配置。

    参数：
      question - 用户的原始问题
      analysis - Analysis Agent 输出的推理结论
      raw_rows - SQL Agent 查到的原始数据行，用于提取列名供图表决策

    返回：
      (markdown报告文字, 图表配置字典)
      - 图表配置字典示例：{"type": "line", "x": "月份", "y": ["收入"], "title": "月度收入趋势"}
      - 如果不需要画图，图表配置为 None
    """
    user_message = build_report_input(question, analysis, raw_rows)
    payload = generate_report_payload(user_message)
    markdown = extract_markdown(payload)
    chart_config = extract_chart_config(payload)

    return markdown, chart_config
