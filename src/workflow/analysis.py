"""
src/workflow/analysis.py —— Analysis Agent
职责：
  负责两个阶段的推理工作（都使用 deepseek-v4-pro 思考模式）：
  1. 前置拆解：把抽象的用户问题拆解成具体的查询子任务
  2. 后置分析：接收 SQL Agent 查好的数据，做深度推理
"""

from src.llm import REASONING_MODEL, THINKING_EXTRA_BODY, THINKING_REASONING_EFFORT, client, debug

# 前置拆解的系统提示词：把抽象问题翻译成具体查询意图
DECOMPOSE_SYSTEM_PROMPT = """你是一个数据分析规划师，擅长把模糊的业务问题拆解成可执行的数据查询任务。

数据库结构如下：
{schema}

你会收到一个用户的业务问题，你的任务是：
1. 理解问题背后的业务含义
2. 确定需要查询哪些指标、哪些表、哪些时间范围
3. 规划查询方案

【核心原则：SQL Agent 只能返回一张结果表】
- 如果问题只涉及一张表，直接查那张表
- 如果问题涉及多张表（例如订单表 + 台账表），必须用 JOIN 把所有数据合并成一张宽表，一次性返回
- 不允许让 SQL Agent 分开查多张表再拼——最终只能有一条 SELECT 语句返回数据
- 子任务中涉及的探索性查询（如查省份名称、查关联字段）只是辅助步骤，最终必须合并进 JOIN

输出格式（纯文字，不要 JSON）：
- 最终查询目标：一条 JOIN SQL，输出所有需要的字段
- 需要的字段：来自 xxx 表的 xxx，来自 xxx 表的 xxx
- 关联条件：通过 xxx 字段关联
- 过滤条件：xxx

只输出查询规划，不要其他解释。"""

# 后置分析的系统提示词：基于数据做推理
ANALYZE_SYSTEM_PROMPT = """你是一个专业的数据分析师，擅长从数据中发现规律和问题。

你会收到：
1. 用户的原始问题
2. 已经从数据库查好的数据

你的任务：
- 基于数据，回答用户的问题
- 给出清晰的结论，说明数据反映了什么
- 如有趋势、异常、对比，主动点出来
- 用自然语言输出，结构清晰

注意：不要编造数据中没有的内容，结论必须来自数据本身。"""


def decompose(schema: str, question: str) -> str:
    """
    前置拆解：把抽象问题翻译成具体的查询子任务列表。
    """
    debug("[Analysis Agent] 开始拆解问题")

    response = client.chat.completions.create(
        model=REASONING_MODEL,   # 拆解需要更强推理能力
        messages=[
            {"role": "system", "content": DECOMPOSE_SYSTEM_PROMPT.format(schema=schema)},
            {"role": "user", "content": f"用户问题：{question}"},
        ],
        max_tokens=1024,
        reasoning_effort=THINKING_REASONING_EFFORT,
        extra_body=THINKING_EXTRA_BODY,
    )

    return response.choices[0].message.content


def format_raw_rows(raw_rows: list[dict]) -> str:
    """把结构化查询结果转成模型更容易阅读的文字表格。"""
    # 把结构化数据转成文字表格，方便模型阅读
    if raw_rows:
        headers = list(raw_rows[0].keys())
        header_line = " | ".join(headers)
        separator = "-" * len(header_line)
        data_lines = [
            " | ".join(str(row.get(h, "")) for h in headers)
            for row in raw_rows
        ]
        # 拼成完整的文字表格
        data_text = f"{header_line}\n{separator}\n" + "\n".join(data_lines)
        data_text += f"\n\n共 {len(raw_rows)} 行"
    else:
        data_text = "无数据"

    return data_text


def build_analysis_input(question: str, raw_rows: list[dict]) -> str:
    """把用户问题和查询结果拼成后置分析模型的输入。"""
    data_text = format_raw_rows(raw_rows)
    return f"""用户问题：{question}

以下是从数据库查到的相关数据：

{data_text}

请基于上面的数据回答用户问题，给出分析结论。"""


def analyze_prepared(user_message: str) -> str:
    """执行后置分析推理，输入必须已经完成格式化。"""
    debug("[Analysis Agent] 开始推理分析")

    response = client.chat.completions.create(
        model=REASONING_MODEL,
        messages=[
            {"role": "system", "content": ANALYZE_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        max_tokens=4096,
        reasoning_effort=THINKING_REASONING_EFFORT,
        extra_body=THINKING_EXTRA_BODY,
    )

    return response.choices[0].message.content


def analyze(question: str, raw_rows: list[dict]) -> tuple[str, list[dict]]:
    """
    后置分析：基于 SQL Agent 返回的结构化数据，做深度推理，输出分析结论。

    这个函数保留为兼容入口；LangGraph 分支会把准备输入和执行分析拆成两个节点。
    """
    user_message = build_analysis_input(question, raw_rows)
    conclusion = analyze_prepared(user_message)

    # 返回推理结论文字 + 透传原始数据行（供 Report Agent 决定画什么图）
    return conclusion, raw_rows
