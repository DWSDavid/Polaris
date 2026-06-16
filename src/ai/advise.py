"""Grounded portfolio-level decision briefs."""

from __future__ import annotations

from src.ai import ai_client

SYSTEM_PROMPT = (
    "你是A股中期波段决策辅助。只能使用用户提供的结构化事实，"
    "不要编造价格、资金、个股名、新闻或财务数据。人最后决定，你不自动下单。"
)

SECTION_PROMPT = (
    "请用中文分点输出 5 点以内："
    "1. 大趋势；2. 资金与分化；3. 龙头联动；"
    "4. 持仓、对冲与担保比；5. 今日观察。"
    "每一点必须引用下面 facts 中已有字段，不要补充未给出的数字。"
)


def build_advice_prompt(facts: dict) -> str:
    lines = [
        SECTION_PROMPT,
        "安全约束：不要编造任何未给出的行情/资金/个股/新闻，不给买卖指令。",
        "事实摘要:",
        *_readable_summary(facts),
        "facts:",
    ]
    lines.extend(_flatten_facts(facts))
    return "\n".join(lines)


def advise(facts: dict) -> str:
    return ai_client.chat(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_advice_prompt(facts)},
        ]
    )


def _flatten_facts(value, prefix: str = "") -> list[str]:
    lines = []
    if isinstance(value, dict):
        for key, item in value.items():
            name = f"{prefix}.{key}" if prefix else str(key)
            lines.extend(_flatten_facts(item, name))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            name = f"{prefix}[{index}]"
            lines.extend(_flatten_facts(item, name))
        if not value:
            lines.append(f"- {prefix}: []")
    else:
        lines.append(f"- {prefix}: {value}")
    return lines


def _readable_summary(facts: dict) -> list[str]:
    lines = []
    if "mainline" in facts:
        lines.append(
            "当前主线: "
            f"{facts.get('mainline')}, "
            f"持续{facts.get('mainline_trend_days', '未知')}天, "
            f"10日资金{facts.get('mainline_inflow_10d', '未知')}"
        )
    holdings = facts.get("holdings") or []
    if holdings:
        holding_text = "、".join(
            f"{item.get('name', '未知')}({item.get('sector', '未知')}, {item.get('state', '未知')})"
            for item in holdings
            if isinstance(item, dict)
        )
        if holding_text:
            lines.append(f"当前持仓: {holding_text}")
    candidates = facts.get("candidates") or []
    if candidates:
        lines.append("候选篮子: " + "、".join(str(item) for item in candidates))
    hedge_pairs = facts.get("hedge_pairs") or []
    if hedge_pairs:
        pair_text = "、".join(
            "↔".join(str(part) for part in pair)
            for pair in hedge_pairs
            if isinstance(pair, (list, tuple)) and len(pair) >= 2
        )
        if pair_text:
            lines.append(f"对冲对: {pair_text}")
    if "guarantee_ratio" in facts:
        lines.append(f"担保比: {facts.get('guarantee_ratio')}")
    if "today_watch" in facts:
        lines.append(f"今日观察: {facts.get('today_watch')}")
    return lines or ["无摘要字段，仅使用下方 facts。"]
