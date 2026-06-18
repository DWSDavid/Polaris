"""Grounded single-stock analysis brief."""

from __future__ import annotations

from src.ai import ai_client
from src.ai.humanize import assert_no_jargon, conclusion_first_instruction

SYSTEM_PROMPT = (
    "你是A股单股节点分析助手。只能使用用户提供的真实事实，"
    "不要编造价格、资金、行业、个股名、新闻或财务数据。"
    "你只给入场/持有/退出观察倾向和验证条件，不自动下单，人最后决定。"
    "禁止输出任何英文变量名、字段名、等号或代码写法。"
)


def build_stock_advice_prompt(facts: dict) -> str:
    return "\n".join(
        [
            "请用类 TradingAgents 的多角色视角，但只做一段中文决策解释。",
            conclusion_first_instruction(),
            "必须分 5 点：1. 技术面；2. 资金面；3. 行业背景；4. 风控；5. 今日观察。",
            "每一点只能引用下方真实事实。不要编造，不给买卖指令。",
            "真实事实：",
            *_fact_lines(facts),
        ]
    )


def stock_advice(facts: dict, timeout: int = 30) -> str:
    text = ai_client.chat(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_stock_advice_prompt(facts)},
        ],
        timeout=timeout,
    )
    try:
        assert_no_jargon(text)
    except ValueError:
        return _local_stock_summary(facts)
    if text.startswith("未配置 AI API Key"):
        return _local_stock_summary(facts)
    return text or _local_stock_summary(facts)


def _fact_lines(facts: dict) -> list[str]:
    decision = facts.get("decision") or {}
    lines = [
        f"- 股票：{facts.get('name', '未知')}（{facts.get('code', '')}）",
        f"- 所属行业：{facts.get('sector', '未知')}，行业状态：{facts.get('sector_state', '未知')}，行业10日资金：{_money(facts.get('sector_inflow_10d'))}",
        f"- 系统倾向：{decision.get('stance', '待确认')}，综合分：{_num(decision.get('score')):.2f}",
        f"- 今日价格：{_num(facts.get('latest_price')):.2f}，今日涨跌：{_num(facts.get('pct_chg')):+.2f}%",
        f"- 技术面：20日均线{_yes_no(facts.get('above_ma20'))}，60日均线{_yes_no(facts.get('above_ma60'))}，20日涨跌{_num(facts.get('return_20d')):+.2f}%，60日涨跌{_num(facts.get('return_60d')):+.2f}%",
        f"- 箱体位置：{_box_label(facts.get('position_in_box'))}，60日高点回撤：{_num(facts.get('drawdown_60d')):.1%}",
        f"- 个股资金：5日主力{_money(facts.get('stock_inflow_5d'))}，10日主力{_money(facts.get('stock_inflow_10d'))}",
        f"- 量能估值：量比{_num(facts.get('volume_ratio')):.2f}，换手{_num(facts.get('turnover_rate')):.2f}%，市盈率{_optional(facts.get('pe_ttm'))}，市净率{_optional(facts.get('pb'))}",
        f"- 核心理由：{_join(decision.get('reasons') or [])}",
        f"- 风险提示：{_join(decision.get('risk_flags') or ['暂无明显结构性风险'])}",
        f"- 今日观察：{_join(decision.get('watch_points') or [])}",
    ]
    return lines


def _local_stock_summary(facts: dict) -> str:
    decision = facts.get("decision") or {}
    name = facts.get("name") or facts.get("code") or "该股"
    stance = decision.get("stance", "观察等待确认")
    reasons = _join(decision.get("reasons") or [])
    risks = _join(decision.get("risk_flags") or ["暂无明显结构性风险"])
    return (
        f"结论：{name}当前系统倾向是{stance}，只作观察辅助，人最后决定。\n"
        f"1. 技术面：20日均线{_yes_no(facts.get('above_ma20'))}，60日均线{_yes_no(facts.get('above_ma60'))}，箱体位置{_box_label(facts.get('position_in_box'))}。"
        f"2. 资金面：5日主力{_money(facts.get('stock_inflow_5d'))}，10日主力{_money(facts.get('stock_inflow_10d'))}。"
        f"3. 行业背景：{facts.get('sector', '所属行业')}处于{facts.get('sector_state', '未知')}。"
        f"4. 风控：{risks}。5. 今日观察：{reasons or '等待更多共振'}。"
    )


def _yes_no(value) -> str:
    if value is None:
        return "缺数据"
    return "之上" if bool(value) else "之下"


def _box_label(value) -> str:
    number = _num(value)
    if number >= 0.9:
        return "高位"
    if number >= 0.65:
        return "偏高"
    if number <= 0.25:
        return "低位"
    return "中部"


def _money(value) -> str:
    number = _num(value)
    yi = number / 100_000_000 if abs(number) >= 1_000_000 else number
    return f"{yi:+.1f}亿"


def _join(values) -> str:
    return "、".join(str(value) for value in values if str(value)) or "无"


def _optional(value) -> str:
    number = _num(value)
    return "-" if number == 0 else f"{number:.2f}"


def _num(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
