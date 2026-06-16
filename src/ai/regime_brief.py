"""Grounded AI summary for style/regime research."""

from __future__ import annotations

from src.ai import ai_client
from src.ai.humanize import assert_no_jargon, conclusion_first_instruction

SYSTEM_PROMPT = (
    "你是A股风格与风口研究助手。只使用传入事实，不要编造指数、利率、资金、政策或行业名。"
    "输出只是研究辅助，人最后决定，不自动下单。禁止输出任何英文变量名、字段名、等号或代码写法。"
)

USER_PROMPT = (
    "请用中文分点输出：1. 近1年总结；2. 近3年总结；"
    "3. 各次风格转换及其可能原因，必须围绕利率/流动性/政策/盈利四类线索；"
    "4. 当前处于什么风格、风口在哪；5. 风险与验证。"
    "只使用传入事实，若没有原因字段，就说证据不足，不要编造。"
)


def build_regime_prompt(facts: dict) -> str:
    lines = [
        USER_PROMPT,
        conclusion_first_instruction(),
        "安全约束：只使用传入事实；不要编造任何未给出的宏观、政策、盈利或行业信息。",
        "真实事实:",
    ]
    lines.extend(_humanize_regime_facts(facts))
    return "\n".join(lines)


def regime_brief(facts: dict, timeout: int = 30) -> str:
    text = ai_client.chat(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_regime_prompt(facts)},
        ],
        timeout=timeout,
    )
    try:
        assert_no_jargon(text)
    except ValueError:
        return _local_regime_summary(facts)
    return text


def _humanize_regime_facts(facts: dict) -> list[str]:
    lines = []
    one_year = facts.get("one_year") or {}
    if isinstance(one_year, dict) and one_year.get("summary"):
        lines.append(f"- 近1年总结：{one_year.get('summary')}")
    three_year = facts.get("three_year") or {}
    if isinstance(three_year, dict) and three_year.get("summary"):
        lines.append(f"- 近3年总结：{three_year.get('summary')}")
    for item in facts.get("epochs") or []:
        if not isinstance(item, dict):
            continue
        period = "至".join(str(item.get(key, "")) for key in ("start", "end") if item.get(key))
        themes = _theme_text(item.get("themes") or [])
        macro = _macro_text(item.get("macro") or {})
        lines.append(
            f"- 风格阶段：{period or '时间未明'}，{item.get('regime', '风格未明')}；"
            f"主题：{themes or '未给出'}；宏观线索：{macro or '证据不足'}"
        )
    current = facts.get("current") or {}
    if isinstance(current, dict):
        style = current.get("style", "未知")
        themes = _theme_text(current.get("themes") or [])
        lines.append(f"- 当前风格：{style}；当前风口：{themes or '未给出'}")
    return lines


def _local_regime_summary(facts: dict) -> str:
    current = facts.get("current") or {}
    style = current.get("style", "当前风格") if isinstance(current, dict) else "当前风格"
    detail = "；".join(_humanize_regime_facts(facts)[:4])
    return f"结论：{style}仍需用资金、政策和盈利线索继续验证。\n1. 风格判断：{detail}。"


def _theme_text(value) -> str:
    if not isinstance(value, list):
        return str(value)
    names = []
    for item in value[:6]:
        if isinstance(item, dict):
            sector = item.get("sector", "未知主题")
            strength = item.get("avg_strength")
            names.append(f"{sector}({strength})" if strength is not None else str(sector))
        else:
            names.append(str(item))
    return "、".join(names)


def _macro_text(value: dict) -> str:
    if not isinstance(value, dict):
        return str(value)
    parts = []
    if "cn_10y" in value:
        parts.append(f"10年国债{value.get('cn_10y')}")
    if "northbound_net" in value:
        parts.append(f"北向资金{value.get('northbound_net')}")
    if "margin_balance" in value:
        parts.append(f"融资余额{value.get('margin_balance')}")
    return "，".join(parts)
