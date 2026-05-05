"""
src/workflow/router.py —— Router Agent
职责：
  判断用户问题的意图，决定走哪条处理路径：
  - 简单查询 → SQL Agent 取数 → 直接返回
  - 复杂分析 → SQL Agent 取数 → Analysis Agent 推理 → Report Agent 格式化输出
"""

from typing import Optional
from src.llm import FAST_MODEL, NON_THINKING_EXTRA_BODY, client, debug
from src.workflow import sql, analysis, report

# 意图判断的系统提示词（轻量级，只做分类）
ROUTER_SYSTEM_PROMPT = """你是一个问题分类器，判断用户的问题属于哪种类型。

简单查询：只需要查出数据就能回答，例如：
- 查某个指标的数值
- 列出某些记录
- 统计总数、平均值

复杂分析：需要对数据做进一步推理，例如：
- 环比 / 同比对比
- 趋势分析
- 原因推断
- 异常检测
- 综合多个指标得出结论

只回复一个词：simple 或 complex，不要其他任何内容。"""


def classify(question: str) -> str:
    """
    判断问题复杂度，返回 'simple' 或 'complex'。
    用 deepseek-v4-flash 做分类，关闭思考模式以保持响应轻量。
    """
    response = client.chat.completions.create(
        model=FAST_MODEL,
        messages=[
            {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        temperature=0,
        max_tokens=10,  # 只需要一个词，严格限制输出长度
        extra_body=NON_THINKING_EXTRA_BODY,
    )
    # 统一转小写，去除空格，防止模型多输出空格或大写
    return response.choices[0].message.content.strip().lower()


def run(schema: str, question: str, history: list[dict]) -> tuple[str, Optional[dict], list[dict]]:
    """
    Router Agent 主函数：判断意图后分发给对应 Agent。

    参数：
      schema   - 数据库结构
      question - 用户问题
      history  - 多轮对话历史

    返回：
      (最终回答文字, 图表配置, 原始数据行)
      - 最终回答文字：展示给用户的 Markdown 文字
      - 图表配置：Report Agent 决定的图表参数，None 表示不画图
      - 原始数据行：SQL 查到的结构化数据，供 CLI/Web/API 展示或渲染
    """
    # 第一步：判断问题类型
    intent = classify(question)
    debug(f"[Router] 意图分类: {intent}")

    if intent == "complex":
        print("  → 复杂分析，启动完整链路：Analysis 拆解 → SQL 取数 → Analysis 推理 → Report 报告")

        # 第二步：Analysis Agent 前置拆解，把抽象问题翻译成具体查询任务
        print("  → [Analysis Agent] 拆解问题...")
        subtasks = analysis.decompose(schema, question)
        debug(f"拆解结果：{subtasks}")

        # 第三步：SQL Agent 按拆解结果取数，只返回结构化原始数据
        print("  → [SQL Agent] 开始查询数据...")
        guided_question = f"用户原始问题：{question}\n\n需要查询的内容：\n{subtasks}"
        raw_rows = sql.run(schema, guided_question, history)

        # 第四步：Analysis Agent 后置推理，基于结构化数据推理，透传原始数据
        print("  → [Analysis Agent] 开始推理分析...")
        conclusion, raw_rows = analysis.analyze(question, raw_rows)

        # 第五步：Report Agent 格式化输出 + 决定图表配置
        print("  → [Report Agent] 开始生成报告...")
        markdown, chart_config = report.run(question, conclusion, raw_rows)

        return markdown, chart_config, raw_rows

    else:
        # 简单查询：SQL Agent 取数，直接返回结构化数据，交给入口层展示
        print("  → 简单查询，启动 SQL Agent")
        raw_rows = sql.run(schema, question, history)
        # 简单查询不需要文字说明，返回空字符串，数据行由入口层直接展示
        return "", None, raw_rows
