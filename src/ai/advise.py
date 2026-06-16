"""Grounded portfolio-level decision briefs."""

from __future__ import annotations

from src.ai import ai_client

SYSTEM_PROMPT = (
    "你是A股中期波段决策辅助。只能使用用户提供的结构化事实，"
    "不要编造价格、资金、个股名、新闻或财务数据。人最后决定，你不自动下单。"
)

SECTION_PROMPT = (
    "请用中文输出 80-220 字，必须按 5 个决策分点："
    "1. 周期判断（大趋势）；2. 资金与分化；3. 龙头联动；"
    "4. 对冲与担保比（结合持仓）；5. 今日观察。"
    "周期判断必须用箱体位置、MA60/中期趋势、多周资金和启动迹象判断周期阶段（箱体/启动/主升/退潮）以及中期结构是否完好；"
    "如 facts 提供市场 context，只能结合北向、龙虎榜、研报、新闻做佐证；结构完好时，10%内回撤说明为正常波动。"
    "禁止把 facts 中出现的字段说成缺失；若字段已出现，必须使用其值。"
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
    if "trend_days" in facts or "mainline_trend_days" in facts:
        lines.append(f"趋势持续: {facts.get('trend_days', facts.get('mainline_trend_days'))} 天")
    cycle = facts.get("cycle") or {}
    if cycle:
        lines.append(
            "周期结构: "
            f"箱体位置={cycle.get('position_in_box', '未知')}，"
            f"中期趋势={cycle.get('midterm_trend', '未知')}，"
            f"多周资金={cycle.get('cum_inflow_20d', cycle.get('cum_inflow_60d', '未知'))}"
        )
    ignition = facts.get("ignition") or {}
    if ignition:
        lines.append(
            "启动迹象: "
            f"flag={ignition.get('ignition_flag', '未知')}，"
            f"score={ignition.get('ignition_score', '未知')}"
        )
    market_context = facts.get("market_context") or facts.get("context") or {}
    if market_context:
        lines.append(f"市场context(北向/龙虎榜/研报/新闻): {_compact_value(market_context)}")
    analogy = facts.get("historical_analogy")
    if analogy:
        lines.append(f"历史类比: {_compact_value(analogy)}")
    rotation = facts.get("rotation_flow")
    if rotation:
        label = rotation.get("rotation_label", "未知") if isinstance(rotation, dict) else _compact_value(rotation)
        net = rotation.get("net_inflow", "未知") if isinstance(rotation, dict) else "未知"
        lines.append(f"资金接力: {label}，净流入={net}")
    guard = facts.get("valuation_guard")
    if guard:
        lines.append(f"估值护栏: {_compact_value(guard)}")
    if "hedge_score" in facts:
        lines.append(f"对冲度: {facts.get('hedge_score')}")
    linkage = facts.get("leader_linkage")
    if linkage:
        label = linkage.get("label", "未知") if isinstance(linkage, dict) else _compact_value(linkage)
        lines.append(f"龙头联动: {label}")
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


def _compact_value(value) -> str:
    if isinstance(value, dict):
        return "，".join(f"{key}={item}" for key, item in value.items())
    if isinstance(value, list):
        return "，".join(str(item) for item in value)
    return str(value)
