"""Grounded sector summaries built only from supplied facts."""

from __future__ import annotations

from src.ai import ai_client
from src.ai.humanize import assert_no_jargon, conclusion_first_instruction, humanize_facts
from src.compute.glossary import explain_term

FACT_KEYS = [
    "sector",
    "state",
    "trend_days",
    "historical_analogy",
    "rotation_flow",
    "valuation_guard",
    "hedge_score",
    "hedge_pairs",
    "guarantee_ratio",
    "leader_linkage",
    "cycle",
    "ignition",
    "market_context",
    "pct_chg",
    "main_net_inflow",
    "inflow_5d",
    "inflow_10d",
    "diffusion",
    "turning_point",
    "top_leaders",
]

SYSTEM_PROMPT = (
    "你是A股板块轮动分析助手。只能使用用户提供的结构化事实，"
    "不要编造价格、资金、个股名、新闻或财务数据。人最后决定，你不下单。"
    "禁止输出任何英文变量名、字段名、等号或代码写法。"
)


def build_sector_prompt(facts: dict) -> str:
    lines = [
        "请基于以下真实事实写中文板块综述，禁止补充未给出的数字。",
        conclusion_first_instruction(),
        "真实事实：",
    ]
    lines.extend(f"- {line}" for line in humanize_facts(_ordered_facts(facts)))
    state = facts.get("state")
    if state:
        lines.append(f"- 状态解释：{explain_term(str(state))}")
    lines.append(
        "输出要求：80-220字，按 5 个决策分点写：周期判断、资金与分化、龙头联动、对冲与担保比、今日观察。"
        "周期判断必须用箱体位置、MA60/中期趋势、多周资金和启动迹象判断周期阶段（箱体/启动/主升/退潮）以及中期结构是否完好。"
        "如提供市场佐证，只能结合北向、龙虎榜、研报、新闻做佐证；结构完好时，10%内回撤说明为正常波动。"
        "禁止把上方已经出现的事实说成缺失；若事实已出现，必须使用其值。"
        "每一点只引用上方已有事实；不编造价格、资金、个股名、新闻或财务数据；只给观察倾向，不给买卖指令。"
    )
    return "\n".join(lines)


def summarize_sector(facts: dict) -> str:
    text = ai_client.chat(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_sector_prompt(facts)},
        ]
    )
    try:
        assert_no_jargon(text)
    except ValueError:
        return _local_sector_summary(facts)
    return text


def _ordered_facts(facts: dict) -> dict:
    ordered = {key: facts[key] for key in FACT_KEYS if key in facts and facts[key] is not None}
    ordered.update({key: value for key, value in facts.items() if key not in ordered and value is not None})
    return ordered


def _local_sector_summary(facts: dict) -> str:
    lines = humanize_facts(_ordered_facts(facts))
    sector = facts.get("sector", "该板块")
    state = facts.get("state", "状态待确认")
    lead = f"结论：{sector}处于{state}，先看资金、扩散和龙头能否继续互相确认。"
    detail = "；".join(lines[:5])
    return f"{lead}\n1. 周期判断：{detail}。2. 今日观察：只作数据归纳，人最后决定。"
