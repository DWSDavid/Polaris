"""Grounded portfolio-level decision briefs."""

from __future__ import annotations

from src.ai import ai_client
from src.ai.humanize import assert_no_jargon, conclusion_first_instruction, humanize_facts

SYSTEM_PROMPT = (
    "你是A股中期波段决策辅助。只能使用用户提供的结构化事实，"
    "不要编造价格、资金、个股名、新闻或财务数据。人最后决定，你不自动下单。"
    "禁止输出任何英文变量名、字段名、等号或代码写法。"
)

SECTION_PROMPT = (
    "请用中文输出 80-220 字，必须按 5 个决策分点："
    "1. 周期判断（大趋势）；2. 资金与分化；3. 龙头联动；"
    "4. 对冲与担保比（结合持仓）；5. 今日观察。"
    "周期判断必须用箱体位置、MA60/中期趋势、多周资金和启动迹象判断周期阶段（箱体/启动/主升/退潮）以及中期结构是否完好；"
    "如提供市场佐证，只能结合北向、龙虎榜、研报、新闻做佐证；结构完好时，10%内回撤说明为正常波动。"
    "禁止把已经出现的事实说成缺失；若事实已出现，必须使用其值。"
    "每一点必须引用下面已有事实，不要补充未给出的数字。"
)


def build_advice_prompt(facts: dict) -> str:
    lines = [
        SECTION_PROMPT,
        conclusion_first_instruction(),
        "安全约束：不要编造任何未给出的行情/资金/个股/新闻，不给买卖指令。",
        "真实事实:",
        *humanize_facts(facts),
    ]
    return "\n".join(lines)


def advise(facts: dict, timeout: int = 30) -> str:
    text = ai_client.chat(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_advice_prompt(facts)},
        ],
        timeout=timeout,
    )
    try:
        assert_no_jargon(text)
    except ValueError:
        return _local_advice_summary(facts)
    return text


def _local_advice_summary(facts: dict) -> str:
    lines = humanize_facts(facts)
    ranked = facts.get("ranked_directions") or []
    top = ranked[0].get("sector") if ranked and isinstance(ranked[0], dict) else facts.get("mainline", "当前方向")
    detail = "；".join(lines[:6])
    return (
        f"结论：优先观察{top}，只有资金、扩散和持仓风险同时匹配时才提高仓位假设。\n"
        f"1. 周期判断：{detail}。2. 今日观察：以上只是数据归纳，人最后决定。"
    )
