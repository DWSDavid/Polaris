"""Grounded sector summaries built only from supplied facts."""

from __future__ import annotations

from src.ai import ai_client
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
)


def build_sector_prompt(facts: dict) -> str:
    lines = ["请基于以下真实事实写中文板块综述，禁止补充未给出的数字。"]
    for key in FACT_KEYS:
        if key in facts and facts[key] is not None:
            lines.append(f"- {key}: {facts[key]}")
    for key, value in facts.items():
        if key not in FACT_KEYS and value is not None:
            lines.append(f"- {key}: {value}")
    state = facts.get("state")
    if state:
        lines.append(f"- state_definition: {explain_term(str(state))}")
    lines.append(
        "输出要求：80-220字，按 5 个决策分点写：周期判断、资金与分化、龙头联动、对冲与担保比、今日观察。"
        "周期判断必须用箱体位置、MA60/中期趋势、多周资金和启动迹象判断周期阶段（箱体/启动/主升/退潮）以及中期结构是否完好。"
        "如 facts 提供市场 context，只能结合北向、龙虎榜、研报、新闻做佐证；结构完好时，10%内回撤说明为正常波动。"
        "禁止把 facts 中出现的字段说成缺失；若字段已出现，必须使用其值。"
        "每一点只引用上方 facts 中已有字段；不编造价格、资金、个股名、新闻或财务数据；只给观察倾向，不给买卖指令。"
    )
    return "\n".join(lines)


def summarize_sector(facts: dict) -> str:
    return ai_client.chat(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_sector_prompt(facts)},
        ]
    )
