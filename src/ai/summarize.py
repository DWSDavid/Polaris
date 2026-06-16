"""Grounded sector summaries built only from supplied facts."""

from __future__ import annotations

from src.ai import ai_client
from src.compute.glossary import explain_term

FACT_KEYS = [
    "sector",
    "state",
    "trend_days",
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
    state = facts.get("state")
    if state:
        lines.append(f"- state_definition: {explain_term(str(state))}")
    lines.append(
        "输出要求：分 3-5 点，80-200 字，说明主线、持续天数、资金、扩散和龙头；"
        "只给观察倾向，不给买卖指令。"
    )
    return "\n".join(lines)


def summarize_sector(facts: dict) -> str:
    return ai_client.chat(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_sector_prompt(facts)},
        ]
    )
